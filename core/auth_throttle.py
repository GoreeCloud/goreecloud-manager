"""Database-backed administrative login throttling.

The throttle stores only an HMAC-derived account key. Raw submitted usernames, client
addresses, passwords, and request metadata are not persisted here.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import LoginThrottleBucket

MAX_FAILURES = 5


def _account_key(username: str) -> str:
    normalized = username.strip().casefold().encode("utf-8")
    secret = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(secret, normalized, hashlib.sha256).hexdigest()


def _window_seconds() -> int:
    return settings.MANAGER_LOGIN_THROTTLE_WINDOW_SECONDS


def _lock_seconds() -> int:
    return settings.MANAGER_LOGIN_THROTTLE_LOCK_SECONDS


def is_login_locked(username: str) -> bool:
    if not username.strip():
        return False

    bucket = LoginThrottleBucket.objects.filter(key=_account_key(username)).first()
    if bucket is None or bucket.locked_until is None:
        return False
    return bucket.locked_until > timezone.now()


def register_login_failure(username: str) -> None:
    if not username.strip():
        return

    now = timezone.now()
    window_start = now - timedelta(seconds=_window_seconds())
    key = _account_key(username)

    with transaction.atomic():
        bucket = LoginThrottleBucket.objects.filter(key=key).first()
        if bucket is None:
            LoginThrottleBucket.objects.create(
                key=key,
                failures=1,
                window_started_at=now,
            )
            return

        if bucket.locked_until and bucket.locked_until > now:
            return

        if bucket.window_started_at < window_start:
            bucket.failures = 1
            bucket.window_started_at = now
            bucket.locked_until = None
        else:
            bucket.failures += 1
            if bucket.failures >= MAX_FAILURES:
                bucket.locked_until = now + timedelta(seconds=_lock_seconds())

        bucket.save(update_fields=("failures", "window_started_at", "locked_until", "updated_at"))


def clear_login_failures(username: str) -> None:
    if username.strip():
        LoginThrottleBucket.objects.filter(key=_account_key(username)).delete()
