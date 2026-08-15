"""Authentication forms for the private Manager administrative interface."""

from __future__ import annotations

from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .auth_throttle import clear_login_failures, is_login_locked, register_login_failure


class SharedLoginThrottleMixin:
    """Apply shared account-keyed throttling without changing base-form authorization rules."""

    def clean(self):
        username = self.cleaned_data.get("username") or ""
        password = self.cleaned_data.get("password") or ""

        if username and password and is_login_locked(username):
            raise ValidationError(
                self.error_messages["invalid_login"],
                code="invalid_login",
                params={"username": self.username_field.verbose_name},
            )

        try:
            cleaned_data = super().clean()
        except ValidationError:
            if username and password:
                register_login_failure(username)
            raise

        clear_login_failures(username)
        return cleaned_data


class ThrottledAuthenticationForm(SharedLoginThrottleMixin, AuthenticationForm):
    """Manager login form with the shared database-backed throttle."""


class ThrottledAdminAuthenticationForm(SharedLoginThrottleMixin, AdminAuthenticationForm):
    """Django admin login form retaining the normal active/staff authorization boundary."""
