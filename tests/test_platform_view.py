"""View tests for authority-preserving GoreeCloud Platform visibility."""

from datetime import UTC, datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from integrations.mesh import MeshPlatformRecord, MeshPlatformSnapshot, MeshRelationship


class PlatformViewTests(TestCase):
    def _record(self, *, freshness_state="fresh", stable_eligible=False, computed_result="nonconformant"):
        return MeshPlatformRecord(
            component_id="goreecloud-tasks",
            product_name="GoreeCloud Tasks",
            kind="application",
            lifecycle="stable" if stable_eligible else "development",
            version="0.1",
            supported_platforms=("web", "linux-server"),
            repository="GoreeCloud/goreecloud-tasks",
            source_revision="0123456789abcdef0123456789abcdef01234567",
            capabilities=("operational-work",),
            dependencies=("goreecloud-mesh",),
            relationships=(
                MeshRelationship(
                    target="goreecloud-mesh",
                    relationship_type="platform-coordination",
                    required=True,
                ),
            ),
            platform_systems=(
                ("manager", "applicable-nonconformant"),
                ("identity", "applicable-migration-required"),
                ("wardveil_security", "applicable-nonconformant"),
                ("privacy_shield", "applicable-nonconformant"),
                ("everkeep", "applicable-nonconformant"),
                ("mesh", "applicable-nonconformant"),
                ("glaze_ui", "applicable-migration-required"),
            ),
            runtime_state="unknown",
            health_state="unknown",
            readiness="unknown",
            backup_status="verified",
            restore_status="required_missing",
            last_verified_restore=None,
            export_status="implemented_unverified",
            export_formats=("json",),
            declared_result=computed_result,
            computed_result=computed_result,
            stable_eligible=stable_eligible,
            evaluator_repository="GoreeCloud/GoreeCloud",
            evaluator_revision="abcdef0123456789abcdef0123456789abcdef01",
            evaluated_at=datetime(2026, 9, 3, 0, 29, tzinfo=UTC),
            missing_mandatory_evidence=("restore", "platform-acceptance"),
            blockers=("target acceptance incomplete",),
            observed_at=datetime(2026, 9, 3, 0, 30, tzinfo=UTC),
            observation_age_seconds=60,
            evaluation_age_seconds=120,
            freshness_state=freshness_state,
        )

    def test_platform_page_requires_authentication(self):
        response = self.client.get(reverse("platform"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    @patch("core.views.mesh_platform_snapshot")
    def test_platform_page_preserves_authority_and_restore_boundaries(self, mocked_snapshot):
        mocked_snapshot.return_value = MeshPlatformSnapshot(
            state="healthy",
            detail="Live authority-preserving Mesh platform registry data verified for 1 component(s).",
            condition="healthy",
            records=(self._record(),),
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
        self.assertContains(response, "goreecloud-tasks")
        self.assertContains(response, "applicable-migration-required")
        self.assertContains(response, "goreecloud-mesh")
        self.assertContains(response, "Backup is not restore proof")
        self.assertContains(response, "required_missing")
        self.assertContains(response, "Stable: not eligible")
        self.assertContains(response, "Evidence: fresh")
        self.assertContains(response, "Manager presents normalized Mesh records but does not approve")
        self.assertContains(response, "local freshness classification affects only whether evidence is presented as current")
        self.assertContains(response, "canonical GoreeCloud evaluator remains authoritative")
        self.assertContains(response, "GoreeCloud/GoreeCloud")
        self.assertContains(response, "abcdef012345")
        self.assertContains(response, "target acceptance incomplete")
        self.assertContains(response, "Manager does not present it as currently restorable")
        self.assertContains(response, "Wardveil Security")
        self.assertContains(response, "Privacy Shield")
        self.assertContains(response, "Glaze UI")
        self.assertNotContains(response, "Wardveil_Security")
        self.assertNotContains(response, "Privacy_Shield")
        self.assertNotContains(response, "Glaze_Ui")

    @patch("core.views.mesh_platform_snapshot")
    def test_platform_page_labels_stale_favorable_state_as_historical(self, mocked_snapshot):
        stale = self._record(
            freshness_state="stale",
            stable_eligible=True,
            computed_result="conformant",
        )
        mocked_snapshot.return_value = MeshPlatformSnapshot(
            state="degraded",
            detail=(
                "GoreeCloud Mesh returned 1 stale platform record(s) out of 1. "
                "Manager preserves those producer values for inspection but excludes stale favorable state."
            ),
            condition="stale-records",
            records=(stale,),
        )
        user = get_user_model().objects.create_user(
            username="platform-manager-stale-view-test",
            password="strong-test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("platform"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stale platform evidence")
        self.assertContains(response, "Historical producer state")
        self.assertContains(response, "Evidence: stale")
        self.assertContains(response, "conformant")
        self.assertContains(response, "Stable: eligible")
        self.assertContains(response, "excludes stale favorable state")
        self.assertContains(response, "fresh canonical-evaluator conformant")
        self.assertContains(response, "<strong>0</strong>", html=True)

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
