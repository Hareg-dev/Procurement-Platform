"""AgentScope intake agent backed by Groq.

The agent is created per run with a Toolkit bound to the initiating user and
tenant. Only the tools can touch data, and the only write tool records a
proposal. The runtime persists the run, each provenance step and token usage.
"""

import hashlib
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.request_context import get_request_id
from app.models.agents import AgentRun, AgentRunStatus, AgentStep
from app.models.orm import User, utcnow
from app.models.procurement import ActorType, OrganizationMember
from app.services.agents.errors import AgentRunFailed, AgentUnavailable
from app.services.agents.tools import ToolContext, add_step, build_toolkit
from app.services.procurement import audit
from app.services.procurement.errors import NotFoundError


SYSTEM_PROMPT = """You are the intake agent for a multi-tenant procurement platform.
Your job is to turn a buyer's request into a well-formed draft requisition proposal.

Rules:
- Use only the provided tools. Never invent budget data, suppliers or prices.
- Call list_budgets and list_recent_requisitions when you need context.
- If essential information is missing (what, how much, when, cost center),
  ask at most one short clarifying question and stop.
- Otherwise call propose_requisition exactly once, with every line priced,
  a rationale and a confidence between 0 and 1.
- propose_requisition only records a proposal for human approval. It never
  creates a requisition. Never claim that a requisition was created.
- Quantities and unit prices are positive decimals. Use the organization's
  currency; use USD only if nothing indicates otherwise.
- Keep your final answer short and state that the proposal is awaiting review.
"""


def build_model(
    *,
    api_key: str,
    base_url: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
):
    """Build an AgentScope OpenAI-compatible model pointed at Groq."""
    # Import order workaround for AgentScope 2.0.11: model before agent/tool.
    import agentscope.model  # noqa: F401
    from agentscope.credential import OpenAICredential
    from agentscope.model import OpenAIChatModel

    return OpenAIChatModel(
        credential=OpenAICredential(api_key=api_key, base_url=base_url),
        model=model_name,
        stream=False,
        parameters=OpenAIChatModel.Parameters(
            temperature=temperature,
            max_tokens=max_tokens,
        ),
    )


def _extract_text(reply: Any) -> str:
    content = getattr(reply, "content", None)
    if isinstance(content, str):
        return content.strip()
    parts: list[str] = []
    for block in content or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()


def _usage(reply: Any) -> tuple[Optional[int], Optional[int]]:
    usage = getattr(reply, "usage", None)
    return (
        getattr(usage, "input_tokens", None),
        getattr(usage, "output_tokens", None),
    )


async def add_run_step(
    db: AsyncSession,
    run: AgentRun,
    index: int,
    kind: str,
    *,
    role: Optional[str] = None,
    content: Optional[str] = None,
) -> AgentStep:
    step = AgentStep(
        run_id=run.id,
        step_index=index,
        kind=kind,
        role=role,
        content=content,
    )
    db.add(step)
    await db.flush()
    return step


async def load_run(
    db: AsyncSession, *, organization_id: int, run_id: int
) -> AgentRun:
    stmt = (
        select(AgentRun)
        .where(
            AgentRun.id == run_id,
            AgentRun.organization_id == organization_id,
        )
        .options(
            selectinload(AgentRun.steps),
            selectinload(AgentRun.proposals),
        )
        .execution_options(populate_existing=True)
    )
    run = (await db.execute(stmt)).scalar_one_or_none()
    if run is None:
        raise NotFoundError("Agent run not found")
    return run


async def list_runs(
    db: AsyncSession,
    *,
    organization_id: int,
    status: Optional[AgentRunStatus] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AgentRun]:
    stmt = select(AgentRun).where(
        AgentRun.organization_id == organization_id
    )
    if status is not None:
        stmt = stmt.where(AgentRun.status == status)
    stmt = (
        stmt.order_by(AgentRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


class IntakeAgentRuntime:
    agent_name = "IntakeAgent"

    async def run(
        self,
        db: AsyncSession,
        *,
        user: User,
        member: OrganizationMember,
        message: str,
    ) -> AgentRun:
        if not settings.groq_api_key:
            raise AgentUnavailable(
                "Agent runtime is not configured: set GROQ_API_KEY"
            )

        prompt_hash = hashlib.sha256(
            f"{SYSTEM_PROMPT}\n{message}".encode("utf-8")
        ).hexdigest()

        run = AgentRun(
            organization_id=member.organization_id,
            initiated_by_user_id=user.id,
            agent_name=self.agent_name,
            model_name=settings.groq_model,
            status=AgentRunStatus.RUNNING,
            prompt_hash=prompt_hash,
            input={"message": message},
            correlation_id=get_request_id(),
            started_at=utcnow(),
        )
        db.add(run)
        await db.flush()
        await add_run_step(
            db, run, 0, "message", role="user", content=message
        )
        # Persist the run before calling the model so a crash or timeout still
        # leaves an auditable run row; in-flight steps are committed on success.
        await db.commit()

        ctx = ToolContext(
            db=db, user=user, member=member, run=run, step_index=1
        )

        try:
            reply = await self._invoke(ctx, message)
        except Exception as exc:
            await db.rollback()
            failed = await db.get(AgentRun, run.id)
            if failed is not None:
                failed.status = AgentRunStatus.FAILED
                failed.error = str(exc)[:4000]
                failed.finished_at = utcnow()
                await add_run_step(
                    db,
                    failed,
                    1,
                    "error",
                    content=str(exc)[:4000],
                )
                audit.record_audit(
                    db,
                    organization_id=failed.organization_id,
                    actor=f"{self.agent_name} ({failed.model_name})",
                    actor_type=ActorType.AGENT,
                    action="agent_run.failed",
                    entity_type="agent_run",
                    entity_id=failed.id,
                    after={"error": str(exc)[:1000]},
                    correlation_id=failed.correlation_id,
                )
                await db.commit()
            raise AgentRunFailed(f"Agent run failed: {exc}") from exc

        text = _extract_text(reply)
        await add_step(ctx, kind="final", role="assistant", content=text)

        prompt_tokens, completion_tokens = _usage(reply)
        run.status = AgentRunStatus.COMPLETED
        run.output = {
            "reply": text,
            "proposal_id": ctx.state.get("proposal_id"),
        }
        run.prompt_tokens = prompt_tokens
        run.completion_tokens = completion_tokens
        run.finished_at = utcnow()

        audit.record_audit(
            db,
            organization_id=run.organization_id,
            actor=f"{self.agent_name} ({run.model_name})",
            actor_type=ActorType.AGENT,
            action="agent_run.completed",
            entity_type="agent_run",
            entity_id=run.id,
            after={
                "status": AgentRunStatus.COMPLETED.value,
                "proposal_id": ctx.state.get("proposal_id"),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
            correlation_id=run.correlation_id,
        )
        await db.commit()

        return await load_run(
            db,
            organization_id=run.organization_id,
            run_id=run.id,
        )

    async def _invoke(self, ctx: ToolContext, message: str):
        """Run the AgentScope ReAct loop. Overridden in tests."""
        model = build_model(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
            model_name=settings.groq_model,
            temperature=settings.agent_temperature,
            max_tokens=settings.agent_max_tokens,
        )

        import agentscope.model  # noqa: F401  (import order workaround)
        from agentscope.agent import Agent, ReActConfig
        from agentscope.message import Msg, TextBlock

        agent = Agent(
            name=self.agent_name,
            system_prompt=SYSTEM_PROMPT,
            model=model,
            toolkit=build_toolkit(ctx),
            react_config=ReActConfig(max_iters=settings.agent_max_iters),
        )
        return await agent.reply(
            Msg(
                name="user",
                content=[TextBlock(type="text", text=message)],
                role="user",
            )
        )


intake_agent_runtime = IntakeAgentRuntime()
