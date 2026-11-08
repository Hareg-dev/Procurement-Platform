"""
Sourcing v2: events with lots, invitations, Q&A, addenda and sealed bids.

An event belongs to the buying organization (``organization_id``) and is
always split into at least one lot; every requirement line belongs to a lot and
every bid is submitted per lot. That keeps the bid uniqueness rule simple
(one bid per supplier per lot) and matches how tenders are actually run.

Sealed-bid integrity is a data-access rule, not a prompt rule: bid amounts are
only exposed to the buying organization after ``opened_at`` is recorded.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.orm import BaseModel, Company, User, utcnow
from app.models.procurement import Requisition


class SourcingEventType(str, Enum):
    RFQ = "rfq"
    RFP = "rfp"
    TENDER = "tender"


class SourcingVisibility(str, Enum):
    PUBLIC = "public"
    INVITED = "invited"


class SourcingStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    OPENED = "opened"
    EVALUATING = "evaluating"
    AWARDED = "awarded"
    CANCELLED = "cancelled"


class InvitationStatus(str, Enum):
    INVITED = "invited"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class BidStatus(str, Enum):
    SUBMITTED = "submitted"
    WITHDRAWN = "withdrawn"
    DISQUALIFIED = "disqualified"


class SourcingEvent(BaseModel):
    """A tender / RFQ / RFP run by a buying organization."""

    __tablename__ = "sourcing_events"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "event_number", name="uq_sourcing_event_number"
        ),
        CheckConstraint("version >= 1", name="ck_sourcing_event_version"),
    )

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    requisition_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("requisitions.id"), nullable=True, index=True
    )
    event_number: Mapped[str] = mapped_column(String(40), nullable=False)
    event_type: Mapped[SourcingEventType] = mapped_column(
        SQLEnum(SourcingEventType),
        nullable=False,
        default=SourcingEventType.RFQ,
    )
    visibility: Mapped[SourcingVisibility] = mapped_column(
        SQLEnum(SourcingVisibility),
        nullable=False,
        default=SourcingVisibility.PUBLIC,
    )
    sealed_bids: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[SourcingStatus] = mapped_column(
        SQLEnum(SourcingStatus),
        nullable=False,
        default=SourcingStatus.DRAFT,
        index=True,
    )
    questions_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    closing_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    opened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    opened_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    requisition: Mapped[Optional[Requisition]] = relationship("Requisition")
    lots: Mapped[list["SourcingLot"]] = relationship(
        "SourcingLot",
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="SourcingLot.lot_number",
    )
    invitations: Mapped[list["SourcingInvitation"]] = relationship(
        "SourcingInvitation",
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="SourcingInvitation.id",
    )
    questions: Mapped[list["SourcingQuestion"]] = relationship(
        "SourcingQuestion",
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="SourcingQuestion.asked_at",
    )
    addenda: Mapped[list["SourcingAddendum"]] = relationship(
        "SourcingAddendum",
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="SourcingAddendum.addendum_number",
    )
    bids: Mapped[list["SourcingBid"]] = relationship(
        "SourcingBid",
        back_populates="event",
        cascade="all, delete-orphan",
    )


class SourcingLot(BaseModel):
    """A lot groups requirement lines and is bid on as a unit."""

    __tablename__ = "sourcing_lots"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "lot_number", name="uq_sourcing_lot_number"
        ),
        CheckConstraint("lot_number >= 1", name="ck_sourcing_lot_number"),
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey("sourcing_events.id"), nullable=False, index=True
    )
    lot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 4), nullable=True
    )

    event: Mapped[SourcingEvent] = relationship(
        "SourcingEvent", back_populates="lots"
    )
    lines: Mapped[list["SourcingLine"]] = relationship(
        "SourcingLine",
        back_populates="lot",
        cascade="all, delete-orphan",
        order_by="SourcingLine.line_number",
    )


class SourcingLine(BaseModel):
    """A requirement line that suppliers must price."""

    __tablename__ = "sourcing_lines"
    __table_args__ = (
        UniqueConstraint(
            "lot_id", "line_number", name="uq_sourcing_line_number"
        ),
        CheckConstraint("quantity > 0", name="ck_sourcing_line_quantity"),
        CheckConstraint(
            "target_unit_price IS NULL OR target_unit_price >= 0",
            name="ck_sourcing_line_target_price",
        ),
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey("sourcing_events.id"), nullable=False, index=True
    )
    lot_id: Mapped[int] = mapped_column(
        ForeignKey("sourcing_lots.id"), nullable=False, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unit"
    )
    target_unit_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 4), nullable=True
    )

    lot: Mapped[SourcingLot] = relationship(
        "SourcingLot", back_populates="lines"
    )


class SourcingInvitation(BaseModel):
    """Invitation for a supplier organization to participate."""

    __tablename__ = "sourcing_invitations"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "supplier_company_id", name="uq_sourcing_invitation"
        ),
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey("sourcing_events.id"), nullable=False, index=True
    )
    supplier_company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    status: Mapped[InvitationStatus] = mapped_column(
        SQLEnum(InvitationStatus),
        nullable=False,
        default=InvitationStatus.INVITED,
        index=True,
    )
    invited_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    responded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    event: Mapped[SourcingEvent] = relationship(
        "SourcingEvent", back_populates="invitations"
    )
    supplier_company: Mapped[Company] = relationship("Company")


class SourcingQuestion(BaseModel):
    """Clarification question and (optional) public answer."""

    __tablename__ = "sourcing_questions"

    event_id: Mapped[int] = mapped_column(
        ForeignKey("sourcing_events.id"), nullable=False, index=True
    )
    supplier_company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    asked_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    asked_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answered_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    answered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    event: Mapped[SourcingEvent] = relationship(
        "SourcingEvent", back_populates="questions"
    )


class SourcingAddendum(BaseModel):
    """Published clarification/addition, optionally extending the deadline."""

    __tablename__ = "sourcing_addenda"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "addendum_number", name="uq_sourcing_addendum"
        ),
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey("sourcing_events.id"), nullable=False, index=True
    )
    addendum_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    extended_closing_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    event: Mapped[SourcingEvent] = relationship(
        "SourcingEvent", back_populates="addenda"
    )


class SourcingBid(BaseModel):
    """A supplier's priced response for one lot of an event."""

    __tablename__ = "sourcing_bids"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "lot_id",
            "supplier_company_id",
            name="uq_sourcing_bid_per_lot",
        ),
        CheckConstraint("total_amount >= 0", name="ck_sourcing_bid_total"),
        CheckConstraint("version >= 1", name="ck_sourcing_bid_version"),
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey("sourcing_events.id"), nullable=False, index=True
    )
    lot_id: Mapped[int] = mapped_column(
        ForeignKey("sourcing_lots.id"), nullable=False, index=True
    )
    supplier_company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    submitted_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    status: Mapped[BidStatus] = mapped_column(
        SQLEnum(BidStatus),
        nullable=False,
        default=BidStatus.SUBMITTED,
        index=True,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    event: Mapped[SourcingEvent] = relationship(
        "SourcingEvent", back_populates="bids"
    )
    supplier_company: Mapped[Company] = relationship("Company")
    lines: Mapped[list["SourcingBidLine"]] = relationship(
        "SourcingBidLine",
        back_populates="bid",
        cascade="all, delete-orphan",
        order_by="SourcingBidLine.id",
    )


class SourcingBidLine(BaseModel):
    """Price quoted for one requirement line."""

    __tablename__ = "sourcing_bid_lines"
    __table_args__ = (
        UniqueConstraint(
            "bid_id", "sourcing_line_id", name="uq_sourcing_bid_line"
        ),
        CheckConstraint("quantity > 0", name="ck_sourcing_bid_line_quantity"),
        CheckConstraint(
            "unit_price >= 0", name="ck_sourcing_bid_line_unit_price"
        ),
        CheckConstraint("line_total >= 0", name="ck_sourcing_bid_line_total"),
    )

    bid_id: Mapped[int] = mapped_column(
        ForeignKey("sourcing_bids.id"), nullable=False, index=True
    )
    sourcing_line_id: Mapped[int] = mapped_column(
        ForeignKey("sourcing_lines.id"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    bid: Mapped[SourcingBid] = relationship(
        "SourcingBid", back_populates="lines"
    )
