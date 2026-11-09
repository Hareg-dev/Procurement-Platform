"""Agent runtime tests: tools, proposals, approval and provenance.

No test calls Groq. The runtime's `_invoke` seam is replaced with a deterministic
fake, and model construction is checked without sending a request.
"""

from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_token_with_user_data
from app.models.agents import (
    AgentProposal,
    AgentRun,
    AgentRunStatus,
    ProposalStatus,
)
from app.models.orm import Company, User, UserRole
from app.models.procurement import (
    AuditEvent,
    OrganizationMember,
    OrgRole,
    Requisition,
)
from app.services.agents.runtime import IntakeAgentRuntime
from app.services.agents.tools import (
    ProposeRequisitionArgs,
    ToolContext,
    tool_propose_requisition,
)


def auth_headers(user: User) -> dict[str, str]:
    token = create_token_with_user_data(user.id, user.email)
    return {"Authorization": f"Bearer {token}"}


async def _make_member(
    session: AsyncSession,
    company: Company,
    key: str,
    org_role: OrgRole = OrgRole.ORG_ADMIN,
) -> User:
    user = User(
        email=f"{key}@agents.test",
        hashed_password="unused-in-tests",
        first_name=key.title(),
        last_name="Agent",
        role=UserRole.BUYER,
        is_active=True,
        is_verified=True,
        company_id=company.id,
    )
    session.add(user)
    await session.flush()
    session.add(
        OrganizationMember(
            organization_id=company.id,
            user_id=user.id,
            org_role=org_role,
        )
    )
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def buyer(test_db_session: AsyncSession, test_company: Company) -> User:
    return await _make_member(test_db_session, test_company, "agentbuyer")


@pytest_asyncio.fixture
async def buyer_member(
    test_db_session: AsyncSession, buyer: User
) -> OrganizationMember:
    result = await test_db_session.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == buyer.id
        )
    )
    return result.scalar_one()


@pytest_asyncio.fixture
async def other_buyer(test_db_session: AsyncSession) -> User:
    company = Company(name="Other Buyer Ltd.", is_active=True)
    test_db_session.add(company)
    await test_db_session.flush()
    return await _make_member(test_db_session, company, "otherbuyer")


def proposal_args() -> ProposeRequisitionArgs:
    return ProposeRequisitionArgs(
        title="Ergonomic office chairs",
        description="Ten chairs for the new floor",
        cost_center="OPS",
        currency="USD",
        needed_by="2030-01-31",
        lines=[
            {
                "description": "Ergonomic chair",
                "quantity": "10",
                "unit_of_measure": "unit",
                "unit_price": "50",
            }
        ],
        rationale="The new floor needs seating before the team moves in.",
        confidence=0.9,
        evidence=["Facilities confirmed the request"],
    )


async def _run_and_proposal(
    session: AsyncSession, buyer: User, member: OrganizationMember
):
    run = AgentRun(
        organization_id=member.organization_id,
        initiated_by_user_id=buyer.id,
        agent_name="IntakeAgent",
        model_name="llama-3.3-70b-versatile",
        status=AgentRunStatus.RUNNING,
        input={"message": "Need ten chairs"},
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    ctx = ToolContext(
        db=session, user=buyer, member=member, run=run, step_index=1
    )
    result = await tool_propose_requisition(ctx, proposal_args())
    await session.commit()
    return run, ctx, result


class TestProposalWorkflow:
    async def test_tool_creates_one_pending_proposal(
        self,
        test_db_session: AsyncSession,
        buyer: User,
        buyer_member: OrganizationMember,
    ):
        run, ctx, result = await _run_and_proposal(
            test_db_session, buyer, buyer_member
        )

        assert result["status"] == "pending"
        assert Decimal(result["total_amount"]) == Decimal("500")
        assert result["currency"] == "USD"

        proposal = await test_db_session.get(
            AgentProposal, result["proposal_id"]
        )
        assert proposal is not None
        assert proposal.status == ProposalStatus.PENDING
        assert proposal.action == "create_requisition"
        assert proposal.payload["title"] == "Ergonomic office chairs"
        assert proposal.confidence == Decimal("0.900")

        second = await tool_propose_requisition(ctx, proposal_args())
        assert "error" in second

        count = await test_db_session.scalar(
            select(func.count())
            .select_from(AgentProposal)
            .where(AgentProposal.run_id == run.id)
        )
        assert count == 1

        audit_actions = {
            event.action
            for event in (
                await test_db_session.execute(
                    select(AuditEvent).where(
                        AuditEvent.entity_type == "agent_proposal",
                        AuditEvent.entity_id == proposal.id,
                    )
                )
            ).scalars().all()
        }
        assert "agent_proposal.created" in audit_actions

    async def test_approval_executes_requisition(
        self,
        test_client: AsyncClient,
        test_db_session: AsyncSession,
        buyer: User,
        buyer_member: OrganizationMember,
    ):
        _, _, result = await _run_and_proposal(
            test_db_session, buyer, buyer_member
        )
        proposal_id = result["proposal_id"]

        response = await test_client.post(
            f"/api/v2/agents/proposals/{proposal_id}/approve",
            json={"comment": "Approved for the new floor"},
            headers=auth_headers(buyer),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == ProposalStatus.EXECUTED.value
        assert body["executed_entity_type"] == "requisition"
        assert body["reviewed_by_user_id"] == buyer.id

        requisition_id = body["executed_entity_id"]
        requisition = await test_client.get(
            f"/api/v2/requisitions/{requisition_id}",
            headers=auth_headers(buyer),
        )
        assert requisition.status_code == 200, requisition.text
        data = requisition.json()
        assert Decimal(data["total_amount"]) == Decimal("500")
        assert data["requested_by_user_id"] == buyer.id
        assert data["status"] == "draft"

        again = await test_client.post(
            f"/api/v2/agents/proposals/{proposal_id}/approve",
            json={},
            headers=auth_headers(buyer),
        )
        assert again.status_code == 409

    async def test_rejection_does_not_create_requisition(
        self,
        test_client: AsyncClient,
        test_db_session: AsyncSession,
        buyer: User,
        buyer_member: OrganizationMember,
    ):
        _, _, result = await _run_and_proposal(
            test_db_session, buyer, buyer_member
        )

        response = await test_client.post(
            f"/api/v2/agents/proposals/{result['proposal_id']}/reject",
            json={"comment": "Not this quarter"},
            headers=auth_headers(buyer),
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == ProposalStatus.REJECTED.value

        requisition_count = await test_db_session.scalar(
            select(func.count())
            .select_from(Requisition)
            .where(
                Requisition.organization_id
                == buyer_member.organization_id
            )
        )
        assert requisition_count == 0

    async def test_tenant_isolation(
        self,
        test_client: AsyncClient,
        test_db_session: AsyncSession,
        buyer: User,
        buyer_member: OrganizationMember,
        other_buyer: User,
    ):
        _, _, result = await _run_and_proposal(
            test_db_session, buyer, buyer_member
        )
        proposal_id = result["proposal_id"]

        read = await test_client.get(
            f"/api/v2/agents/proposals/{proposal_id}",
            headers=auth_headers(other_buyer),
        )
        assert read.status_code == 404

        approve = await test_client.post(
            f"/api/v2/agents/proposals/{proposal_id}/approve",
            json={},
            headers=auth_headers(other_buyer),
        )
        assert approve.status_code == 404


class TestIntakeEndpoint:
    async def test_intake_requires_groq_configuration(
        self,
        test_client: AsyncClient,
        monkeypatch,
        buyer: User,
    ):
        monkeypatch.setattr(settings, "groq_api_key", "")

        response = await test_client.post(
            "/api/v2/agents/intake",
            json={"message": "I need ten office chairs"},
            headers=auth_headers(buyer),
        )
        assert response.status_code == 503
        assert "GROQ_API_KEY" in response.json()["detail"]

    async def test_intake_run_with_fake_agent(
        self,
        test_client: AsyncClient,
        monkeypatch,
        buyer: User,
    ):
        monkeypatch.setattr(settings, "groq_api_key", "test-key")

        async def fake_invoke(self, ctx, message):
            result = await tool_propose_requisition(ctx, proposal_args())
            assert "proposal_id" in result

            class Reply:
                content = "Proposal recorded; awaiting human review."
                usage = None

            return Reply()

        monkeypatch.setattr(IntakeAgentRuntime, "_invoke", fake_invoke)

        response = await test_client.post(
            "/api/v2/agents/intake",
            json={"message": "I need ten office chairs"},
            headers=auth_headers(buyer),
        )
        assert response.status_code == 201, response.text
        body = response.json()

        assert body["status"] == AgentRunStatus.COMPLETED.value
        assert body["model_name"] == settings.groq_model
        assert body["finished_at"] is not None
        assert len(body["proposals"]) == 1
        assert body["proposals"][0]["status"] == ProposalStatus.PENDING.value
        assert body["output"]["reply"].startswith("Proposal recorded")

        kinds = [step["kind"] for step in body["steps"]]
        assert "message" in kinds
        assert "tool_call" in kinds
        assert "tool_result" in kinds
        assert "final" in kinds

        run_id = body["id"]
        fetched = await test_client.get(
            f"/api/v2/agents/runs/{run_id}",
            headers=auth_headers(buyer),
        )
        assert fetched.status_code == 200
        assert len(fetched.json()["steps"]) == len(body["steps"])


def test_groq_model_configuration():
    pytest.importorskip("agentscope")
    from app.services.agents.runtime import build_model

    model = build_model(
        api_key="test-key",
        base_url="https://api.groq.com/openai/v1",
        model_name="llama-3.3-70b-versatile",
        temperature=0.2,
        max_tokens=256,
    )
    assert type(model).__name__ == "OpenAIChatModel"
    assert model.model == "llama-3.3-70b-versatile"
    assert model.credential.base_url == "https://api.groq.com/openai/v1"
