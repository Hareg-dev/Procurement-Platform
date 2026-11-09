from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v2.deps import get_org_member
from app.core.db import get_db
from app.models.agents import AgentRunStatus, ProposalStatus
from app.models.agent_schemas import (
    AgentProposalResponse,
    AgentRunResponse,
    AgentRunSummary,
    IntakeRequest,
    ProposalDecisionRequest,
)
from app.services.agents.proposals import proposal_service
from app.services.agents.runtime import (
    intake_agent_runtime,
    list_runs,
    load_run,
)

router = APIRouter(prefix="/agents", tags=["v2-agents"])


@router.post(
    "/intake",
    response_model=AgentRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run the intake agent on a free-text request",
)
async def run_intake(
    payload: IntakeRequest,
    member=Depends(get_org_member),
    db: AsyncSession = Depends(get_db),
) -> AgentRunResponse:
    """The agent can only read data and record a proposal; it cannot write."""
    return await intake_agent_runtime.run(
        db,
        user=member.user,
        member=member,
        message=payload.message,
    )


@router.get(
    "/runs",
    response_model=list[AgentRunSummary],
    summary="List agent runs for the caller's organization",
)
async def list_agent_runs(
    status_filter: Optional[AgentRunStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member=Depends(get_org_member),
    db: AsyncSession = Depends(get_db),
) -> list[AgentRunSummary]:
    return await list_runs(
        db,
        organization_id=member.organization_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/runs/{run_id}",
    response_model=AgentRunResponse,
    summary="Get one agent run with its provenance steps and proposals",
)
async def get_agent_run(
    run_id: int,
    member=Depends(get_org_member),
    db: AsyncSession = Depends(get_db),
) -> AgentRunResponse:
    return await load_run(
        db,
        organization_id=member.organization_id,
        run_id=run_id,
    )


@router.get(
    "/proposals",
    response_model=list[AgentProposalResponse],
    summary="List agent proposals for the caller's organization",
)
async def list_agent_proposals(
    status_filter: Optional[ProposalStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member=Depends(get_org_member),
    db: AsyncSession = Depends(get_db),
) -> list[AgentProposalResponse]:
    return await proposal_service.list(
        db,
        organization_id=member.organization_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/proposals/{proposal_id}",
    response_model=AgentProposalResponse,
    summary="Get one agent proposal",
)
async def get_agent_proposal(
    proposal_id: int,
    member=Depends(get_org_member),
    db: AsyncSession = Depends(get_db),
) -> AgentProposalResponse:
    return await proposal_service.get(
        db,
        organization_id=member.organization_id,
        proposal_id=proposal_id,
    )


@router.post(
    "/proposals/{proposal_id}/approve",
    response_model=AgentProposalResponse,
    summary="Approve a proposal and execute its action",
)
async def approve_agent_proposal(
    proposal_id: int,
    payload: ProposalDecisionRequest,
    member=Depends(get_org_member),
    db: AsyncSession = Depends(get_db),
) -> AgentProposalResponse:
    return await proposal_service.approve(
        db,
        member=member,
        proposal_id=proposal_id,
        comment=payload.comment,
    )


@router.post(
    "/proposals/{proposal_id}/reject",
    response_model=AgentProposalResponse,
    summary="Reject a proposal without executing it",
)
async def reject_agent_proposal(
    proposal_id: int,
    payload: ProposalDecisionRequest,
    member=Depends(get_org_member),
    db: AsyncSession = Depends(get_db),
) -> AgentProposalResponse:
    return await proposal_service.reject(
        db,
        member=member,
        proposal_id=proposal_id,
        comment=payload.comment,
    )
