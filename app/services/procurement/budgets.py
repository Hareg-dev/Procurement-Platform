"""Budget availability checks and spend commitment."""

from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import utcnow
from app.models.procurement import Budget, Requisition
from app.models.procurement_schemas import BudgetCreate
from app.services.procurement.errors import DomainError, InvalidState
from app.services.procurement.money import quantize_money


def current_fiscal_year() -> int:
    return utcnow().year


async def find_budget(
    db: AsyncSession,
    *,
    organization_id: int,
    cost_center: Optional[str],
    currency: str,
    fiscal_year: Optional[int] = None,
    lock: bool = False,
) -> Optional[Budget]:
    if not cost_center:
        return None

    stmt = select(Budget).where(
        Budget.organization_id == organization_id,
        Budget.cost_center == cost_center,
        Budget.fiscal_year == (fiscal_year or current_fiscal_year()),
        Budget.currency == currency,
    )
    if lock:
        stmt = stmt.with_for_update()

    return (await db.execute(stmt)).scalar_one_or_none()


def _insufficient(budget: Budget, requested: Decimal) -> DomainError:
    return DomainError(
        f"Insufficient budget for cost center '{budget.cost_center}': "
        f"available {budget.available_amount} {budget.currency}, "
        f"requested {requested}"
    )


async def assert_available(
    db: AsyncSession, requisition: Requisition
) -> Optional[Budget]:
    """Fail submission when a matching budget row cannot cover the total."""
    budget = await find_budget(
        db,
        organization_id=requisition.organization_id,
        cost_center=requisition.cost_center,
        currency=requisition.currency,
    )
    if budget is not None and budget.available_amount < requisition.total_amount:
        raise _insufficient(budget, requisition.total_amount)
    return budget


async def commit_spend(
    db: AsyncSession, requisition: Requisition
) -> Optional[Budget]:
    """Commit the requisition total against its budget (final approval)."""
    budget = await find_budget(
        db,
        organization_id=requisition.organization_id,
        cost_center=requisition.cost_center,
        currency=requisition.currency,
        lock=True,
    )
    if budget is None:
        return None
    if budget.available_amount < requisition.total_amount:
        raise _insufficient(budget, requisition.total_amount)

    budget.committed_amount = quantize_money(
        budget.committed_amount + requisition.total_amount
    )
    return budget


async def create_budget(
    db: AsyncSession, *, organization_id: int, payload: BudgetCreate
) -> Budget:
    existing = await find_budget(
        db,
        organization_id=organization_id,
        cost_center=payload.cost_center,
        currency=payload.currency,
        fiscal_year=payload.fiscal_year,
    )
    if existing is not None:
        raise InvalidState(
            "A budget already exists for this cost center, fiscal year and currency"
        )

    budget = Budget(
        organization_id=organization_id,
        cost_center=payload.cost_center,
        fiscal_year=payload.fiscal_year,
        currency=payload.currency,
        amount=payload.amount,
        committed_amount=Decimal("0"),
    )
    db.add(budget)
    await db.commit()
    await db.refresh(budget)
    return budget


async def list_budgets(
    db: AsyncSession, *, organization_id: int, fiscal_year: Optional[int] = None
) -> list[Budget]:
    stmt = select(Budget).where(Budget.organization_id == organization_id)
    if fiscal_year is not None:
        stmt = stmt.where(Budget.fiscal_year == fiscal_year)
    stmt = stmt.order_by(Budget.cost_center.asc(), Budget.fiscal_year.desc())
    return list((await db.execute(stmt)).scalars().all())
