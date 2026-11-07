"""Request/response schemas for the v2 procurement domain.

Money is always ``Decimal`` (serialised as a string by Pydantic) so totals never
pass through binary floating point. ``RequisitionLineCreate`` accepts a unit
price, but line totals and requisition totals are always recomputed server-side.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.procurement import (
    ActorType,
    ApprovalStepStatus,
    OrgRole,
    RequisitionStatus,
)


class _CurrencyMixin(BaseModel):
    currency: str = Field(..., description="ISO 4217 code, e.g. USD")

    @field_validator("currency", mode="before")
    @classmethod
    def upper_currency(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        if len(value) != 3 or not value.isalpha():
            raise ValueError("currency must be a three-letter ISO 4217 code")
        return value


class RequisitionLineCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    quantity: Decimal = Field(..., gt=0, max_digits=18, decimal_places=4)
    unit_of_measure: str = Field(default="unit", min_length=1, max_length=20)
    unit_price: Decimal = Field(..., ge=0, max_digits=18, decimal_places=4)


class RequisitionCreate(_CurrencyMixin):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    cost_center: Optional[str] = Field(None, max_length=100)
    needed_by: Optional[date] = None
    lines: list[RequisitionLineCreate] = Field(..., min_length=1, max_length=200)


class RequisitionUpdate(BaseModel):
    version: int = Field(..., ge=1, description="Optimistic concurrency token")
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    cost_center: Optional[str] = Field(None, max_length=100)
    currency: Optional[str] = Field(None, description="ISO 4217 code, e.g. USD")
    needed_by: Optional[date] = None
    lines: Optional[list[RequisitionLineCreate]] = Field(
        None, min_length=1, max_length=200
    )

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("currency must be a three-letter ISO 4217 code")
        return value


class VersionedRequest(BaseModel):
    version: int = Field(..., ge=1, description="Optimistic concurrency token")


class CancelRequisitionRequest(VersionedRequest):
    reason: Optional[str] = Field(None, max_length=500)


class ApprovalDecisionRequest(VersionedRequest):
    decision: Literal["approve", "reject"]
    comment: Optional[str] = Field(None, max_length=1000)


class BudgetCreate(_CurrencyMixin):
    cost_center: str = Field(..., min_length=1, max_length=100)
    fiscal_year: int = Field(..., ge=2000, le=2100)
    amount: Decimal = Field(..., ge=0, max_digits=18, decimal_places=4)


class ApprovalPolicyCreate(_CurrencyMixin):
    name: str = Field(..., min_length=1, max_length=100)
    min_amount: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=18, decimal_places=4
    )
    max_amount: Optional[Decimal] = Field(
        None, gt=0, max_digits=18, decimal_places=4
    )
    required_role: OrgRole
    step_order: int = Field(default=1, ge=1, le=50)
    is_active: bool = True

    @field_validator("max_amount")
    @classmethod
    def validate_band(
        cls, value: Optional[Decimal], info
    ) -> Optional[Decimal]:
        min_amount = info.data.get("min_amount")
        if value is not None and min_amount is not None and value <= min_amount:
            raise ValueError("max_amount must be greater than min_amount")
        return value


class RequisitionLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    line_number: int
    description: str
    quantity: Decimal
    unit_of_measure: str
    unit_price: Decimal
    line_total: Decimal


class ApprovalStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step_order: int
    required_role: OrgRole
    status: ApprovalStepStatus
    decided_by_user_id: Optional[int] = None
    decided_at: Optional[datetime] = None
    comment: Optional[str] = None


class RequisitionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requisition_number: str
    title: str
    currency: str
    total_amount: Decimal
    status: RequisitionStatus
    needed_by: Optional[date] = None
    version: int
    created_at: datetime


class RequisitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    requisition_number: str
    title: str
    description: Optional[str] = None
    cost_center: Optional[str] = None
    currency: str
    total_amount: Decimal
    status: RequisitionStatus
    requested_by_user_id: int
    needed_by: Optional[date] = None
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    version: int
    created_at: datetime
    updated_at: datetime
    lines: list[RequisitionLineResponse] = Field(default_factory=list)
    approval_steps: list[ApprovalStepResponse] = Field(default_factory=list)


class PendingApprovalItem(BaseModel):
    step: ApprovalStepResponse
    requisition: RequisitionSummary
    requested_by_name: str


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    cost_center: str
    fiscal_year: int
    currency: str
    amount: Decimal
    committed_amount: Decimal
    available_amount: Decimal


class ApprovalPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    name: str
    min_amount: Decimal
    max_amount: Optional[Decimal] = None
    currency: str
    required_role: OrgRole
    step_order: int
    is_active: bool


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    actor_type: ActorType
    actor_user_id: Optional[int] = None
    actor_label: Optional[str] = None
    action: str
    entity_type: str
    entity_id: int
    before: Optional[dict] = None
    after: Optional[dict] = None
    correlation_id: Optional[str] = None
    created_at: datetime
