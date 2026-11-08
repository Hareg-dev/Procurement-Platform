"""Explicit lifecycle rules for sourcing events."""

from app.models.sourcing import SourcingStatus
from app.services.procurement.errors import InvalidState


SOURCING_TRANSITIONS: dict[SourcingStatus, set[SourcingStatus]] = {
    SourcingStatus.DRAFT: {
        SourcingStatus.PUBLISHED,
        SourcingStatus.CANCELLED,
    },
    SourcingStatus.PUBLISHED: {
        SourcingStatus.CLOSED,
        SourcingStatus.CANCELLED,
    },
    SourcingStatus.CLOSED: {
        SourcingStatus.OPENED,
        SourcingStatus.CANCELLED,
    },
    SourcingStatus.OPENED: {
        SourcingStatus.EVALUATING,
        SourcingStatus.AWARDED,
        SourcingStatus.CANCELLED,
    },
    SourcingStatus.EVALUATING: {
        SourcingStatus.AWARDED,
        SourcingStatus.CANCELLED,
    },
    SourcingStatus.AWARDED: set(),
    SourcingStatus.CANCELLED: set(),
}


def ensure_transition(
    current: SourcingStatus, target: SourcingStatus
) -> None:
    if target not in SOURCING_TRANSITIONS[current]:
        raise InvalidState(
            f"Cannot move sourcing event from '{current.value}' "
            f"to '{target.value}'"
        )
