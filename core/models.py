"""Manager-owned database models."""

from __future__ import annotations

from django.db import models


class LoginThrottleBucket(models.Model):
    """Pseudonymous shared state for bounded administrative login throttling."""

    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    window_started_at = models.DateTimeField()
    locked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("updated_at",)
        verbose_name = "login throttle bucket"
        verbose_name_plural = "login throttle buckets"
