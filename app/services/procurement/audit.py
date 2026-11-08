"""Audit trail and transactional outbox.

Both are written through the same session/transaction as the business change,
so a committed state always has its audit row and its event.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.request_context import get_request_id
from app.models.orm import User
from app.models.procurement import ActorType, AuditEvent, OutboxEvent


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def _actor_label(actor: Optional[Any]) -> Optional[str]:
    if isinstance(actor, User):
        return f"{actor.first_name} {actor.last_name} <{actor.email}>"
    if actor is None:
        return None
    return str(actor)


def record_audit(
    db: AsyncSession,
    *,
    organization_id: int,
    actor: Optional[Any],
    action: str,
    entity_type: str,
    entity_id: int,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    correlation_id: Optional[str] = None,
    actor_type: ActorType = ActorType.USER,
) -> AuditEvent:
    event = AuditEvent(
        organization_id=organization_id,
        actor_type=actor_type,
        actor_user_id=getattr(actor, "id", None),
        actor_label=_actor_label(actor),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=_jsonable(before) if before is not None else None,
        after=_jsonable(after) if after is not None else None,
        correlation_id=correlation_id or get_request_id(),
    )
    db.add(event)
    return event


def emit_event(
    db: AsyncSession,
    *,
    organization_id: int,
    event_type: str,
    aggregate_type: str,
    aggregate_id: int,
    payload: Optional[dict] = None,
) -> OutboxEvent:
    event = OutboxEvent(
        organization_id=organization_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=_jsonable(payload or {}),
    )
    db.add(event)
    return event


def requisition_snapshot(requisition: Any) -> dict:
    return {
        "requisition_number": requisition.requisition_number,
        "status": requisition.status,
        "title": requisition.title,
        "currency": requisition.currency,
        "total_amount": requisition.total_amount,
        "cost_center": requisition.cost_center,
        "version": requisition.version,
    }
