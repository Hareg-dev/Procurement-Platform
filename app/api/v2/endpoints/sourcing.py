from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_active_user
from app.api.v2.deps import get_org_member, require_org_roles
from app.core.db import get_db
from app.models.orm import User
from app.models.procurement import OrgRole
from app.models.procurement_schemas import VersionedRequest
from app.models.sourcing import SourcingStatus
from app.models.sourcing_schemas import (
    AddendumCreate,
    AddendumResponse,
    BidResponse,
    BidSubmitRequest,
    BidWithdrawRequest,
    InvitationBatchCreate,
    InvitationResponse,
    InvitationRespondRequest,
    QuestionAnswerRequest,
    QuestionCreate,
    QuestionResponse,
    SourcingEventCreate,
    SourcingEventResponse,
    SourcingEventSummary,
    SourcingEventUpdate,
    SourcingLotsReplace,
)
from app.services.sourcing.bids import sourcing_bid_service
from app.services.sourcing.events import sourcing_event_service
from app.services.sourcing.qna import sourcing_qna_service

router = APIRouter(prefix="/sourcing-events", tags=["v2-sourcing"])

can_manage_events = require_org_roles(OrgRole.BUYER, OrgRole.ORG_ADMIN)


@router.post(
    "",
    response_model=SourcingEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft sourcing event with lots and lines",
)
async def create_sourcing_event(
    payload: SourcingEventCreate,
    member=Depends(can_manage_events),
    db: AsyncSession = Depends(get_db),
) -> SourcingEventResponse:
    return await sourcing_event_service.create(
        db, member=member, creator=member.user, payload=payload
    )


@router.get(
    "",
    response_model=list[SourcingEventSummary],
    summary="List the caller organization's sourcing events",
)
async def list_sourcing_events(
    status_filter: Optional[SourcingStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member=Depends(get_org_member),
    db: AsyncSession = Depends(get_db),
) -> list[SourcingEventSummary]:
    return await sourcing_event_service.list_for_org(
        db,
        organization_id=member.organization_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/opportunities",
    response_model=list[SourcingEventSummary],
    summary="List open opportunities for the caller's supplier organization",
)
async def list_opportunities(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[SourcingEventSummary]:
    return await sourcing_event_service.list_opportunities(
        db, user=current_user, limit=limit, offset=offset
    )


@router.get(
    "/{event_id}",
    response_model=SourcingEventResponse,
    summary="Get a sourcing event (buyer organization or eligible supplier)",
)
async def get_sourcing_event(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SourcingEventResponse:
    return await sourcing_event_service.get_for_user(
        db, user=current_user, event_id=event_id
    )


@router.patch(
    "/{event_id}",
    response_model=SourcingEventResponse,
    summary="Edit a draft sourcing event header",
)
async def update_sourcing_event(
    event_id: int,
    payload: SourcingEventUpdate,
    member=Depends(can_manage_events),
    db: AsyncSession = Depends(get_db),
) -> SourcingEventResponse:
    return await sourcing_event_service.update(
        db, member=member, event_id=event_id, payload=payload
    )


@router.put(
    "/{event_id}/lots",
    response_model=SourcingEventResponse,
    summary="Replace all lots and requirement lines on a draft event",
)
async def replace_sourcing_lots(
    event_id: int,
    payload: SourcingLotsReplace,
    member=Depends(can_manage_events),
    db: AsyncSession = Depends(get_db),
) -> SourcingEventResponse:
    return await sourcing_event_service.replace_lots(
        db, member=member, event_id=event_id, payload=payload
    )


@router.post(
    "/{event_id}/publish",
    response_model=SourcingEventResponse,
    summary="Publish an event so suppliers can bid",
)
async def publish_sourcing_event(
    event_id: int,
    payload: VersionedRequest,
    member=Depends(can_manage_events),
    db: AsyncSession = Depends(get_db),
) -> SourcingEventResponse:
    return await sourcing_event_service.publish(
        db, member=member, event_id=event_id, version=payload.version
    )


@router.post(
    "/{event_id}/close",
    response_model=SourcingEventResponse,
    summary="Stop accepting bids",
)
async def close_sourcing_event(
    event_id: int,
    payload: VersionedRequest,
    member=Depends(can_manage_events),
    db: AsyncSession = Depends(get_db),
) -> SourcingEventResponse:
    return await sourcing_event_service.close(
        db, member=member, event_id=event_id, version=payload.version
    )


@router.post(
    "/{event_id}/open",
    response_model=SourcingEventResponse,
    summary="Open a closed event and reveal sealed bids",
)
async def open_sourcing_event(
    event_id: int,
    payload: VersionedRequest,
    member=Depends(can_manage_events),
    db: AsyncSession = Depends(get_db),
) -> SourcingEventResponse:
    return await sourcing_event_service.open(
        db, member=member, event_id=event_id, version=payload.version
    )


@router.post(
    "/{event_id}/cancel",
    response_model=SourcingEventResponse,
    summary="Cancel an event",
)
async def cancel_sourcing_event(
    event_id: int,
    payload: VersionedRequest,
    member=Depends(can_manage_events),
    db: AsyncSession = Depends(get_db),
) -> SourcingEventResponse:
    return await sourcing_event_service.cancel(
        db, member=member, event_id=event_id, version=payload.version
    )


@router.get(
    "/{event_id}/invitations",
    response_model=list[InvitationResponse],
    summary="List supplier invitations",
)
async def list_invitations(
    event_id: int,
    member=Depends(get_org_member),
    db: AsyncSession = Depends(get_db),
) -> list[InvitationResponse]:
    return await sourcing_event_service.list_invitations(
        db, member=member, event_id=event_id
    )


@router.post(
    "/{event_id}/invitations",
    response_model=list[InvitationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Invite supplier organizations",
)
async def invite_suppliers(
    event_id: int,
    payload: InvitationBatchCreate,
    member=Depends(can_manage_events),
    db: AsyncSession = Depends(get_db),
) -> list[InvitationResponse]:
    return await sourcing_event_service.invite(
        db,
        member=member,
        event_id=event_id,
        supplier_company_ids=payload.supplier_company_ids,
    )


@router.post(
    "/{event_id}/invitations/{invitation_id}/respond",
    response_model=InvitationResponse,
    summary="Accept or decline an invitation (supplier)",
)
async def respond_to_invitation(
    event_id: int,
    invitation_id: int,
    payload: InvitationRespondRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationResponse:
    return await sourcing_event_service.respond_to_invitation(
        db,
        user=current_user,
        event_id=event_id,
        invitation_id=invitation_id,
        payload=payload,
    )


@router.get(
    "/{event_id}/questions",
    response_model=list[QuestionResponse],
    summary="List clarification questions visible to the caller",
)
async def list_questions(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[QuestionResponse]:
    return await sourcing_qna_service.list_questions(
        db, user=current_user, event_id=event_id
    )


@router.post(
    "/{event_id}/questions",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ask a clarification question (supplier)",
)
async def ask_question(
    event_id: int,
    payload: QuestionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> QuestionResponse:
    return await sourcing_qna_service.ask(
        db, user=current_user, event_id=event_id, payload=payload
    )


@router.post(
    "/{event_id}/questions/{question_id}/answer",
    response_model=QuestionResponse,
    summary="Answer a clarification question",
)
async def answer_question(
    event_id: int,
    question_id: int,
    payload: QuestionAnswerRequest,
    member=Depends(can_manage_events),
    db: AsyncSession = Depends(get_db),
) -> QuestionResponse:
    return await sourcing_qna_service.answer(
        db,
        member=member,
        event_id=event_id,
        question_id=question_id,
        payload=payload,
    )


@router.get(
    "/{event_id}/addenda",
    response_model=list[AddendumResponse],
    summary="List published addenda",
)
async def list_addenda(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[AddendumResponse]:
    return await sourcing_qna_service.list_addenda(
        db, user=current_user, event_id=event_id
    )


@router.post(
    "/{event_id}/addenda",
    response_model=AddendumResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Publish an addendum, optionally extending the deadline",
)
async def create_addendum(
    event_id: int,
    payload: AddendumCreate,
    member=Depends(can_manage_events),
    db: AsyncSession = Depends(get_db),
) -> AddendumResponse:
    return await sourcing_qna_service.create_addendum(
        db, member=member, event_id=event_id, payload=payload
    )


@router.post(
    "/{event_id}/lots/{lot_id}/bids",
    response_model=BidResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a priced bid for one lot (supplier)",
)
async def submit_bid(
    event_id: int,
    lot_id: int,
    payload: BidSubmitRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> BidResponse:
    return await sourcing_bid_service.submit(
        db,
        user=current_user,
        event_id=event_id,
        lot_id=lot_id,
        payload=payload,
    )


@router.get(
    "/{event_id}/bids",
    response_model=list[BidResponse],
    summary="List bids visible to the caller (sealed-aware)",
)
async def list_bids(
    event_id: int,
    lot_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[BidResponse]:
    return await sourcing_bid_service.list_for_user(
        db,
        user=current_user,
        event_id=event_id,
        lot_id=lot_id,
    )


@router.get(
    "/{event_id}/lots/{lot_id}/bids",
    response_model=list[BidResponse],
    summary="List bids for a lot (sealed-aware)",
)
async def list_lot_bids(
    event_id: int,
    lot_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[BidResponse]:
    return await sourcing_bid_service.list_for_user(
        db, user=current_user, event_id=event_id, lot_id=lot_id
    )


@router.post(
    "/{event_id}/bids/{bid_id}/withdraw",
    response_model=BidResponse,
    summary="Withdraw a submitted bid before the deadline (supplier)",
)
async def withdraw_bid(
    event_id: int,
    bid_id: int,
    payload: BidWithdrawRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> BidResponse:
    return await sourcing_bid_service.withdraw(
        db,
        user=current_user,
        event_id=event_id,
        bid_id=bid_id,
        payload=payload,
    )
