"""Authenticated overview rendering tests for Beszel resource visibility."""

from datetime import UTC, datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from integrations.beszel import BeszelContainer, BeszelDetails, BeszelStats, BeszelStatus


class BeszelOverviewTests(TestCase):
    @patch("core.views.beszel_status")
    def test_authenticated_overview_renders_sanitized_beszel_resources(self, mocked_status):
        observed = datetime(2026, 8, 11, 22, 35, tzinfo=UTC)
        mocked_status.return_value = BeszelStatus(
            state="healthy",
            detail="Native Beszel resource data verified from the delegated read-only artifact for 1 container(s).",
            generated_at=observed,
            artifact_age_seconds=30,
            collector_state="ok",
            collector_checked_at=observed,
            beszel_version="0.18.7",
            source_name="goreecloud-vps-01",
            source_status="up",
            source_updated_at=observed,
            agent_version="0.18.7",
            stats=BeszelStats(
                observed_at=observed,
                cpu_percent=5.03,
                load_average=(0.1, 0.2, 0.3),
                memory_total_gb=7.58,
                memory_used_gb=4.18,
                memory_percent=55.19,
                swap_total_gb=2.0,
                swap_used_gb=0.11,
                disk_total_gb=73.62,
                disk_used_gb=21.02,
                disk_percent=29.78,
                network_sent_bytes=1000,
                network_recv_bytes=2000,
                temperatures=(),
            ),
            details=BeszelDetails(
                hostname="goreecloud-vps-01",
                kernel="6.12.96+deb13-amd64",
                cores=4,
                threads=4,
                cpu_model="Intel Core Processor (Haswell, no TSX)",
                os_name="Debian GNU/Linux 13 (trixie)",
                architecture="x86_64",
                memory_bytes=8134107136,
                podman=False,
            ),
            containers=(
                BeszelContainer(
                    name="caddy",
                    state="Up 4 days",
                    health="healthy",
                    cpu_percent=0.2,
                    memory_gb=0.05,
                    network_sent_bytes=300,
                    network_recv_bytes=500,
                ),
            ),
        )

        user = get_user_model().objects.create_user(
            username="beszel-admin-test",
            password="strong-test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("overview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Beszel")
        self.assertContains(response, "Delegated read-only Beszel artifact")
        self.assertContains(response, "goreecloud-vps-01 resource monitoring")
        self.assertContains(response, "5.0%")
        self.assertContains(response, "55.2%")
        self.assertContains(response, "29.8%")
        self.assertContains(response, "caddy")
        self.assertContains(response, "Aug 11, 2026 5:35 PM CDT")
        self.assertContains(response, "does not prove service availability")
