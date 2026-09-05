"""UI integration tests for bounded Wardveil Security status visibility."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from integrations.wardveil import WardveilEvidence, WardveilSnapshot


class WardveilOverviewTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="wardveil-visibility-admin",
            password="strong-test-password",
        )
        self.client.force_login(user)

    def _snapshot(self, *, outcome="attention", fresh=True):
        now = datetime.now(timezone.utc)
        record = WardveilEvidence(
            subject_kind="service",
            subject_id="goreecloud-manager",
            subject_scope="runtime",
            outcome=outcome,
            observed_at=now - timedelta(minutes=1),
            valid_until=now + timedelta(minutes=10) if fresh else now - timedelta(seconds=1),
            fresh=fresh,
            producer_revision="0123456789abcdef0123456789abcdef01234567",
            summary="Wardveil security-status evidence.",
        )
        return WardveilSnapshot(
            state="available" if fresh else "stale",
            detail="Wardveil producer evidence is available.",
            condition="current" if fresh else "stale-only",
            records=(record,),
            current_count=1 if fresh else 0,
            stale_count=0 if fresh else 1,
        )

    def test_integration_status_surfaces_current_producer_outcome_without_claim_upgrade(self):
        status = self._snapshot(outcome="protected", fresh=True).integration_status()
        self.assertEqual(status["state"], "available")
        self.assertIn("Current Wardveil producer outcomes: Protected (1).", status["detail"])
        self.assertNotIn("Protected by Wardveil", status["detail"])

    def test_stale_outcome_is_labeled_historical(self):
        status = self._snapshot(outcome="protected", fresh=False).integration_status()
        self.assertIn("Historical Wardveil producer outcomes: Protected (1).", status["detail"])
        self.assertNotIn("Current Wardveil producer outcomes", status["detail"])

    @patch("core.views.wardveil_snapshot")
    def test_authenticated_overview_displays_wardveil_integration_and_producer_outcome(
        self,
        mocked_snapshot,
    ):
        mocked_snapshot.return_value = self._snapshot(outcome="attention", fresh=True)
        response = self.client.get(reverse("overview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wardveil Security")
        self.assertContains(response, "Current Wardveil producer outcomes: Attention (1).")
        self.assertNotContains(response, "Protected by Wardveil")
        self.assertTrue(mocked_snapshot.called)
