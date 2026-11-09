"""Agent-specific domain errors."""

from app.services.procurement.errors import DomainError


class AgentUnavailable(DomainError):
    status_code = 503


class AgentRunFailed(DomainError):
    status_code = 502
