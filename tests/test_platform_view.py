"""View tests for authority-preserving GoreeCloud Platform visibility."""

from datetime import UTC, datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from integrations.mesh import MeshPlatformRecord, MeshPlatformSnapshot, MeshRelationship


class PlatformViewTests(TestCase):
    def test_platform_page_requires_authentication(self):
        response = self.client.get(reverse("platform"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    @patch("core.views.mesh_platform_snapshot")
    def test_platform_page_preserves_producer_and_restore_boundaries(self, mocked_snapshot):
        mocked_snapshot.return_value = MeshPlatformSnapshot(
            state="healthy",
            detail="Live authority-preserving Mesh platform registry data verified for 1 component(s).",
            condition="healthy",
            records=(
                MeshPlatformRecord(
                    component_id="goreecloud.tasks",
                    product_name="GoreeCloud Tasks",
                    kind="application",
                    lifecycle="Development",
                    version="0.1",
                    supported_platforms=("web", "linux-server"),
                    repository="GoreeCloud/goreecloud-tasks",
                    source_revision="0123456789abcdef0123456789abcdef01234567",
                    capabilities=("operational-work",),
                    dependencies=("goreecloud.mesh",),
                    relationships=(
                        MeshRelationship(
                            target="goreecloud.mesh",
                            relationship_type="platform-coordination",
                            required=True,
                        ),
                    ),
                    platform_systems=(
                        ("manager", "Applicable — Nonconformant"),
                        ("identity", "Applicable — Migration Required"),
                        ("wardveil_security", "Applicable — Nonconformant"),
                        ("privacy_shield", "Applicable — Nonconformant"),
                        ("everkeep", "Applicable — Nonconformant"),
                        ("mesh", "Applicable — Nonconformant"),
                        ("glaze_ui", "Applicable — Migration Required"),
                    ),
                    runtime_state="unknown",
                    health_state="unknown",
                    readiness="unknown",
                    backup_status="verified",
                    restore_status="required_missing",
                    last_verified_restore=None,
                    export_status="implemented_unverified",
                    export_formats=("json",),
                    overall_result="non-conformant",
                    stable_eligible=False,
                    missing_mandatory_evidence=("restore", "platform-acceptance"),
                    observed_at=datetime(2026, 9, 3, 0, 30, tzinfo=UTC),
                ),
            ),
        )
        user = get_user_model().objects.create_user(
            username="platform-manager-view-test",
            password="strong-test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("platform"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "GoreeCloud Platform")
        self.assertContains(response, "GoreeCloud Tasks")
        self.assertContains(response, "goreecloud.tasks")
        self.assertContains(response, "Applicable — Migration Required")
        self.assertContains(response, "goreecloud.mesh")
        self.assertContains(response, "Backup is not restore proof")
        self.assertContains(response, "required_missing")
        self.assertContains(response, "Stable: not eligible")
        self.assertContains(response, "Manager presents normalized Mesh records but does not approve")
        self.assertContains(response, "Manager does not present it as currently restorable")
        self.assertContains(response, "Wardveil Security")
        self.assertContains(response, "Privacy Shield")
        self.assertContains(response, "Glaze UI")
        self.assertNotContains(response, "Wardveil_Security")
        self.assertNotContains(response, "Privacy_Shield")
        self.assertNotContains(response, "Glaze_Ui")

    @patch("core.views.mesh_platform_snapshot")
    def test_platform_page_fails_soft_without_manufacturing_state(self, mocked_snapshot):
        mocked_snapshot.return_value = MeshPlatformSnapshot(
            state="unavailable",
            detail="GoreeCloud Mesh did not respond before the configured timeout.",
            condition="unreachable",
        )
        user = get_user_model().objects.create_user(
            username="platform-manager-unavailable-test",
            password="strong-test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("platform"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Live platform data is not available")
        self.assertContains(response, "configured timeout")
        self.assertContains(response, "do not infer component conformance or continuity")
