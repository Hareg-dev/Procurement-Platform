"""Permissioned tools the intake agent may call.

Every tool runs as the initiating user and inside their tenant. Read tools only
read; the proposal tool writes an ``AgentProposal`` and nothing else. The tool
layer also records the call/result as provenance steps on the run.
"""

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agents import AgentProposal, AgentRun, AgentStep, ProposalStatus
from app.models.orm import User
from app.models.procurement import ActorType, OrganizationMember
from app.models.procurement_schemas import RequisitionCreate, RequisitionLineCreate
from app.services.procurement import audit
from app.services.procurement.budgets import find_budget, list_budgets
from app.services.procurement.errors import DomainError
from app.services.procurement.money import compute_line_total, quantize_money
from app.services.procurement.requisitions import requisition_service

CREATE_REQUISITION = "create_requisition"


@dataclass
class ToolContext:
    db: AsyncSession
    user: User
    member: OrganizationMember
    run: AgentRun
    step_index: int = 0
    state: dict = field(default_factory=dict)

    @property
    def organization_id(self) -> int:
        return self.member.organization_id


class EmptyArgs(BaseModel):
    pass


class RecentRequisitionsArgs(BaseModel):
    limit: int = Field(default=5, ge=1, le=20)


class ProposalLineArgs(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    quantity: Decimal = Field(..., gt=0)
    unit_of_measure: str = Field(default="unit", min_length=1, max_length=20)
    unit_price: Decimal = Field(..., ge=0)


class ProposeRequisitionArgs(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    cost_center: Optional[str] = None
    currency: str = Field(..., min_length=3, max_length=3)
    needed_by: Optional[str] = Field(
        None, description="ISO date, e.g. 2026-12-31"
    )
    lines: list[ProposalLineArgs] = Field(..., min_length=1)
    rationale: str = Field(..., min_length=1, max_length=2000)
    confidence: float = Field(..., ge=0, le=1)
    evidence: Optional[list[str]] = None


def _validation_details(exc: ValidationError) -> list[dict]:
    return [
        {"loc": list(item.get("loc", ())), "msg": item.get("msg"), "type": item.get("type")}
        for item in exc.errors()
    ]


async def add_step(
    ctx: ToolContext,
    *,
    kind: str,
    role: Optional[str] = None,
    content: Optional[str] = None,
    tool_name: Optional[str] = None,
    tool_input: Optional[dict] = None,
    tool_output: Optional[dict] = None,
) -> AgentStep:
    step = AgentStep(
        run_id=ctx.run.id,
        step_index=ctx.step_index,
        kind=kind,
        role=role,
        content=content,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_output,
    )
    ctx.step_index += 1
    ctx.db.add(step)
    await ctx.db.flush()
    return step


async def _execute_tool(
    ctx: ToolContext,
    name: str,
    arguments: dict,
    handler: Callable[[], Any],
) -> dict:
    await add_step(
        ctx,
        kind="tool_call",
        role="assistant",
        tool_name=name,
        tool_input=arguments,
    )
    try:
        result = await handler()
    except ValidationError as exc:
        result = {
            "error": "Invalid tool arguments",
            "details": _validation_details(exc),
        }
    except DomainError as exc:
        result = {"error": str(exc)}
    except Exception as exc:  # tools report errors to the model, not crash the run
        result = {"error": str(exc)[:1000]}

    await add_step(
        ctx,
        kind="tool_result",
        role="tool",
        tool_name=name,
        tool_input=arguments,
        tool_output=result,
    )
    return result


async def _list_budgets(ctx: ToolContext) -> dict:
    budgets = await list_budgets(
        ctx.db, organization_id=ctx.organization_id
    )
    return {
        "budgets": [
            {
                "cost_center": budget.cost_center,
                "fiscal_year": budget.fiscal_year,
                "currency": budget.currency,
                "amount": str(budget.amount),
                "committed": str(budget.committed_amount),
                "available": str(budget.available_amount),
            }
            for budget in budgets
        ]
    }


async def _recent_requisitions(ctx: ToolContext, limit: int) -> dict:
    requisitions = await requisition_service.list(
        ctx.db,
        organization_id=ctx.organization_id,
        limit=limit,
    )
    return {
        "requisitions": [
            {
                "requisition_number": item.requisition_number,
                "title": item.title,
                "status": item.status.value,
                "total_amount": str(item.total_amount),
                "currency": item.currency,
                "cost_center": item.cost_center,
            }
            for item in requisitions
        ]
    }


async def _create_proposal(
    ctx: ToolContext, args: ProposeRequisitionArgs
) -> dict:
    if ctx.state.get("proposal_id") is not None:
        return {
            "error": "This run already recorded a proposal. Do not propose again."
        }

    payload = RequisitionCreate(
        title=args.title,
        description=args.description,
        cost_center=args.cost_center,
        currency=args.currency,
        needed_by=args.needed_by,
        lines=[
            RequisitionLineCreate(**line.model_dump())
            for line in args.lines
        ],
    )

    total = quantize_money(
        sum(
            (
                compute_line_total(line.quantity, line.unit_price)
                for line in payload.lines
            ),
            Decimal("0"),
        )
    )

    budget = await find_budget(
        ctx.db,
        organization_id=ctx.organization_id,
        cost_center=payload.cost_center,
        currency=payload.currency,
    )

    evidence: list[dict] = [
        {"source": "agent", "detail": detail}
        for detail in (args.evidence or [])
    ]
    evidence.append(
        {
            "source": "system",
            "detail": f"Computed total {total} {payload.currency}",
        }
    )
    if budget is not None:
        evidence.append(
            {
                "source": "budget",
                "detail": (
                    f"Cost center {budget.cost_center} has "
                    f"{budget.available_amount} {budget.currency} available"
                ),
                "sufficient": budget.available_amount >= total,
            }
        )

    proposal = AgentProposal(
        organization_id=ctx.organization_id,
        run_id=ctx.run.id,
        action=CREATE_REQUISITION,
        payload=json.loads(payload.model_dump_json()),
        rationale=args.rationale,
        evidence=evidence,
        confidence=Decimal(str(args.confidence)).quantize(
            Decimal("0.001")
        ),
        status=ProposalStatus.PENDING,
        proposed_by_user_id=ctx.user.id,
    )
    ctx.db.add(proposal)
    await ctx.db.flush()

    ctx.state["proposal_id"] = proposal.id

    agent_label = f"{ctx.run.agent_name} ({ctx.run.model_name or 'unknown model'})"
    audit.record_audit(
        ctx.db,
        organization_id=ctx.organization_id,
        actor=agent_label,
        actor_type=ActorType.AGENT,
        action="agent_proposal.created",
        entity_type="agent_proposal",
        entity_id=proposal.id,
        correlation_id=ctx.run.correlation_id,
        after={
            "action": proposal.action,
            "total_amount": str(total),
            "currency": payload.currency,
            "confidence": str(proposal.confidence),
            "run_id": ctx.run.id,
        },
    )

    return {
        "proposal_id": proposal.id,
        "status": "pending",
        "total_amount": str(total),
        "currency": payload.currency,
        "budget_sufficient": (
            budget is None or budget.available_amount >= total
        ),
        "message": (
            "Proposal recorded for human review. No requisition has been "
            "created; approval is required."
        ),
    }


async def tool_list_budgets(
    ctx: ToolContext, args: EmptyArgs
) -> dict:
    return await _execute_tool(
        ctx, "list_budgets", {}, lambda: _list_budgets(ctx)
    )


async def tool_recent_requisitions(
    ctx: ToolContext, args: RecentRequisitionsArgs
) -> dict:
    return await _execute_tool(
        ctx,
        "list_recent_requisitions",
        {"limit": args.limit},
        lambda: _recent_requisitions(ctx, args.limit),
    )


async def tool_propose_requisition(
    ctx: ToolContext, args: ProposeRequisitionArgs
) -> dict:
    return await _execute_tool(
        ctx,
        "propose_requisition",
        args.model_dump(mode="json"),
        lambda: _create_proposal(ctx, args),
    )


def build_toolkit(ctx: ToolContext):
    """Build the AgentScope toolkit bound to this run's context."""
    # Import order matters for AgentScope 2.0 on this host: model must be
    # imported before the agent/tool modules to avoid a native init crash.
    import agentscope.model  # noqa: F401
    from agentscope.tool import FunctionTool, Toolkit

    async def list_budgets_fn() -> dict:
        return await tool_list_budgets(ctx, EmptyArgs())

    async def recent_requisitions_fn(limit: int = 5) -> dict:
        return await tool_recent_requisitions(
            ctx, RecentRequisitionsArgs(limit=limit)
        )

    async def propose_requisition_fn(
        title: str,
        currency: str,
        lines: list[dict],
        rationale: str,
        confidence: float,
        description: Optional[str] = None,
        cost_center: Optional[str] = None,
        needed_by: Optional[str] = None,
        evidence: Optional[list[str]] = None,
    ) -> dict:
        try:
            args = ProposeRequisitionArgs(
                title=title,
                currency=currency,
                lines=lines,
                rationale=rationale,
                confidence=confidence,
                description=description,
                cost_center=cost_center,
                needed_by=needed_by,
                evidence=evidence,
            )
        except ValidationError as exc:
            return {
                "error": "Invalid proposal arguments",
                "details": _validation_details(exc),
            }
        return await tool_propose_requisition(ctx, args)

    return Toolkit(
        tools=[
            FunctionTool(
                list_budgets_fn,
                name="list_budgets",
                description=(
                    "List the caller organization's cost-center budgets with "
                    "available amounts. Use before proposing to check funding."
                ),
                input_schema=EmptyArgs,
                is_read_only=True,
                is_concurrency_safe=False,
            ),
            FunctionTool(
                recent_requisitions_fn,
                name="list_recent_requisitions",
                description=(
                    "Show recent requisitions to infer cost centers, currency "
                    "and naming conventions."
                ),
                input_schema=RecentRequisitionsArgs,
                is_read_only=True,
                is_concurrency_safe=False,
            ),
            FunctionTool(
                propose_requisition_fn,
                name="propose_requisition",
                description=(
                    "Record a draft requisition proposal for human approval. "
                    "This never creates a requisition. Call it at most once, "
                    "with every line priced and a rationale."
                ),
                input_schema=ProposeRequisitionArgs,
                is_read_only=False,
                is_concurrency_safe=False,
            ),
        ]
    )
