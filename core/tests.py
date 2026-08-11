"""Core application tests."""

import os
from datetime import UTC, datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from integrations.healthchecks import Healthcheck, HealthchecksSnapshot
from integrations.kopia import KopiaAttempt, KopiaSnapshot, KopiaStatus
from integrations.netbird import NetBirdPeer, NetBirdSnapshot
from integrations.registry import integration_statuses


class CoreViewTests(TestCase):
    def test_health_endpoint_is_public_and_minimal(self):
        response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "goreecloud-manager"})

    def test_overview_requires_authentication(self):
        response = self.client.get(reverse("overview"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_authenticated_user_can_open_overview(self):
        user = get_user_model().objects.create_user(
            username="admin-test",
            password="strong-test-password",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("overview"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "GoreeCloud Manager")
        self.assertContains(response, "NetBird")
        self.assertContains(response, "Healthchecks")
        self.assertContains(response, "Kopia")

    @patch("core.views.netbird_snapshot")
    def test_authenticated_overview_renders_live_netbird_peer(self, mocked_snapshot):
        mocked_snapshot.return_value = NetBirdSnapshot(
            state="healthy",
            detail="Live read-only API data verified for 1 peer(s).",
            peers=(
                NetBirdPeer(
                    peer_id="peer-1",
                    name="goreecloud-test-peer",
                    dns_label="goreecloud-test-peer.netbird.selfhosted",
                    ip="100.64.0.1",
                    ipv6="fd00::1",
                    connected=True,
                    last_seen=datetime(2026, 8, 11, 7, 0, tzinfo=UTC),
                    os="linux",
                    version="0.58.2",
                ),
            ),
        )
        user = get_user_model().objects.create_user(
            username="netbird-admin-test",
            password="strong-test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("overview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "goreecloud-test-peer")
        self.assertContains(response, "100.64.0.1")
        self.assertContains(response, "Connected")

    @patch("core.views.healthchecks_snapshot")
    def test_authenticated_overview_renders_healthchecks_and_kopia_signal(
        self, mocked_snapshot
    ):
        mocked_snapshot.return_value = HealthchecksSnapshot(
            state="healthy",
            detail="Live read-only API data verified for 1 check(s).",
            checks=(
                Healthcheck(
                    key="stable-key",
                    name="GoreeCloud Kopia Backup",
                    slug="goreecloud-kopia-backup",
                    tags=("goreecloud", "backup", "kopia", "vps"),
                    status="up",
                    started=False,
                    last_ping=datetime(2026, 8, 11, 9, 0, tzinfo=UTC),
                    next_ping=datetime(2026, 8, 12, 9, 0, tzinfo=UTC),
                    timeout=86400,
                    grace=43200,
                    schedule="",
                    timezone="",
                ),
            ),
        )
        user = get_user_model().objects.create_user(
            username="healthchecks-admin-test",
            password="strong-test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("overview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Monitoring visibility")
        self.assertContains(response, "GoreeCloud Kopia Backup", count=2)
        self.assertContains(response, "Protection signal from Healthchecks")
        self.assertContains(response, "1 day")
        self.assertContains(response, "12 hours")

    @patch("core.views.kopia_status")
    def test_authenticated_overview_renders_native_kopia_status(self, mocked_status):
        mocked_status.return_value = KopiaStatus(
            state="healthy",
            detail="Native Kopia status verified from the delegated read-only artifact.",
            generated_at=datetime(2026, 8, 11, 12, 55, tzinfo=UTC),
            artifact_age_seconds=300,
            source_host="goreecloud-vps-01",
            source_label="GoreeCloud VPS protected data",
            repository_state="ok",
            repository_checked_at=datetime(2026, 8, 11, 12, 55, tzinfo=UTC),
            latest_attempt=KopiaAttempt(
                state="success",
                at=datetime(2026, 8, 11, 3, 33, 30, tzinfo=UTC),
                reason="snapshot-created",
            ),
            latest_snapshot=KopiaSnapshot(
                snapshot_id="c068de12bc7b8d042b901bf1020b52d5",
                start_time=datetime(2026, 8, 11, 3, 33, 28, tzinfo=UTC),
                end_time=datetime(2026, 8, 11, 3, 33, 30, tzinfo=UTC),
                description="Scheduled GoreeCloud VPS backup to laptop SFTP repository",
                size_bytes=484991682,
                file_count=1507,
                directory_count=207,
                error_count=0,
                retention_reasons=("latest-1", "daily-1"),
            ),
            snapshot_age_seconds=33990,
        )
        user = get_user_model().objects.create_user(
            username="kopia-admin-test",
            password="strong-test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("overview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Protection visibility")
        self.assertContains(response, "Native Kopia status artifact")
        self.assertContains(response, "c068de12bc7b8d042b901bf1020b52d5")
        self.assertContains(response, "462.5 MiB")
        self.assertContains(response, "1507")
        self.assertContains(response, "Snapshot created")
        self.assertContains(response, "Aug 10, 2026 10:33 PM CDT")
        self.assertContains(response, "neither signal proves restore readiness")


class IntegrationRegistryTests(SimpleTestCase):
    def test_enabled_flag_changes_state_without_returning_token(self):
        with patch.dict(
            os.environ,
            {
                "NETBIRD_ENABLED": "true",
                "NETBIRD_API_TOKEN": "must-never-appear-in-status-output",
            },
            clear=False,
        ):
            statuses = integration_statuses()

        netbird = next(status for status in statuses if status["key"] == "netbird")
        self.assertEqual(netbird["state"], "configured")
        self.assertNotIn("must-never-appear", repr(statuses))

    def test_false_like_or_missing_flags_are_disabled(self):
        with patch.dict(os.environ, {"NETBIRD_ENABLED": "false"}, clear=False):
            statuses = integration_statuses()

        netbird = next(status for status in statuses if status["key"] == "netbird")
        self.assertEqual(netbird["state"], "disabled")

    def test_live_netbird_status_overrides_configuration_placeholder(self):
        statuses = integration_statuses(
            netbird_status={
                "state": "healthy",
                "detail": "Live read-only API data verified for 1 peer(s).",
            }
        )
        netbird = next(status for status in statuses if status["key"] == "netbird")
        self.assertEqual(netbird["state"], "healthy")

    def test_live_healthchecks_status_overrides_configuration_placeholder(self):
        statuses = integration_statuses(
            healthchecks_status={
                "state": "degraded",
                "detail": "Live data verified; 1 check requires attention.",
            }
        )
        healthchecks = next(
            status for status in statuses if status["key"] == "healthchecks"
        )
        self.assertEqual(healthchecks["state"], "degraded")

    def test_live_kopia_status_overrides_configuration_placeholder(self):
        statuses = integration_statuses(
            kopia_status={
                "state": "degraded",
                "detail": "Native Kopia status verified; latest attempt was skipped.",
            }
        )
        kopia = next(status for status in statuses if status["key"] == "kopia")
        self.assertEqual(kopia["state"], "degraded")
