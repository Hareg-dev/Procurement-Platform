"""Clarification questions, answers and published addenda."""

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import User, utcnow
from app.models.sourcing import (
    SourcingAddendum,
    SourcingQuestion,
    SourcingStatus,
)
from app.models.sourcing_schemas import (
    AddendumCreate,
    QuestionAnswerRequest,
    QuestionCreate,
)
from app.services.procurement import audit
from app.services.procurement.errors import (
    DomainError,
    InvalidState,
    NotFoundError,
    VersionConflict,
)
from app.services.sourcing.access import (
    ensure_buyer_role,
    ensure_buying_org,
    ensure_supplier_can_view,
    get_membership,
)
from app.services.sourcing.events import _require_event, _snapshot


class SourcingQnAService:
    async def ask(
        self,
        db: AsyncSession,
        *,
        user: User,
        event_id: int,
        payload: QuestionCreate,
    ) -> SourcingQuestion:
        event = await _require_event(db, event_id)
        await ensure_supplier_can_view(db, event=event, user=user)

        if event.status != SourcingStatus.PUBLISHED:
            raise InvalidState(
                "Questions can only be asked while the event is open"
            )
        now = utcnow()
        if event.closing_at <= now:
            raise InvalidState("Bidding has closed for this event")
        if (
            event.questions_deadline is not None
            and now > event.questions_deadline
        ):
            raise InvalidState("The question period has closed")

        question = SourcingQuestion(
            event_id=event.id,
            supplier_company_id=user.company_id,
            asked_by_user_id=user.id,
            question=payload.question,
            is_public=payload.is_public,
        )
        db.add(question)
        await db.flush()

        audit.record_audit(
            db,
            organization_id=event.organization_id,
            actor=user,
            action="sourcing.question_asked",
            entity_type="sourcing_question",
            entity_id=question.id,
            after={
                "event_id": event.id,
                "supplier_company_id": user.company_id,
                "is_public": question.is_public,
            },
        )
        await db.commit()
        await db.refresh(question)
        return question

    async def answer(
        self,
        db: AsyncSession,
        *,
        member,
        event_id: int,
        question_id: int,
        payload: QuestionAnswerRequest,
    ) -> SourcingQuestion:
        ensure_buyer_role(member)
        event = await _require_event(db, event_id)
        ensure_buying_org(member, event)

        question = await db.get(SourcingQuestion, question_id)
        if question is None or question.event_id != event.id:
            raise NotFoundError("Question not found")
        if question.answer is not None:
            raise InvalidState("This question has already been answered")

        question.answer = payload.answer
        question.answered_by_user_id = member.user_id
        question.answered_at = utcnow()
        question.is_public = payload.is_public

        audit.record_audit(
            db,
            organization_id=event.organization_id,
            actor=member.user,
            action="sourcing.question_answered",
            entity_type="sourcing_question",
            entity_id=question.id,
            after={
                "event_id": event.id,
                "is_public": question.is_public,
            },
        )
        audit.emit_event(
            db,
            organization_id=event.organization_id,
            event_type="sourcing.question_answered",
            aggregate_type="sourcing_event",
            aggregate_id=event.id,
            payload={"question_id": question.id},
        )
        await db.commit()
        await db.refresh(question)
        return question

    async def list_questions(
        self, db: AsyncSession, *, user: User, event_id: int
    ) -> list[SourcingQuestion]:
        event = await _require_event(db, event_id)

        membership = await get_membership(
            db, user_id=user.id, organization_id=event.organization_id
        )
        if membership is not None:
            stmt = select(SourcingQuestion).where(
                SourcingQuestion.event_id == event.id
            )
        else:
            await ensure_supplier_can_view(db, event=event, user=user)
            # Other suppliers' unanswered private questions stay private.
            stmt = select(SourcingQuestion).where(
                SourcingQuestion.event_id == event.id,
                or_(
                    and_(
                        SourcingQuestion.is_public.is_(True),
                        SourcingQuestion.answer.is_not(None),
                    ),
                    SourcingQuestion.supplier_company_id == user.company_id,
                ),
            )

        stmt = stmt.order_by(SourcingQuestion.asked_at.asc())
        return list((await db.execute(stmt)).scalars().all())

    async def create_addendum(
        self,
        db: AsyncSession,
        *,
        member,
        event_id: int,
        payload: AddendumCreate,
    ) -> SourcingAddendum:
        ensure_buyer_role(member)
        event = await _require_event(db, event_id, lock=True)
        ensure_buying_org(member, event)

        if event.version != payload.version:
            raise VersionConflict(
                "Sourcing event was modified by someone else; reload and retry"
            )
        if event.status != SourcingStatus.PUBLISHED:
            raise InvalidState(
                "Addenda can only be published while the event is open"
            )

        now = utcnow()
        if payload.extended_closing_at is not None:
            if payload.extended_closing_at <= event.closing_at:
                raise DomainError(
                    "extended_closing_at must be later than the current "
                    "deadline"
                )
            if payload.extended_closing_at <= now:
                raise DomainError(
                    "extended_closing_at must be in the future"
                )

        last_number = await db.scalar(
            select(func.max(SourcingAddendum.addendum_number)).where(
                SourcingAddendum.event_id == event.id
            )
        )
        addendum = SourcingAddendum(
            event_id=event.id,
            addendum_number=(last_number or 0) + 1,
            title=payload.title,
            body=payload.body,
            created_by_user_id=member.user_id,
            extended_closing_at=payload.extended_closing_at,
        )
        db.add(addendum)

        before = _snapshot(event)
        if payload.extended_closing_at is not None:
            event.closing_at = payload.extended_closing_at
        event.version += 1

        audit.record_audit(
            db,
            organization_id=member.organization_id,
            actor=member.user,
            action="sourcing.addendum_published",
            entity_type="sourcing_event",
            entity_id=event.id,
            before=before,
            after={
                **_snapshot(event),
                "addendum_number": addendum.addendum_number,
                "extended_closing_at": payload.extended_closing_at,
            },
        )
        audit.emit_event(
            db,
            organization_id=member.organization_id,
            event_type="sourcing.addendum_published",
            aggregate_type="sourcing_event",
            aggregate_id=event.id,
            payload={
                "addendum_number": addendum.addendum_number,
                "extended_closing_at": payload.extended_closing_at,
            },
        )
        await db.commit()
        await db.refresh(addendum)
        return addendum

    async def list_addenda(
        self, db: AsyncSession, *, user: User, event_id: int
    ) -> list[SourcingAddendum]:
        event = await _require_event(db, event_id)

        membership = await get_membership(
            db, user_id=user.id, organization_id=event.organization_id
        )
        if membership is None:
            await ensure_supplier_can_view(db, event=event, user=user)

        stmt = (
            select(SourcingAddendum)
            .where(SourcingAddendum.event_id == event.id)
            .order_by(SourcingAddendum.addendum_number.asc())
        )
        return list((await db.execute(stmt)).scalars().all())


sourcing_qna_service = SourcingQnAService()
