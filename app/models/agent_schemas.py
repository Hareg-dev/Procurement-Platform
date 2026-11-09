"""Schemas for the agent runtime and proposal workflow."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.agents import AgentRunStatus, ProposalStatus


class IntakeRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)


class AgentStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step_index: int
    kind: str
    role: Optional[str] = None
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[dict] = None
    created_at: datetime


class AgentProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    run_id: int
    action: str
    payload: dict
    rationale: Optional[str] = None
    evidence: Optional[list] = None
    confidence: Optional[Decimal] = None
    status: ProposalStatus
    proposed_by_user_id: int
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_comment: Optional[str] = None
    executed_entity_type: Optional[str] = None
    executed_entity_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class AgentRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_name: str
    model_name: Optional[str] = None
    status: AgentRunStatus
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    prompt_hash: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    created_at: datetime


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    initiated_by_user_id: int
    agent_name: str
    model_name: Optional[str] = None
    status: AgentRunStatus
    prompt_hash: Optional[str] = None
    input: Optional[dict] = None
    output: Optional[dict] = None
    error: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    correlation_id: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    steps: list[AgentStepResponse] = Field(default_factory=list)
    proposals: list[AgentProposalResponse] = Field(default_factory=list)


class ProposalDecisionRequest(BaseModel):
    comment: Optional[str] = Field(None, max_length=1000)
