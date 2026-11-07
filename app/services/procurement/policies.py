"""Approval-matrix resolution.

An organization can configure amount bands per role/step. When it has no
policies, a conservative default ladder applies so a tenant is usable on day
one; the ladder is intentionally simple and can be replaced by policies.
"""

from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.procurement import ApprovalPolicy, OrgRole, Requisition
from app.models.procurement_schemas import ApprovalPolicyCreate
from app.services.procurement.errors import DomainError, InvalidState

# Default ladder thresholds, expressed in the requisition currency.
APPROVER_LIMIT = Decimal("5000")
FINANCE_LIMIT = Decimal("50000")


def default_roles_for(total: Decimal) -> list[OrgRole]:
    if total < APPROVER_LIMIT:
        return [OrgRole.APPROVER]
    if total < FINANCE_LIMIT:
        return [OrgRole.APPROVER, OrgRole.FINANCE]
    return [OrgRole.APPROVER, OrgRole.FINANCE, OrgRole.ORG_ADMIN]


def _bands_overlap(
    a_min: Decimal,
    a_max: Optional[Decimal],
    b_min: Decimal,
    b_max: Optional[Decimal],
) -> bool:
    if a_max is not None and b_min > a_max:
        return False
    if b_max is not None and a_min > b_max:
        return False
    return True


async def resolve_steps(
    db: AsyncSession, requisition: Requisition
) -> list[tuple[int, OrgRole, Optional[int]]]:
    """Return (step_order, required_role, policy_id) for this amount."""
    stmt = (
        select(ApprovalPolicy)
        .where(
            ApprovalPolicy.organization_id == requisition.organization_id,
            ApprovalPolicy.is_active.is_(True),
        )
        .order_by(ApprovalPolicy.step_order.asc(), ApprovalPolicy.min_amount.asc())
    )
    all_policies = list((await db.execute(stmt)).scalars().all())

    # No matrix at all: use the default ladder so a tenant is usable on day one.
    if not all_policies:
        return [
            (index, role, None)
            for index, role in enumerate(
                default_roles_for(requisition.total_amount), start=1
            )
        ]

    policies = [
        policy
        for policy in all_policies
        if policy.currency == requisition.currency
    ]
    # A configured matrix that does not cover this currency must not silently
    # fall back to the default ladder and bypass the org's controls.
    if not policies:
        raise DomainError(
            "No approval policy is configured for currency "
            f"{requisition.currency}; ask an organization admin to add one"
        )

    matched = [
        policy
        for policy in policies
        if policy.min_amount <= requisition.total_amount
        and (
            policy.max_amount is None
            or requisition.total_amount <= policy.max_amount
        )
    ]
    if not matched:
        raise DomainError(
            "No active approval policy covers this requisition amount; "
            "ask an organization admin to configure one"
        )

    steps: dict[int, tuple[int, OrgRole, Optional[int]]] = {}
    for policy in matched:
        if policy.step_order in steps:
            raise DomainError(
                "Approval policies overlap for this amount; "
                "ask an organization admin to fix the approval matrix"
            )
        steps[policy.step_order] = (
            policy.step_order,
            policy.required_role,
            policy.id,
        )

    return [steps[order] for order in sorted(steps)]


async def create_policy(
    db: AsyncSession, *, organization_id: int, payload: ApprovalPolicyCreate
) -> ApprovalPolicy:
    stmt = select(ApprovalPolicy).where(
        ApprovalPolicy.organization_id == organization_id,
        ApprovalPolicy.currency == payload.currency,
        ApprovalPolicy.step_order == payload.step_order,
        ApprovalPolicy.is_active.is_(True),
    )
    existing = list((await db.execute(stmt)).scalars().all())

    for policy in existing:
        if _bands_overlap(
            policy.min_amount,
            policy.max_amount,
            payload.min_amount,
            payload.max_amount,
        ):
            raise InvalidState(
                "This amount band overlaps an existing policy at "
                f"step {payload.step_order}"
            )

    policy = ApprovalPolicy(
        organization_id=organization_id,
        name=payload.name,
        min_amount=payload.min_amount,
        max_amount=payload.max_amount,
        currency=payload.currency,
        required_role=payload.required_role,
        step_order=payload.step_order,
        is_active=payload.is_active,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


async def list_policies(
    db: AsyncSession, *, organization_id: int
) -> list[ApprovalPolicy]:
    stmt = (
        select(ApprovalPolicy)
        .where(ApprovalPolicy.organization_id == organization_id)
        .order_by(
            ApprovalPolicy.step_order.asc(), ApprovalPolicy.min_amount.asc()
        )
    )
    return list((await db.execute(stmt)).scalars().all())
