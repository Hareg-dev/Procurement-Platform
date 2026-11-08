"""Tests for the v2 requisition and approval slice.

These exercise the real business rules: server-side totals, tenant isolation,
organization membership, the default approval ladder, segregation of duties,
budget commitment on final approval and optimistic concurrency.
"""

import datetime as dt
from decimal import Decimal

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_token_with_user_data
from app.models.orm import Company, User, UserRole
from app.models.procurement import (
    AuditEvent,
    Budget,
    OrganizationMember,
    OrgRole,
    OutboxEvent,
    RequisitionStatus,
)


def auth_headers(user: User) -> dict[str, str]:
    token = create_token_with_user_data(user.id, user.email)
    return {"Authorization": f"Bearer {token}"}


async def _make_member(
    session: AsyncSession,
    company: Company,
    key: str,
    org_role: OrgRole,
) -> User:
    user = User(
        email=f"{key}@procurement.test",
        hashed_password="unused-in-tests",
        first_name=key.title(),
        last_name="Tester",
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
async def team(
    test_db_session: AsyncSession,
    test_company: Company,
    test_supplier_company: Company,
):
    return {
        "requester": await _make_member(
            test_db_session, test_company, "requester", OrgRole.ORG_ADMIN
        ),
        "approver": await _make_member(
            test_db_session, test_company, "approver", OrgRole.APPROVER
        ),
        "finance": await _make_member(
            test_db_session, test_company, "finance", OrgRole.FINANCE
        ),
        "admin2": await _make_member(
            test_db_session, test_company, "admin2", OrgRole.ORG_ADMIN
        ),
        "outsider": await _make_member(
            test_db_session,
            test_supplier_company,
            "outsider",
            OrgRole.ORG_ADMIN,
        ),
    }


@pytest_asyncio.fixture
async def ops_budget(test_db_session: AsyncSession, test_company: Company):
    budget = Budget(
        organization_id=test_company.id,
        cost_center="OPS",
        fiscal_year=dt.datetime.utcnow().year,
        currency="USD",
        amount=Decimal("20000"),
        committed_amount=Decimal("0"),
    )
    test_db_session.add(budget)
    await test_db_session.commit()
    await test_db_session.refresh(budget)
    return budget


def payload(total: str = "1000", cost_center: str = "OPS") -> dict:
    return {
        "title": "Laptops for the field team",
        "currency": "usd",
        "cost_center": cost_center,
        "needed_by": "2030-01-31",
        "lines": [
            {
                "description": "Laptop",
                "quantity": "1",
                "unit_price": total,
            }
        ],
    }


async def _create(
    client: AsyncClient, user: User, body: dict | None = None
) -> dict:
    response = await client.post(
        "/api/v2/requisitions",
        json=body or payload(),
        headers=auth_headers(user),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _submit(
    client: AsyncClient, user: User, requisition: dict
) -> dict:
    response = await client.post(
        f"/api/v2/requisitions/{requisition['id']}/submit",
        json={"version": requisition["version"]},
        headers=auth_headers(user),
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestRequisitionCreation:
    async def test_totals_are_computed_server_side(
        self, test_client: AsyncClient, team, test_db_session: AsyncSession
    ):
        body = {
            "title": "Office refresh",
            "currency": "usd",
            "cost_center": "OPS",
            "lines": [
                {"description": "Chair", "quantity": "2", "unit_price": "100.50"},
                {"description": "Desk", "quantity": "1", "unit_price": "250"},
            ],
        }
        response = await test_client.post(
            "/api/v2/requisitions",
            json=body,
            headers={
                **auth_headers(team["requester"]),
                "X-Request-ID": "test-correlation-123",
            },
        )
        assert response.status_code == 201, response.text
        assert response.headers["x-request-id"] == "test-correlation-123"
        data = response.json()

        assert data["currency"] == "USD"
        assert Decimal(data["total_amount"]) == Decimal("451.00")
        assert data["status"] == RequisitionStatus.DRAFT.value
        assert data["requisition_number"].startswith("REQ-")
        assert [line["line_number"] for line in data["lines"]] == [1, 2]
        assert Decimal(data["lines"][0]["line_total"]) == Decimal("201.00")

        audit = (
            await test_db_session.execute(
                select(AuditEvent).where(
                    AuditEvent.entity_type == "requisition",
                    AuditEvent.entity_id == data["id"],
                    AuditEvent.action == "requisition.created",
                )
            )
        ).scalars().first()
        assert audit is not None
        assert audit.correlation_id == "test-correlation-123"

    async def test_membership_is_required(
        self, test_client: AsyncClient, test_buyer_user: User
    ):
        response = await test_client.post(
            "/api/v2/requisitions",
            json=payload(),
            headers=auth_headers(test_buyer_user),
        )
        assert response.status_code == 403
        assert "membership" in response.json()["detail"].lower()

    async def test_tenant_isolation(
        self, test_client: AsyncClient, team, test_supplier_company: Company
    ):
        outsider_requisition = await _create(test_client, team["outsider"])

        response = await test_client.get(
            f"/api/v2/requisitions/{outsider_requisition['id']}",
            headers=auth_headers(team["requester"]),
        )
        assert response.status_code == 404

        listing = await test_client.get(
            "/api/v2/requisitions",
            headers=auth_headers(team["requester"]),
        )
        assert listing.status_code == 200
        assert listing.json() == []


class TestSubmissionAndRouting:
    async def test_default_ladder_and_inbox_visibility(
        self, test_client: AsyncClient, team
    ):
        requisition = await _create(test_client, team["requester"], payload("1000"))
        submitted = await _submit(test_client, team["requester"], requisition)

        assert submitted["status"] == RequisitionStatus.IN_APPROVAL.value
        assert [step["step_order"] for step in submitted["approval_steps"]] == [1]
        assert submitted["approval_steps"][0]["required_role"] == OrgRole.APPROVER.value

        approver_inbox = await test_client.get(
            "/api/v2/approvals", headers=auth_headers(team["approver"])
        )
        assert approver_inbox.status_code == 200
        assert len(approver_inbox.json()) == 1
        assert approver_inbox.json()[0]["requisition"]["id"] == requisition["id"]

        finance_inbox = await test_client.get(
            "/api/v2/approvals", headers=auth_headers(team["finance"])
        )
        assert finance_inbox.json() == []

        requester_inbox = await test_client.get(
            "/api/v2/approvals", headers=auth_headers(team["requester"])
        )
        assert requester_inbox.json() == []

    async def test_approver_cannot_approve_own_request(
        self, test_client: AsyncClient, team
    ):
        # An approver may raise demand, but must never approve it themselves.
        requisition = await _create(test_client, team["approver"], payload("1000"))
        submitted = await _submit(test_client, team["approver"], requisition)
        step_id = submitted["approval_steps"][0]["id"]

        inbox = await test_client.get(
            "/api/v2/approvals", headers=auth_headers(team["approver"])
        )
        assert inbox.json() == []

        decision = await test_client.post(
            f"/api/v2/approvals/{step_id}/decision",
            json={
                "decision": "approve",
                "version": submitted["version"],
            },
            headers=auth_headers(team["approver"]),
        )
        assert decision.status_code == 403
        assert "requester" in decision.json()["detail"].lower()

    async def test_immutable_after_submission(
        self, test_client: AsyncClient, team
    ):
        requisition = await _create(test_client, team["requester"])
        submitted = await _submit(test_client, team["requester"], requisition)

        response = await test_client.patch(
            f"/api/v2/requisitions/{requisition['id']}",
            json={"version": submitted["version"], "title": "Changed"},
            headers=auth_headers(team["requester"]),
        )
        assert response.status_code == 409

    async def test_optimistic_concurrency(
        self, test_client: AsyncClient, team
    ):
        requisition = await _create(test_client, team["requester"])

        response = await test_client.patch(
            f"/api/v2/requisitions/{requisition['id']}",
            json={"version": requisition["version"] + 5, "title": "Changed"},
            headers=auth_headers(team["requester"]),
        )
        assert response.status_code == 409
        assert "modified" in response.json()["detail"].lower()

    async def test_cancel_skips_outstanding_steps(
        self, test_client: AsyncClient, team
    ):
        requisition = await _create(test_client, team["requester"])
        submitted = await _submit(test_client, team["requester"], requisition)

        response = await test_client.post(
            f"/api/v2/requisitions/{requisition['id']}/cancel",
            json={"version": submitted["version"], "reason": "No longer needed"},
            headers=auth_headers(team["requester"]),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == RequisitionStatus.CANCELLED.value
        assert body["approval_steps"][0]["status"] == "skipped"


class TestApprovalFlow:
    async def test_full_approval_commits_budget(
        self,
        test_client: AsyncClient,
        team,
        ops_budget: Budget,
        test_db_session: AsyncSession,
    ):
        requisition = await _create(
            test_client, team["requester"], payload("10000")
        )
        submitted = await _submit(test_client, team["requester"], requisition)
        assert [
            step["required_role"] for step in submitted["approval_steps"]
        ] == [OrgRole.APPROVER.value, OrgRole.FINANCE.value]

        first = await test_client.post(
            f"/api/v2/approvals/{submitted['approval_steps'][0]['id']}/decision",
            json={"decision": "approve", "version": submitted["version"]},
            headers=auth_headers(team["approver"]),
        )
        assert first.status_code == 200, first.text
        assert first.json()["status"] == RequisitionStatus.IN_APPROVAL.value
        assert first.json()["approval_steps"][0]["status"] == "approved"

        finance_inbox = await test_client.get(
            "/api/v2/approvals", headers=auth_headers(team["finance"])
        )
        assert len(finance_inbox.json()) == 1

        second = await test_client.post(
            f"/api/v2/approvals/{submitted['approval_steps'][1]['id']}/decision",
            json={
                "decision": "approve",
                "version": first.json()["version"],
                "comment": "Approved",
            },
            headers=auth_headers(team["finance"]),
        )
        assert second.status_code == 200, second.text
        assert second.json()["status"] == RequisitionStatus.APPROVED.value
        assert second.json()["decided_at"] is not None

        await test_db_session.refresh(ops_budget)
        assert ops_budget.committed_amount == Decimal("10000.0000")

        audit_actions = {
            event.action
            for event in (
                await test_db_session.execute(
                    select(AuditEvent).where(
                        AuditEvent.entity_type == "requisition",
                        AuditEvent.entity_id == requisition["id"],
                    )
                )
            ).scalars().all()
        }
        assert {"requisition.submitted", "requisition.approved"} <= audit_actions

        outbox_types = {
            event.event_type
            for event in (
                await test_db_session.execute(
                    select(OutboxEvent).where(
                        OutboxEvent.aggregate_id == requisition["id"]
                    )
                )
            ).scalars().all()
        }
        assert {"requisition.submitted", "requisition.approved"} <= outbox_types

    async def test_rejection_skips_remaining_steps(
        self,
        test_client: AsyncClient,
        team,
        ops_budget: Budget,
        test_db_session: AsyncSession,
    ):
        requisition = await _create(
            test_client, team["requester"], payload("10000")
        )
        submitted = await _submit(test_client, team["requester"], requisition)

        response = await test_client.post(
            f"/api/v2/approvals/{submitted['approval_steps'][0]['id']}/decision",
            json={
                "decision": "reject",
                "version": submitted["version"],
                "comment": "Budget freeze",
            },
            headers=auth_headers(team["approver"]),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == RequisitionStatus.REJECTED.value
        assert [step["status"] for step in body["approval_steps"]] == [
            "rejected",
            "skipped",
        ]

        await test_db_session.refresh(ops_budget)
        assert ops_budget.committed_amount == Decimal("0")

    async def test_budget_shortfall_blocks_submission(
        self,
        test_client: AsyncClient,
        team,
        ops_budget: Budget,
        test_db_session: AsyncSession,
    ):
        ops_budget.amount = Decimal("500")
        await test_db_session.commit()

        requisition = await _create(test_client, team["requester"], payload("1000"))

        response = await test_client.post(
            f"/api/v2/requisitions/{requisition['id']}/submit",
            json={"version": requisition["version"]},
            headers=auth_headers(team["requester"]),
        )
        assert response.status_code == 400
        assert "insufficient budget" in response.json()["detail"].lower()

    async def test_configured_policy_overrides_default_ladder(
        self, test_client: AsyncClient, team
    ):
        policy = await test_client.post(
            "/api/v2/approval-policies",
            json={
                "name": "All amounts need an org admin",
                "min_amount": "0",
                "max_amount": "100000",
                "currency": "USD",
                "required_role": OrgRole.ORG_ADMIN.value,
                "step_order": 1,
            },
            headers=auth_headers(team["requester"]),
        )
        assert policy.status_code == 201, policy.text

        requisition = await _create(test_client, team["requester"], payload("3000"))
        submitted = await _submit(test_client, team["requester"], requisition)
        assert [
            step["required_role"] for step in submitted["approval_steps"]
        ] == [OrgRole.ORG_ADMIN.value]

        # The requester is an org admin and cannot self-approve.
        inbox = await test_client.get(
            "/api/v2/approvals", headers=auth_headers(team["requester"])
        )
        assert inbox.json() == []

        approved = await test_client.post(
            f"/api/v2/approvals/{submitted['approval_steps'][0]['id']}/decision",
            json={"decision": "approve", "version": submitted["version"]},
            headers=auth_headers(team["admin2"]),
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == RequisitionStatus.APPROVED.value
