"""Sanitized authentication event logging for GoreeCloud Manager."""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.http import HttpRequest

from core.request_context import get_request_id

logger = logging.getLogger("core.auth")


def _safe_user_id(user: Any) -> str:
    """Return only the database identifier needed for operator correlation."""

    value = getattr(user, "pk", None)
    return str(value) if value is not None else "-"


@receiver(user_logged_in, dispatch_uid="goreecloud_manager_auth_login_succeeded")
def log_login_success(
    sender: Any,
    request: HttpRequest | None,
    user: Any,
    **kwargs: Any,
) -> None:
    """Record successful authentication without usernames, IPs, or client metadata."""

    logger.info(
        "event=auth_login_succeeded request_id=%s user_id=%s",
        get_request_id(),
        _safe_user_id(user),
    )


@receiver(user_login_failed, dispatch_uid="goreecloud_manager_auth_login_failed")
def log_login_failure(
    sender: Any,
    credentials: dict[str, Any],
    request: HttpRequest | None,
    **kwargs: Any,
) -> None:
    """Record a failed authentication attempt without logging submitted credentials."""

    logger.warning(
        "event=auth_login_failed request_id=%s",
        get_request_id(),
    )


@receiver(user_logged_out, dispatch_uid="goreecloud_manager_auth_logout")
def log_logout(
    sender: Any,
    request: HttpRequest | None,
    user: Any,
    **kwargs: Any,
) -> None:
    """Record logout using only the request correlation ID and internal user ID."""

    logger.info(
        "event=auth_logout request_id=%s user_id=%s",
        get_request_id(),
        _safe_user_id(user),
    )
