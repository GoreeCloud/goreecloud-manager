"""Per-request correlation context for GoreeCloud Manager."""

from __future__ import annotations

from contextvars import ContextVar, Token

_REQUEST_ID: ContextVar[str] = ContextVar("goreecloud_manager_request_id", default="-")


def get_request_id() -> str:
    """Return the current server-generated request correlation identifier."""

    return _REQUEST_ID.get()


def set_request_id(request_id: str) -> Token[str]:
    """Set the current request identifier and return the reset token."""

    return _REQUEST_ID.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    """Restore the previous request correlation context."""

    _REQUEST_ID.reset(token)
