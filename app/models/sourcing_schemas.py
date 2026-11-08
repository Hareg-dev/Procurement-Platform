"""Request/response schemas for the sourcing (tender) API."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.domain import CompanyPublicResponse
from app.models.sourcing import (
    BidStatus,
    InvitationStatus,
    SourcingEventType,
    SourcingStatus,
    SourcingVisibility,
)


def _naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is not None and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _currency(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    value = value.strip().upper()
    if len(value) != 3 or not value.isalpha():
        raise ValueError("currency must be a three-letter ISO 4217 code")
    return value


class SourcingLineInput(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    quantity: Decimal = Field(..., gt=0, max_digits=18, decimal_places=4)
    unit_of_measure: str = Field(default="unit", min_length=1, max_length=20)
    target_unit_price: Optional[Decimal] = Field(
        None, ge=0, max_digits=18, decimal_places=4
    )


class SourcingLotInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    estimated_amount: Optional[Decimal] = Field(
        None, ge=0, max_digits=18, decimal_places=4
    )
    lines: list[SourcingLineInput] = Field(..., min_length=1, max_length=200)


class SourcingEventCreate(BaseModel):
    requisition_id: Optional[int] = None
    event_type: SourcingEventType = SourcingEventType.RFQ
    visibility: SourcingVisibility = SourcingVisibility.PUBLIC
    sealed_bids: bool = True
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=10000)
    category: Optional[str] = Field(None, max_length=100)
    currency: str = Field(..., description="ISO 4217 code, e.g. USD")
    questions_deadline: Optional[datetime] = None
    closing_at: datetime
    lots: list[SourcingLotInput] = Field(..., min_length=1, max_length=50)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return _currency(value) or value

    @field_validator("closing_at", "questions_deadline")
    @classmethod
    def normalize_dates(
        cls, value: Optional[datetime]
    ) -> Optional[datetime]:
        return _naive_utc(value)

    @model_validator(mode="after")
    def validate_timeline(self):
        if self.questions_deadline is not None:
            if self.questions_deadline >= self.closing_at:
                raise ValueError(
                    "questions_deadline must be before closing_at"
                )
        return self


class SourcingEventUpdate(BaseModel):
    version: int = Field(..., ge=1)
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=10000)
    category: Optional[str] = Field(None, max_length=100)
    visibility: Optional[SourcingVisibility] = None
    sealed_bids: Optional[bool] = None
    currency: Optional[str] = None
    questions_deadline: Optional[datetime] = None
    closing_at: Optional[datetime] = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: Optional[str]) -> Optional[str]:
        return _currency(value)

    @field_validator("closing_at", "questions_deadline")
    @classmethod
    def normalize_dates(
        cls, value: Optional[datetime]
    ) -> Optional[datetime]:
        return _naive_utc(value)


class SourcingLotsReplace(BaseModel):
    version: int = Field(..., ge=1)
    lots: list[SourcingLotInput] = Field(..., min_length=1, max_length=50)


class SourcingLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    line_number: int
    description: str
    quantity: Decimal
    unit_of_measure: str
    target_unit_price: Optional[Decimal] = None


class SourcingLotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lot_number: int
    title: str
    description: Optional[str] = None
    estimated_amount: Optional[Decimal] = None
    lines: list[SourcingLineResponse] = Field(default_factory=list)


class SourcingEventSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_number: str
    event_type: SourcingEventType
    visibility: SourcingVisibility
    sealed_bids: bool
    title: str
    currency: str
    status: SourcingStatus
    closing_at: datetime
    published_at: Optional[datetime] = None
    version: int


class SourcingEventResponse(SourcingEventSummary):
    organization_id: int
    requisition_id: Optional[int] = None
    description: Optional[str] = None
    category: Optional[str] = None
    questions_deadline: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime
    lots: list[SourcingLotResponse] = Field(default_factory=list)


class InvitationBatchCreate(BaseModel):
    supplier_company_ids: list[int] = Field(..., min_length=1, max_length=100)


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_company_id: int
    supplier_company: CompanyPublicResponse
    status: InvitationStatus
    responded_at: Optional[datetime] = None


class InvitationRespondRequest(BaseModel):
    decision: Literal["accept", "decline"]


class QuestionCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=5000)
    is_public: bool = True


class QuestionAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1, max_length=5000)
    is_public: bool = True


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    supplier_company_id: int
    asked_by_user_id: int
    question: str
    asked_at: datetime
    answer: Optional[str] = None
    answered_by_user_id: Optional[int] = None
    answered_at: Optional[datetime] = None
    is_public: bool


class AddendumCreate(BaseModel):
    version: int = Field(..., ge=1)
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=20000)
    extended_closing_at: Optional[datetime] = None

    @field_validator("extended_closing_at")
    @classmethod
    def normalize_date(
        cls, value: Optional[datetime]
    ) -> Optional[datetime]:
        return _naive_utc(value)


class AddendumResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    addendum_number: int
    title: str
    body: str
    published_at: datetime
    extended_closing_at: Optional[datetime] = None


class BidLineInput(BaseModel):
    sourcing_line_id: int
    unit_price: Decimal = Field(..., ge=0, max_digits=18, decimal_places=4)
    note: Optional[str] = Field(None, max_length=500)


class BidSubmitRequest(BaseModel):
    lines: list[BidLineInput] = Field(..., min_length=1, max_length=500)


class BidWithdrawRequest(BaseModel):
    version: int = Field(..., ge=1)


class BidLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sourcing_line_id: int
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    note: Optional[str] = None


class BidResponse(BaseModel):
    """A bid as seen by one caller.

    ``sealed`` is true when the caller is the buying organization and the event
    has not been opened yet; ``total_amount`` and ``lines`` are withheld in
    that case. Suppliers always see their own details.
    """

    id: int
    event_id: int
    lot_id: int
    supplier_company_id: int
    supplier_company: CompanyPublicResponse
    status: BidStatus
    currency: str
    sealed: bool
    total_amount: Optional[Decimal] = None
    version: int
    submitted_at: datetime
    withdrawn_at: Optional[datetime] = None
    lines: list[BidLineResponse] = Field(default_factory=list)
