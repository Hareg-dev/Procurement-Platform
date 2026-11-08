"""Sourcing v2 tests: lifecycle, invitations, sealed bids, Q&A and addenda."""

import datetime as dt
from decimal import Decimal

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_token_with_user_data
from app.models.orm import Company, User, UserRole
from app.models.procurement import (
    OrganizationMember,
    OrgRole,
    Requisition,
    RequisitionStatus,
)
from app.models.sourcing import SourcingStatus


def auth_headers(user: User) -> dict[str, str]:
    token = create_token_with_user_data(user.id, user.email)
    return {"Authorization": f"Bearer {token}"}


async def _make_member(
    session: AsyncSession,
    company: Company,
    key: str,
    marketplace_role: UserRole,
    org_role: OrgRole = OrgRole.ORG_ADMIN,
) -> User:
    user = User(
        email=f"{key}@sourcing.test",
        hashed_password="unused-in-tests",
        first_name=key.title(),
        last_name="Tester",
        role=marketplace_role,
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
    return await _make_member(
        test_db_session, test_company, "sourcingbuyer", UserRole.BUYER
    )


@pytest_asyncio.fixture
async def second_supplier(test_db_session: AsyncSession) -> User:
    company = Company(name="Second Supplier Ltd.", is_active=True)
    test_db_session.add(company)
    await test_db_session.flush()
    return await _make_member(
        test_db_session,
        company,
        "secondsupplier",
        UserRole.SUPPLIER,
        OrgRole.REQUESTER,
    )


def event_payload(
    *,
    visibility: str = "public",
    sealed: bool = True,
    closing_in_days: int = 10,
) -> dict:
    closing = dt.datetime.utcnow() + dt.timedelta(days=closing_in_days)
    return {
        "title": "Office supplies",
        "description": "Quarterly office supplies",
        "currency": "usd",
        "visibility": visibility,
        "sealed_bids": sealed,
        "closing_at": closing.isoformat(),
        "lots": [
            {
                "title": "Lot A - furniture",
                "lines": [
                    {
                        "description": "Chairs",
                        "quantity": "10",
                        "target_unit_price": "50",
                    },
                    {
                        "description": "Desks",
                        "quantity": "5",
                        "target_unit_price": "200",
                    },
                ],
            },
            {
                "title": "Lot B - consumables",
                "lines": [
                    {
                        "description": "Paper reams",
                        "quantity": "100",
                        "target_unit_price": "3",
                    }
                ],
            },
        ],
    }


async def _create_event(
    client: AsyncClient, buyer: User, **overrides
) -> dict:
    response = await client.post(
        "/api/v2/sourcing-events",
        json=event_payload(**overrides),
        headers=auth_headers(buyer),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _transition(
    client: AsyncClient, user: User, event: dict, action: str
) -> dict:
    response = await client.post(
        f"/api/v2/sourcing-events/{event['id']}/{action}",
        json={"version": event["version"]},
        headers=auth_headers(user),
    )
    assert response.status_code == 200, response.text
    return response.json()


def bid_payload(lot: dict, prices: list[str]) -> dict:
    return {
        "lines": [
            {"sourcing_line_id": line["id"], "unit_price": price}
            for line, price in zip(lot["lines"], prices)
        ]
    }


async def _submit_bid(
    client: AsyncClient,
    supplier: User,
    event: dict,
    lot: dict,
    prices: list[str],
):
    return await client.post(
        f"/api/v2/sourcing-events/{event['id']}/lots/{lot['id']}/bids",
        json=bid_payload(lot, prices),
        headers=auth_headers(supplier),
    )


async def _published_public_event(
    client: AsyncClient, buyer: User
) -> dict:
    event = await _create_event(client, buyer)
    return await _transition(client, buyer, event, "publish")


class TestEventLifecycle:
    async def test_create_and_replace_lots(
        self, test_client: AsyncClient, buyer: User
    ):
        event = await _create_event(test_client, buyer)

        assert event["event_number"].startswith("SRC-")
        assert event["status"] == SourcingStatus.DRAFT.value
        assert [lot["lot_number"] for lot in event["lots"]] == [1, 2]
        assert len(event["lots"][0]["lines"]) == 2

        response = await test_client.put(
            f"/api/v2/sourcing-events/{event['id']}/lots",
            json={
                "version": event["version"],
                "lots": [
                    {
                        "title": "Single lot",
                        "lines": [
                            {
                                "description": "Notebooks",
                                "quantity": "20",
                            }
                        ],
                    }
                ],
            },
            headers=auth_headers(buyer),
        )
        assert response.status_code == 200, response.text
        updated = response.json()
        assert len(updated["lots"]) == 1
        assert updated["version"] == event["version"] + 1

    async def test_invited_event_requires_invitation_before_publish(
        self,
        test_client: AsyncClient,
        buyer: User,
        test_supplier_company: Company,
        test_supplier_user: User,
        second_supplier: User,
    ):
        event = await _create_event(test_client, buyer, visibility="invited")

        blocked = await test_client.post(
            f"/api/v2/sourcing-events/{event['id']}/publish",
            json={"version": event["version"]},
            headers=auth_headers(buyer),
        )
        assert blocked.status_code == 400
        assert "invitation" in blocked.json()["detail"].lower()

        invited = await test_client.post(
            f"/api/v2/sourcing-events/{event['id']}/invitations",
            json={"supplier_company_ids": [test_supplier_company.id]},
            headers=auth_headers(buyer),
        )
        assert invited.status_code == 201, invited.text
        assert invited.json()[0]["supplier_company"]["name"] is not None

        published = await _transition(
            test_client, buyer, event, "publish"
        )
        assert published["status"] == SourcingStatus.PUBLISHED.value

        visible = await test_client.get(
            f"/api/v2/sourcing-events/{event['id']}",
            headers=auth_headers(test_supplier_user),
        )
        assert visible.status_code == 200

        hidden = await test_client.get(
            f"/api/v2/sourcing-events/{event['id']}",
            headers=auth_headers(second_supplier),
        )
        assert hidden.status_code == 403

    async def test_draft_event_is_invisible_to_suppliers(
        self,
        test_client: AsyncClient,
        buyer: User,
        test_supplier_user: User,
    ):
        event = await _create_event(test_client, buyer)

        read = await test_client.get(
            f"/api/v2/sourcing-events/{event['id']}",
            headers=auth_headers(test_supplier_user),
        )
        assert read.status_code == 404

        bid = await _submit_bid(
            test_client,
            test_supplier_user,
            event,
            event["lots"][0],
            ["60", "210"],
        )
        assert bid.status_code == 404

    async def test_requisition_link_requires_approval(
        self,
        test_client: AsyncClient,
        buyer: User,
        test_company: Company,
        test_db_session: AsyncSession,
    ):
        draft = Requisition(
            organization_id=test_company.id,
            requisition_number="REQ-TEST-DRAFT",
            title="Draft demand",
            currency="USD",
            total_amount=Decimal("100"),
            status=RequisitionStatus.DRAFT,
            requested_by_user_id=buyer.id,
            version=1,
        )
        approved = Requisition(
            organization_id=test_company.id,
            requisition_number="REQ-TEST-APPROVED",
            title="Approved demand",
            currency="USD",
            total_amount=Decimal("100"),
            status=RequisitionStatus.APPROVED,
            requested_by_user_id=buyer.id,
            version=2,
        )
        test_db_session.add_all([draft, approved])
        await test_db_session.commit()
        await test_db_session.refresh(draft)
        await test_db_session.refresh(approved)

        rejected = await test_client.post(
            "/api/v2/sourcing-events",
            json={**event_payload(), "requisition_id": draft.id},
            headers=auth_headers(buyer),
        )
        assert rejected.status_code == 409

        response = await test_client.post(
            "/api/v2/sourcing-events",
            json={**event_payload(), "requisition_id": approved.id},
            headers=auth_headers(buyer),
        )
        assert response.status_code == 201, response.text
        assert response.json()["requisition_id"] == approved.id


class TestSealedBids:
    async def test_sealed_bid_hidden_until_open(
        self,
        test_client: AsyncClient,
        buyer: User,
        test_supplier_user: User,
    ):
        event = await _published_public_event(test_client, buyer)
        lot = event["lots"][0]

        submitted = await _submit_bid(
            test_client, test_supplier_user, event, lot, ["60", "210"]
        )
        assert submitted.status_code == 201, submitted.text
        bid = submitted.json()
        assert Decimal(bid["total_amount"]) == Decimal("1650")

        duplicate = await _submit_bid(
            test_client, test_supplier_user, event, lot, ["60", "210"]
        )
        assert duplicate.status_code == 409

        receipts = await test_client.get(
            f"/api/v2/sourcing-events/{event['id']}/bids",
            headers=auth_headers(buyer),
        )
        assert receipts.status_code == 200, receipts.text
        assert len(receipts.json()) == 1
        assert receipts.json()[0]["sealed"] is True
        assert receipts.json()[0]["total_amount"] is None
        assert receipts.json()[0]["lines"] == []

        own = await test_client.get(
            f"/api/v2/sourcing-events/{event['id']}/bids",
            headers=auth_headers(test_supplier_user),
        )
        assert own.json()[0]["sealed"] is False
        assert Decimal(own.json()[0]["total_amount"]) == Decimal("1650")
        assert len(own.json()[0]["lines"]) == 2

        closed = await _transition(test_client, buyer, event, "close")
        await _transition(test_client, buyer, closed, "open")

        revealed = await test_client.get(
            f"/api/v2/sourcing-events/{event['id']}/bids",
            headers=auth_headers(buyer),
        )
        assert revealed.json()[0]["sealed"] is False
        assert Decimal(revealed.json()[0]["total_amount"]) == Decimal("1650")
        assert len(revealed.json()[0]["lines"]) == 2

    async def test_two_suppliers_see_only_their_own_bids(
        self,
        test_client: AsyncClient,
        buyer: User,
        test_supplier_user: User,
        second_supplier: User,
    ):
        event = await _published_public_event(test_client, buyer)
        lot = event["lots"][0]

        first = await _submit_bid(
            test_client, test_supplier_user, event, lot, ["60", "210"]
        )
        second = await _submit_bid(
            test_client, second_supplier, event, lot, ["55", "200"]
        )
        assert first.status_code == 201
        assert second.status_code == 201

        first_view = await test_client.get(
            f"/api/v2/sourcing-events/{event['id']}/bids",
            headers=auth_headers(test_supplier_user),
        )
        assert len(first_view.json()) == 1
        assert first_view.json()[0]["supplier_company_id"] == (
            test_supplier_user.company_id
        )

        buyer_view = await test_client.get(
            f"/api/v2/sourcing-events/{event['id']}/bids",
            headers=auth_headers(buyer),
        )
        assert len(buyer_view.json()) == 2
        assert all(item["sealed"] for item in buyer_view.json())

        closed = await _transition(test_client, buyer, event, "close")
        await _transition(test_client, buyer, closed, "open")
        revealed = await test_client.get(
            f"/api/v2/sourcing-events/{event['id']}/bids",
            headers=auth_headers(buyer),
        )
        totals = {
            item["supplier_company_id"]: Decimal(str(item["total_amount"]))
            for item in revealed.json()
        }
        assert totals[test_supplier_user.company_id] == Decimal("1650")
        assert totals[second_supplier.company_id] == Decimal("1550")

    async def test_withdraw_and_resubmit(
        self,
        test_client: AsyncClient,
        buyer: User,
        test_supplier_user: User,
    ):
        event = await _published_public_event(test_client, buyer)
        lot = event["lots"][0]

        submitted = (
            await _submit_bid(
                test_client, test_supplier_user, event, lot, ["60", "210"]
            )
        ).json()

        withdrawn = await test_client.post(
            f"/api/v2/sourcing-events/{event['id']}/bids/{submitted['id']}/withdraw",
            json={"version": submitted["version"]},
            headers=auth_headers(test_supplier_user),
        )
        assert withdrawn.status_code == 200, withdrawn.text
        assert withdrawn.json()["status"] == "withdrawn"

        resubmitted = await _submit_bid(
            test_client, test_supplier_user, event, lot, ["55", "200"]
        )
        assert resubmitted.status_code == 201, resubmitted.text
        assert Decimal(resubmitted.json()["total_amount"]) == Decimal("1550")
        assert resubmitted.json()["id"] == submitted["id"]

        stale = await test_client.post(
            f"/api/v2/sourcing-events/{event['id']}/bids/{submitted['id']}/withdraw",
            json={"version": submitted["version"]},
            headers=auth_headers(test_supplier_user),
        )
        assert stale.status_code == 409

    async def test_every_lot_line_must_be_quoted(
        self,
        test_client: AsyncClient,
        buyer: User,
        test_supplier_user: User,
    ):
        event = await _published_public_event(test_client, buyer)
        lot = event["lots"][0]
        other_lot = event["lots"][1]

        partial = await test_client.post(
            f"/api/v2/sourcing-events/{event['id']}/lots/{lot['id']}/bids",
            json={
                "lines": [
                    {
                        "sourcing_line_id": lot["lines"][0]["id"],
                        "unit_price": "60",
                    }
                ]
            },
            headers=auth_headers(test_supplier_user),
        )
        assert partial.status_code == 400
        assert "every line" in partial.json()["detail"].lower()

        wrong_lot = await test_client.post(
            f"/api/v2/sourcing-events/{event['id']}/lots/{lot['id']}/bids",
            json={
                "lines": [
                    {
                        "sourcing_line_id": lot["lines"][0]["id"],
                        "unit_price": "60",
                    },
                    {
                        "sourcing_line_id": other_lot["lines"][0]["id"],
                        "unit_price": "3",
                    },
                ]
            },
            headers=auth_headers(test_supplier_user),
        )
        assert wrong_lot.status_code == 400
        assert "does not belong" in wrong_lot.json()["detail"]


class TestInvitationResponses:
    async def test_decline_blocks_bidding_and_accept_allows(
        self,
        test_client: AsyncClient,
        buyer: User,
        test_supplier_company: Company,
        test_supplier_user: User,
        second_supplier: User,
    ):
        event = await _create_event(test_client, buyer, visibility="invited")
        invited = await test_client.post(
            f"/api/v2/sourcing-events/{event['id']}/invitations",
            json={
                "supplier_company_ids": [
                    test_supplier_company.id,
                    second_supplier.company_id,
                ]
            },
            headers=auth_headers(buyer),
        )
        assert invited.status_code == 201, invited.text
        by_company = {
            item["supplier_company_id"]: item["id"]
            for item in invited.json()
        }

        published = await _transition(
            test_client, buyer, event, "publish"
        )
        lot = published["lots"][0]

        declined = await test_client.post(
            f"/api/v2/sourcing-events/{event['id']}/invitations/"
            f"{by_company[test_supplier_company.id]}/respond",
            json={"decision": "decline"},
            headers=auth_headers(test_supplier_user),
        )
        assert declined.status_code == 200, declined.text
        assert declined.json()["status"] == "declined"

        blocked = await _submit_bid(
            test_client, test_supplier_user, published, lot, ["60", "210"]
        )
        assert blocked.status_code == 403
        assert "declined" in blocked.json()["detail"].lower()

        accepted = await test_client.post(
            f"/api/v2/sourcing-events/{event['id']}/invitations/"
            f"{by_company[second_supplier.company_id]}/respond",
            json={"decision": "accept"},
            headers=auth_headers(second_supplier),
        )
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "accepted"

        bid = await _submit_bid(
            test_client, second_supplier, published, lot, ["55", "200"]
        )
        assert bid.status_code == 201, bid.text


class TestQnAAndAddenda:
    async def test_question_visibility_and_answers(
        self,
        test_client: AsyncClient,
        buyer: User,
        test_supplier_user: User,
        second_supplier: User,
    ):
        event = await _published_public_event(test_client, buyer)

        asked = await test_client.post(
            f"/api/v2/sourcing-events/{event['id']}/questions",
            json={"question": "Are refurbished chairs allowed?"},
            headers=auth_headers(test_supplier_user),
        )
        assert asked.status_code == 201, asked.text
        question_id = asked.json()["id"]

        # Another supplier cannot see an unanswered question.
        hidden = await test_client.get(
            f"/api/v2/sourcing-events/{event['id']}/questions",
            headers=auth_headers(second_supplier),
        )
        assert hidden.json() == []

        answered = await test_client.post(
            f"/api/v2/sourcing-events/{event['id']}/questions/"
            f"{question_id}/answer",
            json={"answer": "Yes, grade A refurbished is acceptable."},
            headers=auth_headers(buyer),
        )
        assert answered.status_code == 200, answered.text
        assert answered.json()["answer"].startswith("Yes")

        visible = await test_client.get(
            f"/api/v2/sourcing-events/{event['id']}/questions",
            headers=auth_headers(second_supplier),
        )
        assert len(visible.json()) == 1

        private = await test_client.post(
            f"/api/v2/sourcing-events/{event['id']}/questions",
            json={"question": "Can we invoice in EUR?", "is_public": False},
            headers=auth_headers(second_supplier),
        )
        assert private.status_code == 201

        first_supplier_view = await test_client.get(
            f"/api/v2/sourcing-events/{event['id']}/questions",
            headers=auth_headers(test_supplier_user),
        )
        assert len(first_supplier_view.json()) == 1

        buyer_view = await test_client.get(
            f"/api/v2/sourcing-events/{event['id']}/questions",
            headers=auth_headers(buyer),
        )
        assert len(buyer_view.json()) == 2

    async def test_addendum_extends_closing(
        self,
        test_client: AsyncClient,
        buyer: User,
        test_supplier_user: User,
    ):
        event = await _published_public_event(test_client, buyer)
        original_closing = dt.datetime.fromisoformat(event["closing_at"])
        extended = original_closing + dt.timedelta(days=2)

        created = await test_client.post(
            f"/api/v2/sourcing-events/{event['id']}/addenda",
            json={
                "version": event["version"],
                "title": "Deadline extension",
                "body": "Bidding is extended by two days.",
                "extended_closing_at": extended.isoformat(),
            },
            headers=auth_headers(buyer),
        )
        assert created.status_code == 201, created.text
        assert created.json()["addendum_number"] == 1

        refreshed = await test_client.get(
            f"/api/v2/sourcing-events/{event['id']}",
            headers=auth_headers(buyer),
        )
        assert dt.datetime.fromisoformat(
            refreshed.json()["closing_at"]
        ) == extended
        assert refreshed.json()["version"] == event["version"] + 1

        shorter = await test_client.post(
            f"/api/v2/sourcing-events/{event['id']}/addenda",
            json={
                "version": refreshed.json()["version"],
                "title": "Too late",
                "body": "This should fail.",
                "extended_closing_at": original_closing.isoformat(),
            },
            headers=auth_headers(buyer),
        )
        assert shorter.status_code == 400

        second = await test_client.post(
            f"/api/v2/sourcing-events/{event['id']}/addenda",
            json={
                "version": refreshed.json()["version"],
                "title": "Clarification only",
                "body": "No deadline change.",
            },
            headers=auth_headers(buyer),
        )
        assert second.status_code == 201
        assert second.json()["addendum_number"] == 2

        supplier_view = await test_client.get(
            f"/api/v2/sourcing-events/{event['id']}/addenda",
            headers=auth_headers(test_supplier_user),
        )
        assert len(supplier_view.json()) == 2
