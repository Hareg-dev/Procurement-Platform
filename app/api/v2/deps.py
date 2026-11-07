"""Tenant-scoped dependencies for the v2 API."""

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.dependencies import get_current_active_user
from app.core.db import get_db
from app.models.orm import User
from app.models.procurement import OrganizationMember, OrgRole


async def get_org_member(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMember:
    """Resolve the caller's membership in their organization (tenant)."""
    result = await db.execute(
        select(OrganizationMember)
        .options(selectinload(OrganizationMember.user))
        .where(
            OrganizationMember.organization_id == current_user.company_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.is_active.is_(True),
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active organization membership for this user",
        )
    return member


def require_org_roles(*roles: OrgRole):
    allowed = set(roles)

    def checker(
        member: OrganizationMember = Depends(get_org_member),
    ) -> OrganizationMember:
        if member.org_role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough organizational permissions",
            )
        return member

    return checker
