"""Shared authorization rules for buying and supplying organizations."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import User, UserRole, utcnow
from app.models.procurement import OrganizationMember, OrgRole
from app.models.sourcing import (
    InvitationStatus,
    SourcingEvent,
    SourcingInvitation,
    SourcingStatus,
    SourcingVisibility,
)
from app.services.procurement.errors import (
    InvalidState,
    NotFoundError,
    PermissionDenied,
)

BUYER_EVENT_ROLES = {OrgRole.BUYER, OrgRole.ORG_ADMIN}

# Statuses in which a supplier organization may see the event.
SUPPLIER_VISIBLE_STATUSES = {
    SourcingStatus.PUBLISHED,
    SourcingStatus.CLOSED,
    SourcingStatus.OPENED,
    SourcingStatus.EVALUATING,
    SourcingStatus.AWARDED,
}


def ensure_buyer_role(member: OrganizationMember) -> None:
    if member.org_role not in BUYER_EVENT_ROLES:
        raise PermissionDenied(
            "Only buyers or organization admins can manage sourcing events"
        )


def ensure_buying_org(
    member: OrganizationMember, event: SourcingEvent
) -> None:
    if event.organization_id != member.organization_id:
        # 404, not 403: do not reveal other tenants' events.
        raise NotFoundError("Sourcing event not found")


async def get_membership(
    db: AsyncSession, *, user_id: int, organization_id: int
) -> Optional[OrganizationMember]:
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def get_invitation(
    db: AsyncSession, *, event_id: int, supplier_company_id: int
) -> Optional[SourcingInvitation]:
    result = await db.execute(
        select(SourcingInvitation).where(
            SourcingInvitation.event_id == event_id,
            SourcingInvitation.supplier_company_id == supplier_company_id,
        )
    )
    return result.scalar_one_or_none()


def ensure_supplier_account(user: User) -> None:
    if user.role != UserRole.SUPPLIER:
        raise PermissionDenied(
            "Only supplier accounts can participate in sourcing events"
        )


async def ensure_supplier_can_view(
    db: AsyncSession, *, event: SourcingEvent, user: User
) -> Optional[SourcingInvitation]:
    ensure_supplier_account(user)

    if event.organization_id == user.company_id:
        raise PermissionDenied(
            "Your organization owns this sourcing event"
        )
    if event.status not in SUPPLIER_VISIBLE_STATUSES:
        raise NotFoundError("Sourcing event not found")

    invitation = await get_invitation(
        db, event_id=event.id, supplier_company_id=user.company_id
    )
    if event.visibility == SourcingVisibility.INVITED:
        if invitation is None:
            raise PermissionDenied(
                "Your organization was not invited to this event"
            )
        if invitation.status == InvitationStatus.DECLINED:
            raise PermissionDenied(
                "Your organization declined this invitation"
            )
    return invitation


def ensure_bidding_open(event: SourcingEvent) -> None:
    if event.status != SourcingStatus.PUBLISHED:
        raise InvalidState("Event is not open for bids")
    if event.closing_at <= utcnow():
        raise InvalidState("Bidding has closed for this event")


async def ensure_supplier_can_bid(
    db: AsyncSession, *, event: SourcingEvent, user: User
) -> Optional[SourcingInvitation]:
    invitation = await ensure_supplier_can_view(
        db, event=event, user=user
    )
    ensure_bidding_open(event)
    return invitation
