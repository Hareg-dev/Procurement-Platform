from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models.orm import UserRole, RFQStatus


# Base schemas
class CompanyBase(BaseModel):
    """Base company schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Company name")
    description: Optional[str] = Field(None, description="Company description")
    website: Optional[str] = Field(None, max_length=255, description="Company website")
    address: Optional[str] = Field(None, description="Company address")
    phone: Optional[str] = Field(
        None, max_length=50, description="Company phone number"
    )


class CompanyCreate(CompanyBase):
    """Schema for creating a new company."""

    pass


class CompanyResponse(CompanyBase):
    """Schema for company responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# User schemas
class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr = Field(..., description="User email address")
    first_name: str = Field(
        ..., min_length=1, max_length=100, description="User first name"
    )
    last_name: str = Field(
        ..., min_length=1, max_length=100, description="User last name"
    )
    role: UserRole = Field(default=UserRole.BUYER, description="User role")


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str = Field(
        ..., min_length=8, description="User password (min 8 characters)"
    )
    company: CompanyCreate = Field(..., description="Company information")


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class UserResponse(UserBase):
    """Schema for user responses (excludes password)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    company_id: int
    company: CompanyResponse
    title: Optional[str] = None
    bio: Optional[str] = None

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}"


class UserUpdate(BaseModel):
    """Schema for updating user information."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


# Authentication schemas
class Token(BaseModel):
    """Schema for JWT token response."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class TokenData(BaseModel):
    """Schema for JWT token data."""

    user_id: Optional[int] = None
    email: Optional[str] = None


class LoginResponse(BaseModel):
    """Schema for login response."""

    user: UserResponse
    token: Token


# Generic response schemas
class MessageResponse(BaseModel):
    """Generic message response schema."""

    message: str = Field(..., description="Response message")


class ErrorResponse(BaseModel):
    """Error response schema."""

    detail: str = Field(..., description="Error detail message")
    error_code: Optional[str] = Field(None, description="Error code")


# Pagination schemas
class PaginationParams(BaseModel):
    """Schema for pagination parameters."""

    page: int = Field(default=1, ge=1, description="Page number")
    size: int = Field(default=20, ge=1, le=100, description="Page size")


class PaginatedResponse(BaseModel):
    """Generic paginated response schema."""

    items: list
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total number of pages")

    @classmethod
    def create(cls, items: list, total: int, page: int, size: int):
        """Create a paginated response."""
        pages = (total + size - 1) // size  # Ceiling division
        return cls(items=items, total=total, page=page, size=size, pages=pages)


# RFQ schemas
class RFQBase(BaseModel):
    """Base RFQ schema with common fields."""

    title: str = Field(..., min_length=1, max_length=255, description="RFQ title")
    description: str = Field(..., min_length=1, description="RFQ description")
    deadline: datetime = Field(..., description="RFQ deadline")
    budget_min: Optional[float] = Field(None, ge=0, description="Minimum budget")
    budget_max: Optional[float] = Field(None, ge=0, description="Maximum budget")
    requirements: Optional[str] = Field(None, description="Additional requirements")


class RFQCreate(RFQBase):
    """Schema for creating a new RFQ."""

    pass


class RFQUpdate(BaseModel):
    """Schema for updating an RFQ."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1)
    deadline: Optional[datetime] = None
    budget_min: Optional[float] = Field(None, ge=0)
    budget_max: Optional[float] = Field(None, ge=0)
    requirements: Optional[str] = None
    status: Optional[RFQStatus] = None


class RFQResponse(RFQBase):
    """Schema for RFQ responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: RFQStatus
    created_at: datetime
    updated_at: datetime
    buyer_company_id: int
    created_by_user_id: int
    buyer_company: CompanyResponse
    bid_count: int = Field(default=0, description="Number of bids received")
    is_open: bool = Field(description="Whether RFQ is open for bidding")
    is_expired: bool = Field(description="Whether RFQ deadline has passed")


class RFQListResponse(BaseModel):
    """Schema for RFQ list responses with minimal data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    deadline: datetime
    status: RFQStatus
    created_at: datetime
    buyer_company: CompanyResponse


# Bid schemas
class BidBase(BaseModel):
    """Base bid schema with common fields."""

    price: float = Field(..., gt=0, description="Bid price")
    message: Optional[str] = Field(None, description="Bid message/proposal")
    delivery_time: Optional[int] = Field(
        None, ge=1, description="Delivery time in days"
    )
    terms: Optional[str] = Field(None, description="Terms and conditions")


class BidCreate(BidBase):
    """Schema for creating a new bid."""

    pass


class BidUpdate(BaseModel):
    """Schema for updating a bid."""

    price: Optional[float] = Field(None, gt=0)
    message: Optional[str] = None
    delivery_time: Optional[int] = Field(None, ge=1)
    terms: Optional[str] = None


class BidResponse(BidBase):
    """Schema for bid responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rfq_id: int
    supplier_company_id: int
    submitted_by_user_id: int
    is_selected: bool
    created_at: datetime
    updated_at: datetime
    supplier_company: CompanyResponse


class BidListResponse(BaseModel):
    """Schema for bid list responses with minimal data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    price: float
    delivery_time: Optional[int]
    is_selected: bool
    created_at: datetime
    supplier_company: CompanyResponse


# Public schemas for marketplace
class CompanyPublicResponse(BaseModel):
    """Schema for public company information in marketplace."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    public_description: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    location: Optional[str] = None
    created_at: datetime


class UserPublicResponse(BaseModel):
    """Schema for public user information."""

    model_config = ConfigDict(from_attributes=True)

    first_name: str
    last_name: str
    title: Optional[str] = None
    bio: Optional[str] = None


# Dashboard schema for personalized user data
class UserDashboardResponse(BaseModel):
    """Schema for user dashboard with personalized information."""

    model_config = ConfigDict(from_attributes=True)

    first_name: str
    last_name: str
    email: str
    role: UserRole
    title: Optional[str] = None
    bio: Optional[str] = None
    company_name: str


# AI-related schemas
class NegotiationRequest(BaseModel):
    """Schema for AI negotiation message generation request."""

    goal: str = Field(
        ..., min_length=1, max_length=1000, description="Negotiation goal or objective"
    )


class NegotiationResponse(BaseModel):
    """Schema for AI negotiation message generation response."""

    message: str = Field(..., description="Generated negotiation message")
    context_used: str = Field(..., description="Context information that was used")


# Advertisement schemas
class AdvertisementBase(BaseModel):
    """Base advertisement schema."""

    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    image_url: Optional[str] = Field(None, max_length=500)
    target_industries: list[str] = Field(default_factory=list)


class AdvertisementCreate(AdvertisementBase):
    """Schema for creating a new advertisement."""

    pass


class AdvertisementUpdate(BaseModel):
    """Schema for updating an advertisement."""

    title: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[str] = None
    target_industries: Optional[list[str]] = None


class AdvertisementResponse(AdvertisementBase):
    """Schema for advertisement response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
