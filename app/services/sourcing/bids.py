"""Sealed bid submission, visibility and withdrawal."""

from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.domain import CompanyPublicResponse
from app.models.orm import User, utcnow
from app.models.sourcing import (
    BidStatus,
    SourcingBid,
    SourcingBidLine,
    SourcingStatus,
)
from app.models.sourcing_schemas import (
    BidLineResponse,
    BidResponse,
    BidSubmitRequest,
    BidWithdrawRequest,
)
from app.services.procurement import audit
from app.services.procurement.errors import (
    DomainError,
    InvalidState,
    NotFoundError,
    VersionConflict,
)
from app.services.procurement.money import compute_line_total, quantize_money
from app.services.sourcing.access import (
    ensure_supplier_account,
    ensure_supplier_can_bid,
    ensure_supplier_can_view,
    get_membership,
)
from app.services.sourcing.events import _require_event


def _to_response(bid: SourcingBid, *, sealed: bool) -> BidResponse:
    return BidResponse(
        id=bid.id,
        event_id=bid.event_id,
        lot_id=bid.lot_id,
        supplier_company_id=bid.supplier_company_id,
        supplier_company=CompanyPublicResponse.model_validate(
            bid.supplier_company
        ),
        status=bid.status,
        currency=bid.currency,
        sealed=sealed,
        total_amount=None if sealed else bid.total_amount,
        version=bid.version,
        submitted_at=bid.submitted_at,
        withdrawn_at=bid.withdrawn_at,
        lines=(
            []
            if sealed
            else [
                BidLineResponse.model_validate(line) for line in bid.lines
            ]
        ),
    )


async def _load_bid(
    db: AsyncSession, bid_id: int, *, with_lines: bool = True
) -> Optional[SourcingBid]:
    options = [selectinload(SourcingBid.supplier_company)]
    if with_lines:
        options.append(selectinload(SourcingBid.lines))
    stmt = (
        select(SourcingBid)
        .where(SourcingBid.id == bid_id)
        .options(*options)
        .execution_options(populate_existing=True)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _load_bids(
    db: AsyncSession,
    *,
    event_id: int,
    lot_id: Optional[int] = None,
    supplier_company_id: Optional[int] = None,
    with_lines: bool,
) -> list[SourcingBid]:
    options = [selectinload(SourcingBid.supplier_company)]
    if with_lines:
        options.append(selectinload(SourcingBid.lines))

    stmt = (
        select(SourcingBid)
        .where(SourcingBid.event_id == event_id)
        .options(*options)
        .order_by(SourcingBid.submitted_at.asc())
    )
    if lot_id is not None:
        stmt = stmt.where(SourcingBid.lot_id == lot_id)
    if supplier_company_id is not None:
        stmt = stmt.where(
            SourcingBid.supplier_company_id == supplier_company_id
        )
    return list((await db.execute(stmt)).scalars().all())


class SourcingBidService:
    async def submit(
        self,
        db: AsyncSession,
        *,
        user: User,
        event_id: int,
        lot_id: int,
        payload: BidSubmitRequest,
    ) -> BidResponse:
        event = await _require_event(db, event_id)
        await ensure_supplier_can_bid(db, event=event, user=user)

        lot = next((lot for lot in event.lots if lot.id == lot_id), None)
        if lot is None:
            raise NotFoundError("Lot not found")

        lot_lines = {line.id: line for line in lot.lines}
        if not lot_lines:
            raise DomainError("This lot has no requirement lines")

        quoted: dict[int, object] = {}
        for line_in in payload.lines:
            if line_in.sourcing_line_id not in lot_lines:
                raise DomainError(
                    f"Line {line_in.sourcing_line_id} does not belong to "
                    f"lot {lot.lot_number}"
                )
            if line_in.sourcing_line_id in quoted:
                raise DomainError(
                    f"Line {line_in.sourcing_line_id} was quoted twice"
                )
            quoted[line_in.sourcing_line_id] = line_in

        missing = set(lot_lines) - set(quoted)
        if missing:
            raise DomainError(
                "Every line in the lot must be priced; missing line ids: "
                f"{sorted(missing)}"
            )

        result = await db.execute(
            select(SourcingBid)
            .where(
                SourcingBid.event_id == event.id,
                SourcingBid.lot_id == lot.id,
                SourcingBid.supplier_company_id == user.company_id,
            )
            .options(selectinload(SourcingBid.lines))
        )
        existing = result.scalar_one_or_none()

        if existing is not None and existing.status == BidStatus.SUBMITTED:
            raise InvalidState(
                "Your organization already submitted a bid for this lot"
            )
        if existing is not None and existing.status != BidStatus.WITHDRAWN:
            raise InvalidState("This bid can no longer be resubmitted")

        if existing is None:
            bid = SourcingBid(
                event_id=event.id,
                lot_id=lot.id,
                supplier_company_id=user.company_id,
                submitted_by_user_id=user.id,
                status=BidStatus.SUBMITTED,
                currency=event.currency,
                total_amount=Decimal("0"),
                submitted_at=utcnow(),
                version=1,
            )
            db.add(bid)
        else:
            bid = existing
            # Flush the old line deletes before re-inserting the same line ids.
            bid.lines.clear()
            await db.flush()
            bid.status = BidStatus.SUBMITTED
            bid.submitted_by_user_id = user.id
            bid.currency = event.currency
            bid.submitted_at = utcnow()
            bid.withdrawn_at = None
            bid.version += 1

        total = Decimal("0")
        for line_in in payload.lines:
            requirement = lot_lines[line_in.sourcing_line_id]
            line_total = compute_line_total(
                requirement.quantity, line_in.unit_price
            )
            bid.lines.append(
                SourcingBidLine(
                    sourcing_line_id=requirement.id,
                    quantity=requirement.quantity,
                    unit_price=line_in.unit_price,
                    line_total=line_total,
                    note=line_in.note,
                )
            )
            total += line_total
        bid.total_amount = quantize_money(total)
        await db.flush()

        # Never put prices in the audit/outbox payload: both are readable by
        # the buying organization before a sealed event is opened.
        audit.record_audit(
            db,
            organization_id=event.organization_id,
            actor=user,
            action="sourcing.bid_submitted",
            entity_type="sourcing_bid",
            entity_id=bid.id,
            after={
                "event_id": event.id,
                "lot_id": lot.id,
                "supplier_company_id": user.company_id,
                "status": BidStatus.SUBMITTED.value,
            },
        )
        audit.emit_event(
            db,
            organization_id=event.organization_id,
            event_type="sourcing.bid_submitted",
            aggregate_type="sourcing_event",
            aggregate_id=event.id,
            payload={
                "event_id": event.id,
                "lot_id": lot.id,
                "supplier_company_id": user.company_id,
            },
        )
        await db.commit()

        stored = await _load_bid(db, bid.id)
        if stored is None:
            raise NotFoundError("Bid not found after submission")
        return _to_response(stored, sealed=False)

    async def list_for_user(
        self,
        db: AsyncSession,
        *,
        user: User,
        event_id: int,
        lot_id: Optional[int] = None,
    ) -> list[BidResponse]:
        event = await _require_event(db, event_id)

        membership = await get_membership(
            db, user_id=user.id, organization_id=event.organization_id
        )
        if membership is not None:
            visible = (
                not event.sealed_bids or event.opened_at is not None
            )
            bids = await _load_bids(
                db,
                event_id=event.id,
                lot_id=lot_id,
                with_lines=visible,
            )
            return [
                _to_response(bid, sealed=not visible) for bid in bids
            ]

        await ensure_supplier_can_view(db, event=event, user=user)
        bids = await _load_bids(
            db,
            event_id=event.id,
            lot_id=lot_id,
            supplier_company_id=user.company_id,
            with_lines=True,
        )
        return [_to_response(bid, sealed=False) for bid in bids]

    async def withdraw(
        self,
        db: AsyncSession,
        *,
        user: User,
        event_id: int,
        bid_id: int,
        payload: BidWithdrawRequest,
    ) -> BidResponse:
        ensure_supplier_account(user)

        bid = await _load_bid(db, bid_id)
        if (
            bid is None
            or bid.event_id != event_id
            or bid.supplier_company_id != user.company_id
        ):
            raise NotFoundError("Bid not found")
        if bid.status != BidStatus.SUBMITTED:
            raise InvalidState("Only a submitted bid can be withdrawn")
        if bid.version != payload.version:
            raise VersionConflict(
                "Bid was modified by someone else; reload and retry"
            )

        event = await _require_event(db, event_id)
        if event.status != SourcingStatus.PUBLISHED:
            raise InvalidState("Bids can only be withdrawn while bidding is open")
        if event.closing_at <= utcnow():
            raise InvalidState("Bidding has closed for this event")

        bid.status = BidStatus.WITHDRAWN
        bid.withdrawn_at = utcnow()
        bid.version += 1

        audit.record_audit(
            db,
            organization_id=event.organization_id,
            actor=user,
            action="sourcing.bid_withdrawn",
            entity_type="sourcing_bid",
            entity_id=bid.id,
            after={
                "event_id": event.id,
                "lot_id": bid.lot_id,
                "status": BidStatus.WITHDRAWN.value,
            },
        )
        audit.emit_event(
            db,
            organization_id=event.organization_id,
            event_type="sourcing.bid_withdrawn",
            aggregate_type="sourcing_event",
            aggregate_id=event.id,
            payload={
                "event_id": event.id,
                "lot_id": bid.lot_id,
                "supplier_company_id": user.company_id,
            },
        )
        await db.commit()

        stored = await _load_bid(db, bid.id)
        if stored is None:
            raise NotFoundError("Bid not found after withdrawal")
        return _to_response(stored, sealed=False)


sourcing_bid_service = SourcingBidService()
