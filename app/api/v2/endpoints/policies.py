from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v2.deps import require_org_roles
from app.core.db import get_db
from app.models.procurement import OrgRole
from app.models.procurement_schemas import (
    ApprovalPolicyCreate,
    ApprovalPolicyResponse,
)
from app.services.procurement.policies import (
    create_policy as create_policy_record,
    list_policies as list_policy_records,
)

router = APIRouter(prefix="/approval-policies", tags=["v2-approvals"])

can_manage_policies = require_org_roles(OrgRole.ORG_ADMIN)


@router.get(
    "",
    response_model=list[ApprovalPolicyResponse],
    summary="List the organization's approval matrix",
)
async def list_policies(
    member=Depends(can_manage_policies),
    db: AsyncSession = Depends(get_db),
) -> list[ApprovalPolicyResponse]:
    return await list_policy_records(
        db, organization_id=member.organization_id
    )


@router.post(
    "",
    response_model=ApprovalPolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an amount-band approval step",
)
async def create_policy(
    payload: ApprovalPolicyCreate,
    member=Depends(can_manage_policies),
    db: AsyncSession = Depends(get_db),
) -> ApprovalPolicyResponse:
    return await create_policy_record(
        db, organization_id=member.organization_id, payload=payload
    )
