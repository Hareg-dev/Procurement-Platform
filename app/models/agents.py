"""
Agent runtime provenance and human-gated proposals.

An agent never mutates business data. It runs with read-only tools plus proposal
tools; a proposal records exactly what the agent wants to do, why, with what
confidence and evidence. A human approves or rejects it, and only the approval
path executes the action through the same domain services used by the API.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.orm import BaseModel, Company, User, utcnow


class AgentRunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProposalStatus(str, Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    REJECTED = "rejected"
    FAILED = "failed"


class AgentRun(BaseModel):
    """One invocation of an agent, with its inputs, output and token usage."""

    __tablename__ = "agent_runs"

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    initiated_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    status: Mapped[AgentRunStatus] = mapped_column(
        SQLEnum(AgentRunStatus),
        nullable=False,
        default=AgentRunStatus.RUNNING,
        index=True,
    )
    prompt_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    input: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    completion_tokens: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    steps: Mapped[list["AgentStep"]] = relationship(
        "AgentStep",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentStep.step_index",
    )
    proposals: Mapped[list["AgentProposal"]] = relationship(
        "AgentProposal",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentProposal.id",
    )


class AgentStep(BaseModel):
    """Ordered provenance for one run: messages, tool calls and results."""

    __tablename__ = "agent_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "step_index", name="uq_agent_step_index"),
    )

    run_id: Mapped[int] = mapped_column(
        ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    tool_input: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    tool_output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    run: Mapped[AgentRun] = relationship("AgentRun", back_populates="steps")


class AgentProposal(BaseModel):
    """A proposed action awaiting human decision."""

    __tablename__ = "agent_proposals"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_agent_proposal_confidence",
        ),
    )

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    run_id: Mapped[int] = mapped_column(
        ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 3), nullable=True
    )
    status: Mapped[ProposalStatus] = mapped_column(
        SQLEnum(ProposalStatus),
        nullable=False,
        default=ProposalStatus.PENDING,
        index=True,
    )
    proposed_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    review_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_entity_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    executed_entity_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    run: Mapped[AgentRun] = relationship(
        "AgentRun", back_populates="proposals"
    )
    proposed_by: Mapped[User] = relationship(
        "User", foreign_keys=[proposed_by_user_id]
    )
    reviewed_by: Mapped[Optional[User]] = relationship(
        "User", foreign_keys=[reviewed_by_user_id]
    )
