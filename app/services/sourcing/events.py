"""Sourcing event lifecycle, invitations and supplier discovery."""

from typing import Optional
from uuid import uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.orm import Company, User, UserRole, utcnow
from app.models.procurement import (
    OrganizationMember,
    Requisition,
    RequisitionStatus,
)
from app.models.sourcing import (
    InvitationStatus,
    SourcingEvent,
    SourcingInvitation,
    SourcingLine,
    SourcingLot,
    SourcingStatus,
    SourcingVisibility,
)
from app.models.sourcing_schemas import (
    InvitationRespondRequest,
    SourcingEventCreate,
    SourcingEventUpdate,
    SourcingLotInput,
    SourcingLotsReplace,
)
from app.services.procurement import audit
from app.services.procurement.errors import (
    DomainError,
    InvalidState,
    NotFoundError,
    VersionConflict,
)
from app.services.sourcing.access import (
    ensure_buyer_role,
    ensure_buying_org,
    ensure_supplier_account,
    ensure_supplier_can_view,
    get_membership,
)
from app.services.sourcing.state import ensure_transition


def _snapshot(event: SourcingEvent) -> dict:
    return {
        "event_number": event.event_number,
        "status": event.status,
        "title": event.title,
        "visibility": event.visibility,
        "sealed_bids": event.sealed_bids,
        "currency": event.currency,
        "closing_at": event.closing_at,
        "version": event.version,
    }


async def _insert_lots(
    db: AsyncSession, event_id: int, lots_in: list[SourcingLotInput]
) -> None:
    """Insert lots and lines directly.

    Do not build them through ``event.lots``: after the event's first flush the
    collection is unloaded, and touching it from sync code triggers an async
    lazy load (MissingGreenlet). Flushing the lots first also gives the lines a
    concrete lot id without a relationship round-trip.
    """
    lots = [
        SourcingLot(
            event_id=event_id,
            lot_number=index,
            title=lot_in.title,
            description=lot_in.description,
            estimated_amount=lot_in.estimated_amount,
        )
        for index, lot_in in enumerate(lots_in, start=1)
    ]
    db.add_all(lots)
    await db.flush()

    lines = [
        SourcingLine(
            event_id=event_id,
            lot_id=lot.id,
            line_number=index,
            description=line_in.description,
            quantity=line_in.quantity,
            unit_of_measure=line_in.unit_of_measure,
            target_unit_price=line_in.target_unit_price,
        )
        for lot, lot_in in zip(lots, lots_in)
        for index, line_in in enumerate(lot_in.lines, start=1)
    ]
    db.add_all(lines)
    await db.flush()


async def _load_event(
    db: AsyncSession, event_id: int, *, lock: bool = False
) -> Optional[SourcingEvent]:
    stmt = (
        select(SourcingEvent)
        .where(SourcingEvent.id == event_id)
        .options(
            selectinload(SourcingEvent.lots).selectinload(
                SourcingLot.lines
            )
        )
        .execution_options(populate_existing=True)
    )
    if lock:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def _require_event(
    db: AsyncSession, event_id: int, *, lock: bool = False
) -> SourcingEvent:
    event = await _load_event(db, event_id, lock=lock)
    if event is None:
        raise NotFoundError("Sourcing event not found")
    return event


def _validate_timeline(event: SourcingEvent) -> None:
    if event.closing_at <= utcnow():
        raise DomainError("closing_at must be in the future")
    if (
        event.questions_deadline is not None
        and event.questions_deadline >= event.closing_at
    ):
        raise DomainError("questions_deadline must be before closing_at")


async def _validate_requisition(
    db: AsyncSession,
    member: OrganizationMember,
    requisition_id: Optional[int],
) -> None:
    if requisition_id is None:
        return
    requisition = await db.get(Requisition, requisition_id)
    if (
        requisition is None
        or requisition.organization_id != member.organization_id
    ):
        raise NotFoundError("Requisition not found")
    if requisition.status != RequisitionStatus.APPROVED:
        raise InvalidState(
            "Sourcing can only start from an approved requisition"
        )


class SourcingEventService:
    async def create(
        self,
        db: AsyncSession,
        *,
        member: OrganizationMember,
        creator: User,
        payload: SourcingEventCreate,
    ) -> SourcingEvent:
        ensure_buyer_role(member)
        await _validate_requisition(db, member, payload.requisition_id)

        if payload.closing_at <= utcnow():
            raise DomainError("closing_at must be in the future")

        event = SourcingEvent(
            organization_id=member.organization_id,
            requisition_id=payload.requisition_id,
            event_number=f"TMP-{uuid4().hex}",
            event_type=payload.event_type,
            visibility=payload.visibility,
            sealed_bids=payload.sealed_bids,
            title=payload.title,
            description=payload.description,
            category=payload.category,
            currency=payload.currency,
            status=SourcingStatus.DRAFT,
            questions_deadline=payload.questions_deadline,
            closing_at=payload.closing_at,
            created_by_user_id=creator.id,
            version=1,
        )
        db.add(event)
        await db.flush()

        event.event_number = f"SRC-{utcnow().year}-{event.id:06d}"
        await _insert_lots(db, event.id, payload.lots)

        audit.record_audit(
            db,
            organization_id=member.organization_id,
            actor=creator,
            action="sourcing.created",
            entity_type="sourcing_event",
            entity_id=event.id,
            after=_snapshot(event),
        )
        await db.commit()

        return await _require_event(db, event.id)

    async def list_for_org(
        self,
        db: AsyncSession,
        *,
        organization_id: int,
        status: Optional[SourcingStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SourcingEvent]:
        stmt = select(SourcingEvent).where(
            SourcingEvent.organization_id == organization_id
        )
        if status is not None:
            stmt = stmt.where(SourcingEvent.status == status)
        stmt = (
            stmt.order_by(SourcingEvent.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def list_opportunities(
        self,
        db: AsyncSession,
        *,
        user: User,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SourcingEvent]:
        ensure_supplier_account(user)
        now = utcnow()

        stmt = (
            select(SourcingEvent)
            .outerjoin(
                SourcingInvitation,
                and_(
                    SourcingInvitation.event_id == SourcingEvent.id,
                    SourcingInvitation.supplier_company_id
                    == user.company_id,
                ),
            )
            .where(
                SourcingEvent.status == SourcingStatus.PUBLISHED,
                SourcingEvent.closing_at > now,
                or_(
                    SourcingEvent.visibility == SourcingVisibility.PUBLIC,
                    and_(
                        SourcingInvitation.id.is_not(None),
                        SourcingInvitation.status
                        != InvitationStatus.DECLINED,
                    ),
                ),
            )
            .order_by(SourcingEvent.closing_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def get_for_user(
        self, db: AsyncSession, *, user: User, event_id: int
    ) -> SourcingEvent:
        event = await _require_event(db, event_id)

        membership = await get_membership(
            db, user_id=user.id, organization_id=event.organization_id
        )
        if membership is not None:
            return event

        await ensure_supplier_can_view(db, event=event, user=user)
        return event

    async def update(
        self,
        db: AsyncSession,
        *,
        member: OrganizationMember,
        event_id: int,
        payload: SourcingEventUpdate,
    ) -> SourcingEvent:
        ensure_buyer_role(member)
        event = await _require_event(db, event_id, lock=True)
        ensure_buying_org(member, event)

        if event.status != SourcingStatus.DRAFT:
            raise InvalidState("Only draft events can be edited")
        if event.version != payload.version:
            raise VersionConflict(
                "Sourcing event was modified by someone else; reload and retry"
            )

        before = _snapshot(event)
        changes = payload.model_dump(
            exclude_unset=True, exclude={"version"}
        )
        for field, value in changes.items():
            setattr(event, field, value)

        _validate_timeline(event)
        event.version += 1

        audit.record_audit(
            db,
            organization_id=member.organization_id,
            actor=member.user,
            action="sourcing.updated",
            entity_type="sourcing_event",
            entity_id=event.id,
            before=before,
            after=_snapshot(event),
        )
        await db.commit()

        return await _require_event(db, event.id)

    async def replace_lots(
        self,
        db: AsyncSession,
        *,
        member: OrganizationMember,
        event_id: int,
        payload: SourcingLotsReplace,
    ) -> SourcingEvent:
        ensure_buyer_role(member)
        event = await _require_event(db, event_id, lock=True)
        ensure_buying_org(member, event)

        if event.status != SourcingStatus.DRAFT:
            raise InvalidState("Only draft events can be edited")
        if event.version != payload.version:
            raise VersionConflict(
                "Sourcing event was modified by someone else; reload and retry"
            )

        before = _snapshot(event)
        before["lot_count"] = len(event.lots)

        # Flush the orphan deletes before re-inserting lot/line numbers.
        event.lots.clear()
        await db.flush()
        await _insert_lots(db, event.id, payload.lots)
        event.version += 1

        after = _snapshot(event)
        after["lot_count"] = len(payload.lots)

        audit.record_audit(
            db,
            organization_id=member.organization_id,
            actor=member.user,
            action="sourcing.lots_replaced",
            entity_type="sourcing_event",
            entity_id=event.id,
            before=before,
            after=after,
        )
        await db.commit()

        return await _require_event(db, event.id)

    async def publish(
        self,
        db: AsyncSession,
        *,
        member: OrganizationMember,
        event_id: int,
        version: int,
    ) -> SourcingEvent:
        ensure_buyer_role(member)
        event = await _require_event(db, event_id, lock=True)
        ensure_buying_org(member, event)

        if event.version != version:
            raise VersionConflict(
                "Sourcing event was modified by someone else; reload and retry"
            )
        ensure_transition(event.status, SourcingStatus.PUBLISHED)

        if event.closing_at <= utcnow():
            raise DomainError("Cannot publish an event whose deadline has passed")
        if not event.lots:
            raise DomainError("A sourcing event needs at least one lot")
        for lot in event.lots:
            if not lot.lines:
                raise DomainError(
                    f"Lot {lot.lot_number} has no requirement lines"
                )

        await _validate_requisition(db, member, event.requisition_id)

        if event.visibility == SourcingVisibility.INVITED:
            invitation_count = await db.scalar(
                select(func.count())
                .select_from(SourcingInvitation)
                .where(SourcingInvitation.event_id == event.id)
            )
            if not invitation_count:
                raise DomainError(
                    "Add at least one supplier invitation before publishing "
                    "an invited event"
                )

        before = _snapshot(event)
        event.status = SourcingStatus.PUBLISHED
        event.published_at = utcnow()
        event.version += 1

        audit.record_audit(
            db,
            organization_id=member.organization_id,
            actor=member.user,
            action="sourcing.published",
            entity_type="sourcing_event",
            entity_id=event.id,
            before=before,
            after=_snapshot(event),
        )
        audit.emit_event(
            db,
            organization_id=member.organization_id,
            event_type="sourcing.published",
            aggregate_type="sourcing_event",
            aggregate_id=event.id,
            payload={
                "event_number": event.event_number,
                "visibility": event.visibility.value,
                "closing_at": event.closing_at,
            },
        )
        await db.commit()

        return await _require_event(db, event.id)

    async def close(
        self,
        db: AsyncSession,
        *,
        member: OrganizationMember,
        event_id: int,
        version: int,
    ) -> SourcingEvent:
        ensure_buyer_role(member)
        event = await _require_event(db, event_id, lock=True)
        ensure_buying_org(member, event)

        if event.version != version:
            raise VersionConflict(
                "Sourcing event was modified by someone else; reload and retry"
            )
        ensure_transition(event.status, SourcingStatus.CLOSED)

        before = _snapshot(event)
        event.status = SourcingStatus.CLOSED
        event.closed_at = utcnow()
        event.version += 1

        audit.record_audit(
            db,
            organization_id=member.organization_id,
            actor=member.user,
            action="sourcing.closed",
            entity_type="sourcing_event",
            entity_id=event.id,
            before=before,
            after=_snapshot(event),
        )
        audit.emit_event(
            db,
            organization_id=member.organization_id,
            event_type="sourcing.closed",
            aggregate_type="sourcing_event",
            aggregate_id=event.id,
            payload={"event_number": event.event_number},
        )
        await db.commit()

        return await _require_event(db, event.id)

    async def open(
        self,
        db: AsyncSession,
        *,
        member: OrganizationMember,
        event_id: int,
        version: int,
    ) -> SourcingEvent:
        ensure_buyer_role(member)
        event = await _require_event(db, event_id, lock=True)
        ensure_buying_org(member, event)

        if event.version != version:
            raise VersionConflict(
                "Sourcing event was modified by someone else; reload and retry"
            )
        ensure_transition(event.status, SourcingStatus.OPENED)

        before = _snapshot(event)
        event.status = SourcingStatus.OPENED
        event.opened_at = utcnow()
        event.opened_by_user_id = member.user_id
        event.version += 1

        audit.record_audit(
            db,
            organization_id=member.organization_id,
            actor=member.user,
            action="sourcing.opened",
            entity_type="sourcing_event",
            entity_id=event.id,
            before=before,
            after=_snapshot(event),
        )
        audit.emit_event(
            db,
            organization_id=member.organization_id,
            event_type="sourcing.opened",
            aggregate_type="sourcing_event",
            aggregate_id=event.id,
            payload={"event_number": event.event_number},
        )
        await db.commit()

        return await _require_event(db, event.id)

    async def cancel(
        self,
        db: AsyncSession,
        *,
        member: OrganizationMember,
        event_id: int,
        version: int,
    ) -> SourcingEvent:
        ensure_buyer_role(member)
        event = await _require_event(db, event_id, lock=True)
        ensure_buying_org(member, event)

        if event.version != version:
            raise VersionConflict(
                "Sourcing event was modified by someone else; reload and retry"
            )
        ensure_transition(event.status, SourcingStatus.CANCELLED)

        before = _snapshot(event)
        event.status = SourcingStatus.CANCELLED
        event.cancelled_at = utcnow()
        event.version += 1

        audit.record_audit(
            db,
            organization_id=member.organization_id,
            actor=member.user,
            action="sourcing.cancelled",
            entity_type="sourcing_event",
            entity_id=event.id,
            before=before,
            after=_snapshot(event),
        )
        audit.emit_event(
            db,
            organization_id=member.organization_id,
            event_type="sourcing.cancelled",
            aggregate_type="sourcing_event",
            aggregate_id=event.id,
            payload={"event_number": event.event_number},
        )
        await db.commit()

        return await _require_event(db, event.id)

    async def invite(
        self,
        db: AsyncSession,
        *,
        member: OrganizationMember,
        event_id: int,
        supplier_company_ids: list[int],
    ) -> list[SourcingInvitation]:
        ensure_buyer_role(member)
        event = await _require_event(db, event_id)
        ensure_buying_org(member, event)

        if event.status not in {
            SourcingStatus.DRAFT,
            SourcingStatus.PUBLISHED,
        }:
            raise InvalidState(
                "Invitations can only be added before the event is closed"
            )
        if event.closing_at <= utcnow():
            raise DomainError("This event's deadline has passed")

        wanted = sorted(set(supplier_company_ids))
        if member.organization_id in wanted:
            raise DomainError("You cannot invite your own organization")

        companies = {
            company_id
            for (company_id,) in (
                await db.execute(
                    select(Company.id).where(Company.id.in_(wanted))
                )
            ).all()
        }
        missing = [company_id for company_id in wanted if company_id not in companies]
        if missing:
            raise NotFoundError(
                f"Unknown supplier organization(s): {missing}"
            )

        supplier_companies = {
            company_id
            for (company_id,) in (
                await db.execute(
                    select(User.company_id)
                    .where(
                        User.company_id.in_(wanted),
                        User.role == UserRole.SUPPLIER,
                        User.is_active.is_(True),
                    )
                    .distinct()
                )
            ).all()
        }
        not_suppliers = [
            company_id
            for company_id in wanted
            if company_id not in supplier_companies
        ]
        if not_suppliers:
            raise DomainError(
                "These organizations have no active supplier account: "
                f"{not_suppliers}"
            )

        existing = {
            invitation.supplier_company_id
            for invitation in (
                await db.execute(
                    select(SourcingInvitation).where(
                        SourcingInvitation.event_id == event.id,
                        SourcingInvitation.supplier_company_id.in_(wanted),
                    )
                )
            ).scalars().all()
        }

        created = []
        for company_id in wanted:
            if company_id in existing:
                continue
            invitation = SourcingInvitation(
                event_id=event.id,
                supplier_company_id=company_id,
                status=InvitationStatus.INVITED,
                invited_by_user_id=member.user_id,
            )
            db.add(invitation)
            created.append(invitation)

        audit.record_audit(
            db,
            organization_id=member.organization_id,
            actor=member.user,
            action="sourcing.invitations_sent",
            entity_type="sourcing_event",
            entity_id=event.id,
            after={"supplier_company_ids": wanted},
        )
        await db.commit()

        result = await db.execute(
            select(SourcingInvitation)
            .where(SourcingInvitation.event_id == event.id)
            .options(selectinload(SourcingInvitation.supplier_company))
            .order_by(SourcingInvitation.id.asc())
        )
        return list(result.scalars().all())

    async def list_invitations(
        self,
        db: AsyncSession,
        *,
        member: OrganizationMember,
        event_id: int,
    ) -> list[SourcingInvitation]:
        event = await _require_event(db, event_id)
        ensure_buying_org(member, event)

        result = await db.execute(
            select(SourcingInvitation)
            .where(SourcingInvitation.event_id == event.id)
            .options(selectinload(SourcingInvitation.supplier_company))
            .order_by(SourcingInvitation.id.asc())
        )
        return list(result.scalars().all())

    async def respond_to_invitation(
        self,
        db: AsyncSession,
        *,
        user: User,
        event_id: int,
        invitation_id: int,
        payload: InvitationRespondRequest,
    ) -> SourcingInvitation:
        ensure_supplier_account(user)

        result = await db.execute(
            select(SourcingInvitation)
            .where(
                SourcingInvitation.id == invitation_id,
                SourcingInvitation.event_id == event_id,
            )
            .options(selectinload(SourcingInvitation.supplier_company))
        )
        invitation = result.scalar_one_or_none()
        if invitation is None:
            raise NotFoundError("Invitation not found")
        if invitation.supplier_company_id != user.company_id:
            raise NotFoundError("Invitation not found")

        event = await _require_event(db, event_id)
        if event.status != SourcingStatus.PUBLISHED:
            raise InvalidState("This event is no longer accepting responses")
        if event.closing_at <= utcnow():
            raise InvalidState("This event's deadline has passed")
        if invitation.status != InvitationStatus.INVITED:
            raise InvalidState("This invitation has already been answered")

        invitation.status = (
            InvitationStatus.ACCEPTED
            if payload.decision == "accept"
            else InvitationStatus.DECLINED
        )
        invitation.responded_at = utcnow()

        audit.record_audit(
            db,
            organization_id=event.organization_id,
            actor=user,
            action=f"sourcing.invitation_{payload.decision}ed",
            entity_type="sourcing_invitation",
            entity_id=invitation.id,
            after={
                "event_id": event.id,
                "supplier_company_id": user.company_id,
            },
        )
        await db.commit()

        result = await db.execute(
            select(SourcingInvitation)
            .where(SourcingInvitation.id == invitation.id)
            .options(selectinload(SourcingInvitation.supplier_company))
        )
        return result.scalar_one()


sourcing_event_service = SourcingEventService()
