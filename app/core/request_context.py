"""Per-request correlation id shared by middleware and services."""

from contextvars import ContextVar, Token
from typing import Optional
from uuid import uuid4

_request_id: ContextVar[Optional[str]] = ContextVar(
    "request_id", default=None
)

MAX_REQUEST_ID_LENGTH = 64
_ALLOWED_REQUEST_ID_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


def new_request_id() -> str:
    return uuid4().hex


def is_valid_request_id(value: str) -> bool:
    return (
        0 < len(value) <= MAX_REQUEST_ID_LENGTH
        and set(value) <= _ALLOWED_REQUEST_ID_CHARS
    )


def set_request_id(value: Optional[str]) -> Token:
    return _request_id.set(value)


def reset_request_id(token: Token) -> None:
    _request_id.reset(token)


def get_request_id() -> Optional[str]:
    return _request_id.get()
