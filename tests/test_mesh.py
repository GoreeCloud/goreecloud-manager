"""Tests for the read-only GoreeCloud Mesh platform-registry integration."""

import os
from unittest.mock import Mock, patch

import httpx
from django.test import SimpleTestCase

from integrations.mesh import mesh_platform_snapshot


class MeshAdapterTests(SimpleTestCase):
    TOKEN = "mesh-read-test-token-0123456789abcdef0123456789abcdef"

    def _response(self, *, status_code=200, payload=None, content=b"{}"):
        response = Mock()
        response.status_code = status_code
        response.content = content
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        return response

    def _record(self):
        return {
            "schema": "goreecloud.mesh.platform-record.v1",
            "source": {
                "repository": "GoreeCloud/goreecloud-tasks",
                "revision": "0123456789abcdef0123456789abcdef01234567",
                "contract_schema_version": "0.2",
                "authority_transfer": False,
            },
            "component": {
                "id": "goreecloud-tasks",
                "product_name": "GoreeCloud Tasks",
                "kind": "application",
                "repository": "GoreeCloud/goreecloud-tasks",
                "lifecycle": "development",
                "version": "0.1",
                "supported_platforms": ["web", "linux-server"],
            },
            "capabilities": ["operational-work"],
            "dependencies": ["goreecloud-mesh"],
            "relationships": [
                {"target": "goreecloud-mesh", "type": "platform-coordination", "required": True}
            ],
            "platform_systems": {
                "manager": {"result": "applicable-nonconformant"},
                "identity": {"result": "applicable-migration-required"},
                "wardveil_security": {"result": "applicable-nonconformant"},
                "privacy_shield": {"result": "applicable-nonconformant"},
                "everkeep": {"result": "applicable-nonconformant"},
                "mesh": {"result": "applicable-nonconformant"},
                "glaze_ui": {"result": "applicable-migration-required"},
            },
            "health": {
                "runtime_state": "unknown",
                "health_state": "unknown",
                "readiness": "unknown",
            },
            "recovery": {
                "backup_status": "implemented_unverified",
                "restore_status": "required_missing",
            },
            "portability": {
                "export_status": "implemented_unverified",
                "formats": ["json"],
            },
            "conformance": {
                "declared_result": "nonconformant",
                "computed_result": "nonconformant",
                "stable_eligible": False,
                "evaluator_repository": "GoreeCloud/GoreeCloud",
                "evaluator_revision": "abcdef0123456789abcdef0123456789abcdef01",
                "evaluated_at": "2026-09-03T00:29:00Z",
                "missing_mandatory_evidence": ["restore", "platform-acceptance"],
                "blockers": ["target acceptance incomplete"],
            },
            "observed_at": "2026-09-03T00:30:00Z",
        }

    def _payload(self):
        return {"count": 1, "records": [self._record()], "note": "coordination-only"}

    def _environment(self, **overrides):
        values = {
            "MESH_ENABLED": "true",
            "MESH_API_URL": "https://mesh.internal.example.test",
            "MESH_ACCESS_TOKEN": self.TOKEN,
            "MESH_ACCESS_TOKEN_FILE": "",
            "MESH_TIMEOUT_SECONDS": "5",
        }
        values.update(overrides)
        return patch.dict(os.environ, values, clear=False)

    @patch("integrations.mesh.httpx.get")
    def test_success_normalizes_authority_preserving_records(self, mocked_get):
        mocked_get.return_value = self._response(payload=self._payload())
        with self._environment():
            snapshot = mesh_platform_snapshot()

        self.assertEqual(snapshot.state, "healthy")
        self.assertEqual(len(snapshot.records), 1)
        record = snapshot.records[0]
        self.assertEqual(record.component_id, "goreecloud-tasks")
        self.assertEqual(record.restore_status, "required_missing")
        self.assertFalse(record.continuity_verified)
        self.assertFalse(record.stable_eligible)
        self.assertEqual(record.computed_result, "nonconformant")
        self.assertEqual(record.evaluator_repository, "GoreeCloud/GoreeCloud")
        self.assertEqual(record.platform_system_map["glaze_ui"], "applicable-migration-required")
        self.assertEqual(snapshot.relationship_count, 2)

        args, kwargs = mocked_get.call_args
        self.assertEqual(args[0], "https://mesh.internal.example.test/v1/platform-registry")
        self.assertEqual(kwargs["headers"]["Authorization"], f"Bearer {self.TOKEN}")
        self.assertNotIn(self.TOKEN, snapshot.detail)

    @patch("integrations.mesh.httpx.get")
    def test_disabled_integration_makes_no_network_request(self, mocked_get):
        with self._environment(MESH_ENABLED="false"):
            snapshot = mesh_platform_snapshot()
        self.assertEqual(snapshot.state, "disabled")
        mocked_get.assert_not_called()

    @patch("integrations.mesh.httpx.get")
    def test_write_or_other_scope_is_not_requested_by_manager(self, mocked_get):
        mocked_get.return_value = self._response(payload=self._payload())
        with self._environment():
            mesh_platform_snapshot()
        authorization = mocked_get.call_args.kwargs["headers"]["Authorization"]
        self.assertEqual(authorization, f"Bearer {self.TOKEN}")
        self.assertNotIn("write", mocked_get.call_args.args[0])

    @patch("integrations.mesh.httpx.get")
    def test_rejected_read_credential_is_sanitized(self, mocked_get):
        mocked_get.return_value = self._response(status_code=403, payload={})
        with self._environment():
            snapshot = mesh_platform_snapshot()
        self.assertEqual(snapshot.state, "unavailable")
        self.assertEqual(snapshot.condition, "authorization-denied")
        self.assertNotIn(self.TOKEN, snapshot.detail)

    @patch("integrations.mesh.httpx.get")
    def test_authority_transfer_is_rejected(self, mocked_get):
        payload = self._payload()
        payload["records"][0]["source"]["authority_transfer"] = True
        mocked_get.return_value = self._response(payload=payload)
        with self._environment():
            snapshot = mesh_platform_snapshot()
        self.assertEqual(snapshot.condition, "schema-invalid")
        self.assertEqual(snapshot.records, ())

    @patch("integrations.mesh.httpx.get")
    def test_mismatched_source_repository_is_rejected(self, mocked_get):
        payload = self._payload()
        payload["records"][0]["source"]["repository"] = "GoreeCloud/goreecloud-manager"
        mocked_get.return_value = self._response(payload=payload)
        with self._environment():
            snapshot = mesh_platform_snapshot()
        self.assertEqual(snapshot.condition, "schema-invalid")

    @patch("integrations.mesh.httpx.get")
    def test_legacy_platform_contract_vocabulary_is_rejected(self, mocked_get):
        payload = self._payload()
        payload["records"][0]["source"]["contract_schema_version"] = "1.0"
        mocked_get.return_value = self._response(payload=payload)
        with self._environment():
            snapshot = mesh_platform_snapshot()
        self.assertEqual(snapshot.condition, "schema-invalid")

        payload = self._payload()
        payload["records"][0]["component"]["lifecycle"] = "Development"
        mocked_get.return_value = self._response(payload=payload)
        with self._environment():
            snapshot = mesh_platform_snapshot()
        self.assertEqual(snapshot.condition, "schema-invalid")

        payload = self._payload()
        payload["records"][0]["platform_systems"]["glaze_ui"] = {
            "status": "Applicable — Migration Required"
        }
        mocked_get.return_value = self._response(payload=payload)
        with self._environment():
            snapshot = mesh_platform_snapshot()
        self.assertEqual(snapshot.condition, "schema-invalid")

    @patch("integrations.mesh.httpx.get")
    def test_noncanonical_evaluator_is_rejected(self, mocked_get):
        payload = self._payload()
        payload["records"][0]["conformance"]["evaluator_repository"] = "GoreeCloud/goreecloud-manager"
        mocked_get.return_value = self._response(payload=payload)
        with self._environment():
            snapshot = mesh_platform_snapshot()
        self.assertEqual(snapshot.condition, "schema-invalid")

    @patch("integrations.mesh.httpx.get")
    def test_backup_never_manufactures_verified_restore(self, mocked_get):
        payload = self._payload()
        payload["records"][0]["recovery"]["backup_status"] = "verified"
        mocked_get.return_value = self._response(payload=payload)
        with self._environment():
            snapshot = mesh_platform_snapshot()
        record = snapshot.records[0]
        self.assertEqual(record.backup_status, "verified")
        self.assertEqual(record.restore_status, "required_missing")
        self.assertFalse(record.continuity_verified)

    @patch("integrations.mesh.httpx.get")
    def test_verified_restore_requires_timestamp(self, mocked_get):
        payload = self._payload()
        payload["records"][0]["recovery"]["restore_status"] = "verified"
        mocked_get.return_value = self._response(payload=payload)
        with self._environment():
            snapshot = mesh_platform_snapshot()
        self.assertEqual(snapshot.condition, "schema-invalid")

    @patch("integrations.mesh.httpx.get")
    def test_false_stable_eligibility_is_rejected(self, mocked_get):
        payload = self._payload()
        payload["records"][0]["conformance"]["stable_eligible"] = True
        mocked_get.return_value = self._response(payload=payload)
        with self._environment():
            snapshot = mesh_platform_snapshot()
        self.assertEqual(snapshot.condition, "schema-invalid")

    @patch("integrations.mesh.httpx.get")
    def test_timeout_is_fail_soft_and_sanitized(self, mocked_get):
        mocked_get.side_effect = httpx.TimeoutException("contains-secret")
        with self._environment():
            snapshot = mesh_platform_snapshot()
        self.assertEqual(snapshot.condition, "unreachable")
        self.assertNotIn("contains-secret", snapshot.detail)
        self.assertNotIn(self.TOKEN, snapshot.detail)

    @patch("integrations.mesh.httpx.get")
    def test_oversized_response_is_rejected(self, mocked_get):
        mocked_get.return_value = self._response(payload=self._payload(), content=b"x" * ((1 << 20) + 1))
        with self._environment():
            snapshot = mesh_platform_snapshot()
        self.assertEqual(snapshot.condition, "response-too-large")

    @patch("integrations.mesh.httpx.get")
    def test_invalid_url_fails_closed_before_network(self, mocked_get):
        with self._environment(MESH_API_URL="https://user:secret@example.test/path?token=bad"):
            snapshot = mesh_platform_snapshot()
        self.assertEqual(snapshot.state, "misconfigured")
        mocked_get.assert_not_called()
