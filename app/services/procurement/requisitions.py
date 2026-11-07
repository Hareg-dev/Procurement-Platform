"""Requisition lifecycle: draft, submit, cancel."""

from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.orm import User, utcnow
from app.models.procurement import (
    ApprovalStep,
    ApprovalStepStatus,
    OrganizationMember,
    OrgRole,
    Requisition,
    RequisitionLine,
    RequisitionStatus,
)
from app.models.procurement_schemas import (
    RequisitionCreate,
    RequisitionLineCreate,
    RequisitionUpdate,
)
from app.services.procurement import audit, budgets, policies
from app.services.procurement.errors import (
    DomainError,
    InvalidState,
    NotFoundError,
    PermissionDenied,
    VersionConflict,
)
from app.services.procurement.money import compute_line_total, quantize_money
from app.services.procurement.state import ensure_transition


def _append_lines(
    requisition: Requisition, lines_in: list[RequisitionLineCreate]
) -> Decimal:
    total = Decimal("0")
    for index, line_in in enumerate(lines_in, start=1):
        line_total = compute_line_total(line_in.quantity, line_in.unit_price)
        requisition.lines.append(
            RequisitionLine(
                line_number=index,
                description=line_in.description,
                quantity=line_in.quantity,
                unit_of_measure=line_in.unit_of_measure,
                unit_price=line_in.unit_price,
                line_total=line_total,
            )
        )
        total += line_total
    return quantize_money(total)


async def _replace_lines(
    db: AsyncSession,
    requisition: Requisition,
    lines_in: list[RequisitionLineCreate],
) -> None:
    # Flush the orphan deletes before inserting rows with the same
    # (requisition_id, line_number) pairs.
    requisition.lines.clear()
    await db.flush()
    requisition.total_amount = _append_lines(requisition, lines_in)


def _assert_can_edit(
    member: OrganizationMember, requisition: Requisition
) -> None:
    if member.org_role == OrgRole.ORG_ADMIN:
        return
    if requisition.requested_by_user_id == member.user_id:
        return
    raise PermissionDenied(
        "Only the requester or an organization admin can modify this requisition"
    )


class RequisitionService:
    async def create(
        self,
        db: AsyncSession,
        *,
        member: OrganizationMember,
        requester: User,
        payload: RequisitionCreate,
    ) -> Requisition:
        requisition = Requisition(
            organization_id=member.organization_id,
            # Temporary unique value; the human-readable number needs the id.
            requisition_number=f"TMP-{uuid4().hex}",
            title=payload.title,
            description=payload.description,
            cost_center=payload.cost_center,
            currency=payload.currency,
            total_amount=Decimal("0"),
            status=RequisitionStatus.DRAFT,
            requested_by_user_id=requester.id,
            needed_by=payload.needed_by,
            version=1,
        )
        requisition.total_amount = _append_lines(requisition, payload.lines)

        db.add(requisition)
        await db.flush()
        requisition.requisition_number = (
            f"REQ-{utcnow().year}-{requisition.id:06d}"
        )

        audit.record_audit(
            db,
            organization_id=member.organization_id,
            actor=requester,
            action="requisition.created",
            entity_type="requisition",
            entity_id=requisition.id,
            after=audit.requisition_snapshot(requisition),
        )
        await db.commit()

        return await self.get(
            db,
            organization_id=member.organization_id,
            requisition_id=requisition.id,
        )

    async def list(
        self,
        db: AsyncSession,
        *,
        organization_id: int,
        status: Optional[RequisitionStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Requisition]:
        stmt = select(Requisition).where(
            Requisition.organization_id == organization_id
        )
        if status is not None:
            stmt = stmt.where(Requisition.status == status)
        stmt = (
            stmt.order_by(Requisition.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def get(
        self, db: AsyncSession, *, organization_id: int, requisition_id: int
    ) -> Requisition:
        stmt = (
            select(Requisition)
            .where(
                Requisition.id == requisition_id,
                Requisition.organization_id == organization_id,
            )
            .options(
                selectinload(Requisition.lines),
                selectinload(Requisition.approval_steps),
            )
            # Services re-read after commit; refresh the identity map so newly
            # created lines/steps are not hidden by a stale loaded collection.
            .execution_options(populate_existing=True)
        )
        requisition = (await db.execute(stmt)).scalar_one_or_none()
        if requisition is None:
            # Do not reveal requisitions from other tenants.
            raise NotFoundError("Requisition not found")
        return requisition

    async def _get_for_update(
        self, db: AsyncSession, *, organization_id: int, requisition_id: int
    ) -> Requisition:
        stmt = (
            select(Requisition)
            .where(
                Requisition.id == requisition_id,
                Requisition.organization_id == organization_id,
            )
            .options(
                selectinload(Requisition.lines),
                selectinload(Requisition.approval_steps),
            )
            .with_for_update()
        )
        requisition = (await db.execute(stmt)).scalar_one_or_none()
        if requisition is None:
            raise NotFoundError("Requisition not found")
        return requisition

    async def update(
        self,
        db: AsyncSession,
        *,
        member: OrganizationMember,
        requisition_id: int,
        payload: RequisitionUpdate,
    ) -> Requisition:
        requisition = await self._get_for_update(
            db,
            organization_id=member.organization_id,
            requisition_id=requisition_id,
        )
        _assert_can_edit(member, requisition)

        if requisition.status != RequisitionStatus.DRAFT:
            raise InvalidState("Only draft requisitions can be edited")
        if requisition.version != payload.version:
            raise VersionConflict(
                "Requisition was modified by someone else; reload and retry"
            )

        before = audit.requisition_snapshot(requisition)

        changes = payload.model_dump(
            exclude_unset=True, exclude={"version", "lines"}
        )
        for field, value in changes.items():
            setattr(requisition, field, value)

        if payload.lines is not None:
            await _replace_lines(db, requisition, payload.lines)

        requisition.version += 1

        audit.record_audit(
            db,
            organization_id=member.organization_id,
            actor=member.user,
            action="requisition.updated",
            entity_type="requisition",
            entity_id=requisition.id,
            before=before,
            after=audit.requisition_snapshot(requisition),
        )
        await db.commit()

        return await self.get(
            db,
            organization_id=member.organization_id,
            requisition_id=requisition.id,
        )

    async def submit(
        self,
        db: AsyncSession,
        *,
        member: OrganizationMember,
        requisition_id: int,
        version: int,
    ) -> Requisition:
        requisition = await self._get_for_update(
            db,
            organization_id=member.organization_id,
            requisition_id=requisition_id,
        )
        if (
            member.org_role not in {OrgRole.ORG_ADMIN, OrgRole.BUYER}
            and requisition.requested_by_user_id != member.user_id
        ):
            raise PermissionDenied(
                "Only the requester, a buyer or an organization admin can submit"
            )
        if requisition.version != version:
            raise VersionConflict(
                "Requisition was modified by someone else; reload and retry"
            )

        ensure_transition(requisition.status, RequisitionStatus.IN_APPROVAL)

        if not requisition.lines:
            raise DomainError(
                "A requisition needs at least one line before submission"
            )

        await budgets.assert_available(db, requisition)
        resolved_steps = await policies.resolve_steps(db, requisition)

        for step_order, required_role, policy_id in resolved_steps:
            db.add(
                ApprovalStep(
                    requisition_id=requisition.id,
                    policy_id=policy_id,
                    step_order=step_order,
                    required_role=required_role,
                )
            )

        before = audit.requisition_snapshot(requisition)
        requisition.status = RequisitionStatus.IN_APPROVAL
        requisition.submitted_at = utcnow()
        requisition.version += 1

        audit.record_audit(
            db,
            organization_id=member.organization_id,
            actor=member.user,
            action="requisition.submitted",
            entity_type="requisition",
            entity_id=requisition.id,
            before=before,
            after=audit.requisition_snapshot(requisition),
        )
        audit.emit_event(
            db,
            organization_id=member.organization_id,
            event_type="requisition.submitted",
            aggregate_type="requisition",
            aggregate_id=requisition.id,
            payload={
                "requisition_number": requisition.requisition_number,
                "total_amount": requisition.total_amount,
                "currency": requisition.currency,
                "steps": [
                    {
                        "step_order": step_order,
                        "required_role": required_role.value,
                    }
                    for step_order, required_role, _ in resolved_steps
                ],
            },
        )
        await db.commit()

        return await self.get(
            db,
            organization_id=member.organization_id,
            requisition_id=requisition.id,
        )

    async def cancel(
        self,
        db: AsyncSession,
        *,
        member: OrganizationMember,
        requisition_id: int,
        version: int,
        reason: Optional[str] = None,
    ) -> Requisition:
        requisition = await self._get_for_update(
            db,
            organization_id=member.organization_id,
            requisition_id=requisition_id,
        )
        if (
            member.org_role != OrgRole.ORG_ADMIN
            and requisition.requested_by_user_id != member.user_id
        ):
            raise PermissionDenied(
                "Only the requester or an organization admin can cancel"
            )
        if requisition.version != version:
            raise VersionConflict(
                "Requisition was modified by someone else; reload and retry"
            )

        ensure_transition(requisition.status, RequisitionStatus.CANCELLED)

        before = audit.requisition_snapshot(requisition)
        for step in requisition.approval_steps:
            if step.status == ApprovalStepStatus.PENDING:
                step.status = ApprovalStepStatus.SKIPPED

        requisition.status = RequisitionStatus.CANCELLED
        requisition.decided_at = utcnow()
        requisition.version += 1

        audit.record_audit(
            db,
            organization_id=member.organization_id,
            actor=member.user,
            action="requisition.cancelled",
            entity_type="requisition",
            entity_id=requisition.id,
            before=before,
            after={
                **audit.requisition_snapshot(requisition),
                "reason": reason,
            },
        )
        audit.emit_event(
            db,
            organization_id=member.organization_id,
            event_type="requisition.cancelled",
            aggregate_type="requisition",
            aggregate_id=requisition.id,
            payload={"reason": reason},
        )
        await db.commit()

        return await self.get(
            db,
            organization_id=member.organization_id,
            requisition_id=requisition.id,
        )


requisition_service = RequisitionService()
