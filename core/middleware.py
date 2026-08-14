"""Small request-boundary middleware for GoreeCloud Manager."""

from __future__ import annotations

import logging
from collections.abc import Callable
from uuid import uuid4

from django.conf import settings
from django.db.utils import OperationalError
from django.http import HttpRequest, HttpResponse

from core.request_context import reset_request_id, set_request_id

logger = logging.getLogger(__name__)
_SQLITE_LOCK_MARKERS = (
    "database is locked",
    "database table is locked",
    "database schema is locked",
)


def _is_sqlite_contention(error: OperationalError) -> bool:
    """Recognize transient SQLite lock failures without exposing their raw text."""

    if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
        return False

    message = str(error).casefold()
    return any(marker in message for marker in _SQLITE_LOCK_MARKERS)


class RequestContextMiddleware:
    """Assign a correlation ID and fail softly on transient SQLite contention."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = uuid4().hex
        token = set_request_id(request_id)
        try:
            try:
                response = self.get_response(request)
            except OperationalError as exc:
                if not _is_sqlite_contention(exc):
                    raise

                logger.warning(
                    "event=sqlite_contention request_id=%s action=request_rejected",
                    request_id,
                )
                response = HttpResponse(
                    "Service temporarily unavailable. Please retry.",
                    status=503,
                    content_type="text/plain; charset=utf-8",
                )
                response["Retry-After"] = "1"
                response["Cache-Control"] = "no-store"

            response["X-Request-ID"] = request_id
            return response
        finally:
            reset_request_id(token)
