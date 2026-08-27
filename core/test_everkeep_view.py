"""Authenticated Everkeep detail-surface tests."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from integrations.everkeep import EverkeepCapability, EverkeepSnapshot


class EverkeepDetailViewTests(TestCase):
    def test_everkeep_detail_requires_authentication(self):
        response = self.client.get(reverse("everkeep"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    @patch("core.everkeep_views.everkeep_snapshot")
    def test_authenticated_view_renders_sanitized_resilience_state(self, mocked_snapshot):
        mocked_snapshot.return_value = EverkeepSnapshot(
            state="ready",
            detail="Adapter detail must not become the primary healthy-state presentation.",
            producer="GoreeCloud/Everkeep",
            generated_at="2026-08-27T17:00:00Z",
            recovery_readiness="verified",
            backup_verification="verified",
            backup_verification_age_seconds=7_200,
            portability_continuity="pending",
            preservation="verified",
            capabilities=(
                EverkeepCapability(id="backup-integrity", state="verified"),
                EverkeepCapability(id="private-looking-capability-id", state="attention"),
            ),
            production_approved=False,
        )
        user = get_user_model().objects.create_user(
            username="everkeep-admin-test",
            password="strong-test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("everkeep"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Everkeep")
        self.assertContains(response, "Recovery readiness")
        self.assertContains(response, "Backup integrity")
        self.assertContains(response, "Additional resilience capability")
        self.assertContains(response, "2 hours ago")
        self.assertContains(response, "Runtime acceptance required")
        self.assertContains(response, "Read only")
        self.assertNotContains(response, "private-looking-capability-id")
        self.assertNotContains(
            response,
            "Adapter detail must not become the primary healthy-state presentation.",
        )

    @patch("core.everkeep_views.everkeep_snapshot")
    def test_unavailable_view_keeps_contained_diagnostic_detail(self, mocked_snapshot):
        mocked_snapshot.return_value = EverkeepSnapshot(
            state="unavailable",
            detail="Configured Everkeep status file is unavailable.",
        )
        user = get_user_model().objects.create_user(
            username="everkeep-unavailable-test",
            password="strong-test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("everkeep"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Configured Everkeep status file is unavailable.")
        self.assertContains(response, "Not reported")
