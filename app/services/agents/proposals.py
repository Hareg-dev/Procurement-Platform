"""Human review and execution of agent proposals."""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agents import AgentProposal, AgentRun, ProposalStatus
from app.models.orm import User, utcnow
from app.models.procurement import (
    ActorType,
    OrganizationMember,
    OrgRole,
)
from app.models.procurement_schemas import RequisitionCreate
from app.services.agents.tools import CREATE_REQUISITION
from app.services.procurement import audit
from app.services.procurement.errors import (
    DomainError,
    InvalidState,
    NotFoundError,
    PermissionDenied,
)
from app.services.procurement.requisitions import requisition_service


@dataclass(frozen=True)
class ActionSpec:
    allowed_roles: frozenset[OrgRole]
    allow_self_review: bool


# Draft requisition creation is a low-risk action: the requester may approve the
# agent's draft themselves. High-impact actions (award, PO, payment) will set
# allow_self_review=False and require a different member.
ACTION_SPECS: dict[str, ActionSpec] = {
    CREATE_REQUISITION: ActionSpec(
        allowed_roles=frozenset(
            {OrgRole.REQUESTER, OrgRole.BUYER, OrgRole.ORG_ADMIN}
        ),
        allow_self_review=True,
    )
}


async def _get_proposal(
    db: AsyncSession,
    *,
    organization_id: int,
    proposal_id: int,
    lock: bool = False,
) -> AgentProposal:
    stmt = select(AgentProposal).where(
        AgentProposal.id == proposal_id,
        AgentProposal.organization_id == organization_id,
    )
    if lock:
        stmt = stmt.with_for_update()
    proposal = (await db.execute(stmt)).scalar_one_or_none()
    if proposal is None:
        raise NotFoundError("Agent proposal not found")
    return proposal


def _assert_can_review(
    member: OrganizationMember, proposal: AgentProposal
) -> ActionSpec:
    spec = ACTION_SPECS.get(proposal.action)
    if spec is None:
        raise DomainError(
            f"Unsupported proposal action: {proposal.action}"
        )
    if member.org_role not in spec.allowed_roles:
        raise PermissionDenied(
            "Your organizational role cannot review this proposal"
        )
    if (
        member.user_id == proposal.proposed_by_user_id
        and not spec.allow_self_review
    ):
        raise PermissionDenied(
            "A second reviewer is required for this proposal"
        )
    return spec


class ProposalService:
    async def list(
        self,
        db: AsyncSession,
        *,
        organization_id: int,
        status: Optional[ProposalStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AgentProposal]:
        stmt = select(AgentProposal).where(
            AgentProposal.organization_id == organization_id
        )
        if status is not None:
            stmt = stmt.where(AgentProposal.status == status)
        stmt = (
            stmt.order_by(AgentProposal.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def get(
        self, db: AsyncSession, *, organization_id: int, proposal_id: int
    ) -> AgentProposal:
        return await _get_proposal(
            db,
            organization_id=organization_id,
            proposal_id=proposal_id,
        )

    async def approve(
        self,
        db: AsyncSession,
        *,
        member: OrganizationMember,
        proposal_id: int,
        comment: Optional[str] = None,
    ) -> AgentProposal:
        proposal = await _get_proposal(
            db,
            organization_id=member.organization_id,
            proposal_id=proposal_id,
            lock=True,
        )
        _assert_can_review(member, proposal)

        if proposal.status != ProposalStatus.PENDING:
            raise InvalidState("This proposal has already been decided")
        if proposal.action != CREATE_REQUISITION:
            raise DomainError(
                f"Unsupported proposal action: {proposal.action}"
            )

        initiator = await db.get(User, proposal.proposed_by_user_id)
        if initiator is None:
            raise NotFoundError("The proposal initiator no longer exists")

        try:
            payload = RequisitionCreate.model_validate(proposal.payload)
            requisition = await requisition_service.create(
                db, member=member, requester=initiator, payload=payload
            )
        except Exception as exc:
            await db.rollback()
            failed = await _get_proposal(
                db,
                organization_id=member.organization_id,
                proposal_id=proposal_id,
            )
            failed.status = ProposalStatus.FAILED
            failed.reviewed_by_user_id = member.user_id
            failed.reviewed_at = utcnow()
            failed.review_comment = (
                comment or f"Execution failed: {exc}"
            )[:1000]
            audit.record_audit(
                db,
                organization_id=member.organization_id,
                actor=member.user,
                action="agent_proposal.failed",
                entity_type="agent_proposal",
                entity_id=failed.id,
                after={"error": str(exc)[:1000]},
            )
            await db.commit()
            raise DomainError(
                f"Proposal execution failed: {exc}"
            ) from exc

        proposal.status = ProposalStatus.EXECUTED
        proposal.reviewed_by_user_id = member.user_id
        proposal.reviewed_at = utcnow()
        proposal.review_comment = comment
        proposal.executed_entity_type = "requisition"
        proposal.executed_entity_id = requisition.id

        audit.record_audit(
            db,
            organization_id=member.organization_id,
            actor=member.user,
            action="agent_proposal.approved",
            entity_type="agent_proposal",
            entity_id=proposal.id,
            after={
                "requisition_id": requisition.id,
                "comment": comment,
            },
        )

        run = await db.get(AgentRun, proposal.run_id)
        agent_label = (
            f"{run.agent_name} ({run.model_name or 'unknown model'})"
            if run is not None
            else "agent"
        )
        audit.record_audit(
            db,
            organization_id=member.organization_id,
            actor=agent_label,
            actor_type=ActorType.AGENT,
            action="agent_proposal.executed",
            entity_type="agent_proposal",
            entity_id=proposal.id,
            after={
                "action": proposal.action,
                "requisition_id": requisition.id,
                "run_id": proposal.run_id,
            },
            correlation_id=run.correlation_id if run is not None else None,
        )
        audit.emit_event(
            db,
            organization_id=member.organization_id,
            event_type="agent_proposal.executed",
            aggregate_type="agent_proposal",
            aggregate_id=proposal.id,
            payload={
                "action": proposal.action,
                "requisition_id": requisition.id,
                "run_id": proposal.run_id,
            },
        )
        await db.commit()
        await db.refresh(proposal)
        return proposal

    async def reject(
        self,
        db: AsyncSession,
        *,
        member: OrganizationMember,
        proposal_id: int,
        comment: Optional[str] = None,
    ) -> AgentProposal:
        proposal = await _get_proposal(
            db,
            organization_id=member.organization_id,
            proposal_id=proposal_id,
            lock=True,
        )
        _assert_can_review(member, proposal)

        if proposal.status != ProposalStatus.PENDING:
            raise InvalidState("This proposal has already been decided")

        proposal.status = ProposalStatus.REJECTED
        proposal.reviewed_by_user_id = member.user_id
        proposal.reviewed_at = utcnow()
        proposal.review_comment = comment

        audit.record_audit(
            db,
            organization_id=member.organization_id,
            actor=member.user,
            action="agent_proposal.rejected",
            entity_type="agent_proposal",
            entity_id=proposal.id,
            after={"comment": comment},
        )
        await db.commit()
        await db.refresh(proposal)
        return proposal


proposal_service = ProposalService()
