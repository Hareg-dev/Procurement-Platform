from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, JSON, Enum as SQLEnum, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class UserRole(str, Enum):
    """User role enumeration."""

    BUYER = "buyer"
    SUPPLIER = "supplier"
    ADMIN = "admin"


class RFQStatus(str, Enum):
    """RFQ status enumeration."""

    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    AWARDED = "awarded"
    CANCELLED = "cancelled"


class BaseModel(Base):
    """Base model with common fields for all entities."""

    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class Company(BaseModel):
    """Company model for organizations using the platform."""

    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Public profile fields
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    public_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="company", cascade="all, delete-orphan"
    )
    rfqs: Mapped[list["RFQ"]] = relationship(
        "RFQ", back_populates="buyer_company", cascade="all, delete-orphan"
    )
    bids: Mapped[list["Bid"]] = relationship(
        "Bid", back_populates="supplier_company", cascade="all, delete-orphan"
    )
    posts: Mapped[list["Post"]] = relationship(
        "Post", back_populates="company", cascade="all, delete-orphan"
    )


class User(BaseModel):
    """User model for platform users."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), nullable=False, default=UserRole.BUYER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Public profile fields
    title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Foreign keys
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="users")
    posts: Mapped[list["Post"]] = relationship(
        "Post", back_populates="author", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<User(email='{self.email}', role='{self.role}')>"


class Post(BaseModel):
    """Post model for user-generated content."""

    __tablename__ = "posts"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    
    # Foreign keys
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )

    # Relationships
    author: Mapped["User"] = relationship("User", back_populates="posts")
    company: Mapped["Company"] = relationship("Company", back_populates="posts")

    def __repr__(self) -> str:
        return f"<Post(title='{self.title}', author_id={self.author_id})>"


class RFQ(BaseModel):
    """Request for Quotation model."""

    __tablename__ = "rfqs"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[RFQStatus] = mapped_column(
        SQLEnum(RFQStatus), nullable=False, default=RFQStatus.DRAFT, index=True
    )
    budget_min: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    budget_max: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # AI-generated summary
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Foreign keys
    buyer_company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )

    # Relationships
    buyer_company: Mapped["Company"] = relationship("Company", back_populates="rfqs")
    created_by: Mapped["User"] = relationship("User")
    bids: Mapped[list["Bid"]] = relationship(
        "Bid", back_populates="rfq", cascade="all, delete-orphan"
    )

    @property
    def is_open(self) -> bool:
        """Check if RFQ is open for bidding."""
        return self.status == RFQStatus.OPEN and self.deadline > datetime.utcnow()

    @property
    def is_expired(self) -> bool:
        """Check if RFQ deadline has passed."""
        return self.deadline <= datetime.utcnow()

    @property
    def bid_count(self) -> int:
        """Get number of bids submitted."""
        return len(self.bids) if self.bids else 0

    def __repr__(self) -> str:
        return f"<RFQ(title='{self.title}', status='{self.status}')>"


class Bid(BaseModel):
    """Bid model for supplier responses to RFQs."""

    __tablename__ = "bids"

    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    delivery_time: Mapped[Optional[int]] = mapped_column(nullable=True)
    
    __table_args__ = (
        CheckConstraint('delivery_time >= 0', name='positive_delivery_time'),
        CheckConstraint('price > 0', name='positive_price'),
    )
    terms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # AI-generated summary
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Foreign keys
    rfq_id: Mapped[int] = mapped_column(
        ForeignKey("rfqs.id"), nullable=False, index=True
    )
    supplier_company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    submitted_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )

    # Relationships
    rfq: Mapped["RFQ"] = relationship("RFQ", back_populates="bids")
    supplier_company: Mapped["Company"] = relationship("Company", back_populates="bids")
    submitted_by: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<Bid(rfq_id={self.rfq_id}, price='{self.price}')>"


class Advertisement(BaseModel):
    """Advertisement model for targeted ads."""

    __tablename__ = "advertisements"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    target_industries: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    def __repr__(self) -> str:
        return f"<Advertisement(title='{self.title}')>"