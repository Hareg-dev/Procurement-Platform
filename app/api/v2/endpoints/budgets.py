from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v2.deps import require_org_roles
from app.core.db import get_db
from app.models.procurement import OrgRole
from app.models.procurement_schemas import BudgetCreate, BudgetResponse
from app.services.procurement.budgets import (
    create_budget as create_budget_record,
    list_budgets as list_budget_records,
)

router = APIRouter(prefix="/budgets", tags=["v2-budgets"])

can_manage_budgets = require_org_roles(OrgRole.FINANCE, OrgRole.ORG_ADMIN)


@router.get(
    "",
    response_model=list[BudgetResponse],
    summary="List budgets for the caller's organization",
)
async def list_budgets(
    fiscal_year: Optional[int] = Query(None, ge=2000, le=2100),
    member=Depends(can_manage_budgets),
    db: AsyncSession = Depends(get_db),
) -> list[BudgetResponse]:
    return await list_budget_records(
        db,
        organization_id=member.organization_id,
        fiscal_year=fiscal_year,
    )


@router.post(
    "",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a cost-center budget",
)
async def create_budget(
    payload: BudgetCreate,
    member=Depends(can_manage_budgets),
    db: AsyncSession = Depends(get_db),
) -> BudgetResponse:
    return await create_budget_record(
        db, organization_id=member.organization_id, payload=payload
    )
