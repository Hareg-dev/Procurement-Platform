from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v2.deps import get_org_member
from app.core.db import get_db
from app.models.orm import User
from app.models.procurement_schemas import (
    ApprovalDecisionRequest,
    ApprovalStepResponse,
    PendingApprovalItem,
    RequisitionResponse,
    RequisitionSummary,
)
from app.services.procurement.approvals import approval_service

router = APIRouter(tags=["v2-approvals"])


@router.get(
    "/approvals",
    response_model=list[PendingApprovalItem],
    summary="List approval steps the caller can decide now",
)
async def list_pending_approvals(
    member=Depends(get_org_member),
    db: AsyncSession = Depends(get_db),
) -> list[PendingApprovalItem]:
    rows = await approval_service.pending_for_member(db, member=member)

    requester_ids = {requisition.requested_by_user_id for _, requisition in rows}
    requesters: dict[int, User] = {}
    if requester_ids:
        result = await db.execute(select(User).where(User.id.in_(requester_ids)))
        requesters = {user.id: user for user in result.scalars().all()}

    items: list[PendingApprovalItem] = []
    for step, requisition in rows:
        requester = requesters.get(requisition.requested_by_user_id)
        items.append(
            PendingApprovalItem(
                step=ApprovalStepResponse.model_validate(step),
                requisition=RequisitionSummary.model_validate(requisition),
                requested_by_name=(
                    f"{requester.first_name} {requester.last_name}"
                    if requester
                    else "Unknown user"
                ),
            )
        )
    return items


@router.post(
    "/approvals/{step_id}/decision",
    response_model=RequisitionResponse,
    summary="Approve or reject the current approval step",
)
async def decide_approval_step(
    step_id: int,
    payload: ApprovalDecisionRequest,
    member=Depends(get_org_member),
    db: AsyncSession = Depends(get_db),
) -> RequisitionResponse:
    return await approval_service.decide(
        db, member=member, step_id=step_id, payload=payload
    )
