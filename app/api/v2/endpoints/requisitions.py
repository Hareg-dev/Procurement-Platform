from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v2.deps import get_org_member
from app.core.db import get_db
from app.models.procurement import RequisitionStatus
from app.models.procurement_schemas import (
    ApprovalStepResponse,
    CancelRequisitionRequest,
    RequisitionCreate,
    RequisitionResponse,
    RequisitionSummary,
    RequisitionUpdate,
    VersionedRequest,
)
from app.services.procurement.requisitions import requisition_service

router = APIRouter(prefix="/requisitions", tags=["v2-requisitions"])

# Any active member of the organization may raise demand. Approval rights are
# a separate gate handled by the approval step's required role.
can_raise_requisition = get_org_member


@router.post(
    "",
    response_model=RequisitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft requisition",
)
async def create_requisition(
    payload: RequisitionCreate,
    member=Depends(can_raise_requisition),
    db: AsyncSession = Depends(get_db),
) -> RequisitionResponse:
    return await requisition_service.create(
        db, member=member, requester=member.user, payload=payload
    )


@router.get(
    "",
    response_model=list[RequisitionSummary],
    summary="List requisitions in the caller's organization",
)
async def list_requisitions(
    status_filter: Optional[RequisitionStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member=Depends(get_org_member),
    db: AsyncSession = Depends(get_db),
) -> list[RequisitionSummary]:
    return await requisition_service.list(
        db,
        organization_id=member.organization_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{requisition_id}",
    response_model=RequisitionResponse,
    summary="Get a requisition with lines and approval steps",
)
async def get_requisition(
    requisition_id: int,
    member=Depends(get_org_member),
    db: AsyncSession = Depends(get_db),
) -> RequisitionResponse:
    return await requisition_service.get(
        db,
        organization_id=member.organization_id,
        requisition_id=requisition_id,
    )


@router.patch(
    "/{requisition_id}",
    response_model=RequisitionResponse,
    summary="Edit a draft requisition (optimistic concurrency)",
)
async def update_requisition(
    requisition_id: int,
    payload: RequisitionUpdate,
    member=Depends(can_raise_requisition),
    db: AsyncSession = Depends(get_db),
) -> RequisitionResponse:
    return await requisition_service.update(
        db,
        member=member,
        requisition_id=requisition_id,
        payload=payload,
    )


@router.post(
    "/{requisition_id}/submit",
    response_model=RequisitionResponse,
    summary="Submit a requisition for approval",
)
async def submit_requisition(
    requisition_id: int,
    payload: VersionedRequest,
    member=Depends(can_raise_requisition),
    db: AsyncSession = Depends(get_db),
) -> RequisitionResponse:
    return await requisition_service.submit(
        db,
        member=member,
        requisition_id=requisition_id,
        version=payload.version,
    )


@router.post(
    "/{requisition_id}/cancel",
    response_model=RequisitionResponse,
    summary="Cancel a requisition before a final decision",
)
async def cancel_requisition(
    requisition_id: int,
    payload: CancelRequisitionRequest,
    member=Depends(can_raise_requisition),
    db: AsyncSession = Depends(get_db),
) -> RequisitionResponse:
    return await requisition_service.cancel(
        db,
        member=member,
        requisition_id=requisition_id,
        version=payload.version,
        reason=payload.reason,
    )


@router.get(
    "/{requisition_id}/approvals",
    response_model=list[ApprovalStepResponse],
    summary="List approval steps for a requisition",
)
async def list_requisition_approvals(
    requisition_id: int,
    member=Depends(get_org_member),
    db: AsyncSession = Depends(get_db),
) -> list[ApprovalStepResponse]:
    requisition = await requisition_service.get(
        db,
        organization_id=member.organization_id,
        requisition_id=requisition_id,
    )
    return requisition.approval_steps
