"""Domain errors mapped to HTTP responses by a single app-level handler."""


class DomainError(Exception):
    status_code = 400


class NotFoundError(DomainError):
    status_code = 404


class PermissionDenied(DomainError):
    status_code = 403


class InvalidState(DomainError):
    status_code = 409


class VersionConflict(DomainError):
    status_code = 409
