"""Explicit lifecycle rules for requisitions.

Business state is never assigned ad hoc; every change goes through
``ensure_transition`` so illegal moves surface as 409s instead of corrupt rows.
"""

from app.models.procurement import RequisitionStatus
from app.services.procurement.errors import InvalidState


REQUISITION_TRANSITIONS: dict[RequisitionStatus, set[RequisitionStatus]] = {
    RequisitionStatus.DRAFT: {
        RequisitionStatus.IN_APPROVAL,
        RequisitionStatus.CANCELLED,
    },
    RequisitionStatus.IN_APPROVAL: {
        RequisitionStatus.APPROVED,
        RequisitionStatus.REJECTED,
        RequisitionStatus.CANCELLED,
    },
    RequisitionStatus.APPROVED: set(),
    RequisitionStatus.REJECTED: set(),
    RequisitionStatus.CANCELLED: set(),
}


def ensure_transition(
    current: RequisitionStatus, target: RequisitionStatus
) -> None:
    if target not in REQUISITION_TRANSITIONS[current]:
        raise InvalidState(
            f"Cannot move requisition from '{current.value}' to '{target.value}'"
        )
