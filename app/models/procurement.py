"""
Source-to-pay domain: tenants, requisitions, approvals, budgets and audit.

The marketplace ``Company`` row is the tenant root for this module. Existing
``User.company_id`` already binds a user to one company; ``OrganizationMember``
adds the *organizational role* a user holds inside that tenant (requester,
approver, buyer, finance, org admin), which is separate from the marketplace
persona stored in ``User.role`` (buyer/supplier/admin).
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
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

from app.core.db import Base
from app.models.orm import BaseModel, Company, User, utcnow


class OrgRole(str, Enum):
    """A user's role inside a tenant (buyer organization)."""

    REQUESTER = "requester"
    APPROVER = "approver"
    BUYER = "buyer"
    FINANCE = "finance"
    ORG_ADMIN = "org_admin"


class RequisitionStatus(str, Enum):
    DRAFT = "draft"
    IN_APPROVAL = "in_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalStepStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class ActorType(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class OrganizationMember(BaseModel):
    """Tenant membership and organizational role."""

    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    org_role: Mapped[OrgRole] = mapped_column(
        SQLEnum(OrgRole), nullable=False, default=OrgRole.REQUESTER
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    organization: Mapped[Company] = relationship("Company")
    user: Mapped[User] = relationship("User")


class Budget(BaseModel):
    """Committed spend allowance for a cost center in a fiscal year."""

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "cost_center",
            "fiscal_year",
            "currency",
            name="uq_budget_scope",
        ),
        CheckConstraint("amount >= 0", name="ck_budget_amount"),
        CheckConstraint("committed_amount >= 0", name="ck_budget_committed"),
        CheckConstraint(
            "committed_amount <= amount", name="ck_budget_within_amount"
        ),
    )

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    cost_center: Mapped[str] = mapped_column(String(100), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    committed_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )

    organization: Mapped[Company] = relationship("Company")

    @property
    def available_amount(self) -> Decimal:
        return self.amount - self.committed_amount


class Requisition(BaseModel):
    """A purchase request that must pass organizational approval."""

    __tablename__ = "requisitions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "requisition_number",
            name="uq_requisition_number",
        ),
        CheckConstraint("total_amount >= 0", name="ck_requisition_total"),
        CheckConstraint("version >= 1", name="ck_requisition_version"),
    )

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    requisition_number: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost_center: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    status: Mapped[RequisitionStatus] = mapped_column(
        SQLEnum(RequisitionStatus),
        nullable=False,
        default=RequisitionStatus.DRAFT,
        index=True,
    )
    requested_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    needed_by: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    # Optimistic concurrency token, bumped on every mutation.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    requested_by: Mapped[User] = relationship("User")
    lines: Mapped[list["RequisitionLine"]] = relationship(
        "RequisitionLine",
        back_populates="requisition",
        cascade="all, delete-orphan",
        order_by="RequisitionLine.line_number",
    )
    approval_steps: Mapped[list["ApprovalStep"]] = relationship(
        "ApprovalStep",
        back_populates="requisition",
        cascade="all, delete-orphan",
        order_by="ApprovalStep.step_order",
    )


class RequisitionLine(BaseModel):
    """A single requested item. Totals are always computed server-side."""

    __tablename__ = "requisition_lines"
    __table_args__ = (
        UniqueConstraint(
            "requisition_id", "line_number", name="uq_requisition_line"
        ),
        CheckConstraint("quantity > 0", name="ck_requisition_line_quantity"),
        CheckConstraint(
            "unit_price >= 0", name="ck_requisition_line_unit_price"
        ),
        CheckConstraint("line_total >= 0", name="ck_requisition_line_total"),
    )

    requisition_id: Mapped[int] = mapped_column(
        ForeignKey("requisitions.id"), nullable=False, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unit"
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    requisition: Mapped[Requisition] = relationship(
        "Requisition", back_populates="lines"
    )


class ApprovalPolicy(BaseModel):
    """An amount band that requires a given role at a given step."""

    __tablename__ = "approval_policies"
    __table_args__ = (
        CheckConstraint("min_amount >= 0", name="ck_policy_min_amount"),
        CheckConstraint(
            "max_amount IS NULL OR max_amount > min_amount",
            name="ck_policy_amount_band",
        ),
        CheckConstraint("step_order >= 1", name="ck_policy_step_order"),
    )

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    min_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    max_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    required_role: Mapped[OrgRole] = mapped_column(
        SQLEnum(OrgRole), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    organization: Mapped[Company] = relationship("Company")


class ApprovalStep(BaseModel):
    """A concrete approval task generated for a requisition."""

    __tablename__ = "approval_steps"
    __table_args__ = (
        UniqueConstraint(
            "requisition_id", "step_order", name="uq_approval_step_order"
        ),
    )

    requisition_id: Mapped[int] = mapped_column(
        ForeignKey("requisitions.id"), nullable=False, index=True
    )
    policy_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("approval_policies.id"), nullable=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    required_role: Mapped[OrgRole] = mapped_column(
        SQLEnum(OrgRole), nullable=False
    )
    status: Mapped[ApprovalStepStatus] = mapped_column(
        SQLEnum(ApprovalStepStatus),
        nullable=False,
        default=ApprovalStepStatus.PENDING,
        index=True,
    )
    decided_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    requisition: Mapped[Requisition] = relationship(
        "Requisition", back_populates="approval_steps"
    )
    decided_by: Mapped[Optional[User]] = relationship(
        "User", foreign_keys=[decided_by_user_id]
    )


class AuditEvent(Base):
    """Append-only record of every business action, including future agents."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    actor_type: Mapped[ActorType] = mapped_column(
        SQLEnum(ActorType), nullable=False, default=ActorType.USER
    )
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    # Denormalised label so the trail survives user deletion and names agents.
    actor_label: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # Physical names avoid the BEFORE/AFTER keywords on some engines.
    before: Mapped[Optional[dict]] = mapped_column(
        "before_state", JSON, nullable=True
    )
    after: Mapped[Optional[dict]] = mapped_column(
        "after_state", JSON, nullable=True
    )
    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )


class OutboxEvent(Base):
    """Transactional outbox row for reliable domain-event delivery."""

    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
