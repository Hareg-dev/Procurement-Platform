"""Approval inbox and decision handling."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.orm import utcnow
from app.models.procurement import (
    ApprovalStep,
    ApprovalStepStatus,
    OrganizationMember,
    Requisition,
    RequisitionStatus,
)
from app.models.procurement_schemas import ApprovalDecisionRequest
from app.services.procurement import audit, budgets
from app.services.procurement.errors import (
    InvalidState,
    NotFoundError,
    PermissionDenied,
    VersionConflict,
)
from app.services.procurement.requisitions import requisition_service
from app.services.procurement.state import ensure_transition


class ApprovalService:
    async def pending_for_member(
        self, db: AsyncSession, *, member: OrganizationMember
    ) -> list[tuple[ApprovalStep, Requisition]]:
        """Pending steps the member may act on right now."""
        stmt = (
            select(ApprovalStep, Requisition)
            .join(Requisition, ApprovalStep.requisition_id == Requisition.id)
            .where(
                Requisition.organization_id == member.organization_id,
                Requisition.status == RequisitionStatus.IN_APPROVAL,
                ApprovalStep.status == ApprovalStepStatus.PENDING,
                ApprovalStep.required_role == member.org_role,
                # Segregation of duties: never surface your own request.
                Requisition.requested_by_user_id != member.user_id,
            )
            .order_by(
                Requisition.created_at.desc(), ApprovalStep.step_order.asc()
            )
        )
        rows = list((await db.execute(stmt)).all())

        # Only the lowest outstanding step is actionable.
        min_order: dict[int, int] = {}
        for step, requisition in rows:
            min_order[requisition.id] = min(
                min_order.get(requisition.id, step.step_order),
                step.step_order,
            )

        return [
            (step, requisition)
            for step, requisition in rows
            if step.step_order == min_order[requisition.id]
        ]

    async def decide(
        self,
        db: AsyncSession,
        *,
        member: OrganizationMember,
        step_id: int,
        payload: ApprovalDecisionRequest,
    ) -> Requisition:
        stmt = (
            select(ApprovalStep)
            .where(ApprovalStep.id == step_id)
            .options(
                selectinload(ApprovalStep.requisition).selectinload(
                    Requisition.approval_steps
                )
            )
            .with_for_update()
        )
        step = (await db.execute(stmt)).scalar_one_or_none()
        if step is None:
            raise NotFoundError("Approval step not found")

        requisition = step.requisition
        if requisition.organization_id != member.organization_id:
            raise NotFoundError("Approval step not found")

        if requisition.version != payload.version:
            raise VersionConflict(
                "Requisition was modified by someone else; reload and retry"
            )
        if requisition.status != RequisitionStatus.IN_APPROVAL:
            raise InvalidState("Requisition is not awaiting approval")
        if step.status != ApprovalStepStatus.PENDING:
            raise InvalidState("This approval step has already been decided")
        if requisition.requested_by_user_id == member.user_id:
            raise PermissionDenied(
                "The requester cannot approve their own requisition"
            )
        if step.required_role != member.org_role:
            raise PermissionDenied(
                f"This step requires the '{step.required_role.value}' role"
            )

        pending = [
            candidate
            for candidate in requisition.approval_steps
            if candidate.status == ApprovalStepStatus.PENDING
        ]
        if not pending or step.step_order != min(
            candidate.step_order for candidate in pending
        ):
            raise InvalidState("Another approval step must be decided first")

        before_status = requisition.status
        step.decided_by_user_id = member.user_id
        step.decided_at = utcnow()
        step.comment = payload.comment

        if payload.decision == "approve":
            step.status = ApprovalStepStatus.APPROVED
            remaining = [
                candidate for candidate in pending if candidate.id != step.id
            ]
            if remaining:
                requisition.version += 1
            else:
                ensure_transition(
                    requisition.status, RequisitionStatus.APPROVED
                )
                # Commit the spend in the same transaction as the decision.
                await budgets.commit_spend(db, requisition)
                requisition.status = RequisitionStatus.APPROVED
                requisition.decided_at = utcnow()
                requisition.version += 1
                audit.emit_event(
                    db,
                    organization_id=requisition.organization_id,
                    event_type="requisition.approved",
                    aggregate_type="requisition",
                    aggregate_id=requisition.id,
                    payload={
                        "requisition_number": requisition.requisition_number,
                        "total_amount": requisition.total_amount,
                        "currency": requisition.currency,
                    },
                )
        else:
            step.status = ApprovalStepStatus.REJECTED
            for candidate in requisition.approval_steps:
                if (
                    candidate.status == ApprovalStepStatus.PENDING
                    and candidate.id != step.id
                ):
                    candidate.status = ApprovalStepStatus.SKIPPED
            ensure_transition(
                requisition.status, RequisitionStatus.REJECTED
            )
            requisition.status = RequisitionStatus.REJECTED
            requisition.decided_at = utcnow()
            requisition.version += 1
            audit.emit_event(
                db,
                organization_id=requisition.organization_id,
                event_type="requisition.rejected",
                aggregate_type="requisition",
                aggregate_id=requisition.id,
                payload={"comment": payload.comment},
            )

        audit.record_audit(
            db,
            organization_id=requisition.organization_id,
            actor=member.user,
            action=f"approval_step.{payload.decision}",
            entity_type="approval_step",
            entity_id=step.id,
            before={"status": "pending"},
            after={
                "status": step.status.value,
                "step_order": step.step_order,
                "required_role": step.required_role.value,
                "comment": payload.comment,
            },
        )
        if requisition.status != before_status:
            audit.record_audit(
                db,
                organization_id=requisition.organization_id,
                actor=member.user,
                action=f"requisition.{requisition.status.value}",
                entity_type="requisition",
                entity_id=requisition.id,
                before={"status": before_status.value},
                after={"status": requisition.status.value},
            )

        await db.commit()

        return await requisition_service.get(
            db,
            organization_id=requisition.organization_id,
            requisition_id=requisition.id,
        )


approval_service = ApprovalService()
