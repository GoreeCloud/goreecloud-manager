"""Tests for Manager's read-only Wardveil Security evidence consumer."""

import os
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from integrations.wardveil import wardveil_snapshot


class WardveilAdapterTests(SimpleTestCase):
    TOKEN = "wardveil-evidence-read-test-token-0123456789abcdef"

    def _response(self, *, status_code=200, payload=None, content=b"{}"):
        response = Mock()
        response.status_code = status_code
        response.content = content
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        return response

    def _envelope(self, *, outcome="attention", fresh=True):
        return {
            "version": "goreecloud.evidence-envelope.v1",
            "id": "wardveil-status-test-1",
            "producer": {
                "system": "wardveil-security",
                "repository": "GoreeCloud/goreecloud-wardveil-security",
                "revision": "0123456789abcdef0123456789abcdef01234567",
                "contract": "contracts/wardveil.status.schema.json",
            },
            "authority_domain": "security",
            "subject": {
                "kind": "service",
                "id": "goreecloud-manager",
                "scope": "runtime",
            },
            "assertion": "security-status",
            "outcome": outcome,
            "source": "wardveil://records/status-test-1",
            "observed_at": "2026-09-05T12:00:00Z",
            "valid_until": "2099-09-05T13:00:00Z" if fresh else "2026-09-05T12:30:00Z",
            "data_class": "derived",
            "summary": "Wardveil security-status evidence.",
            "payload_digest": "sha256:" + ("a" * 64),
            "contains_user_content": False,
            "contains_secret_material": False,
            "fresh": fresh,
        }

    def _payload(self, *, envelopes=None):
        records = [self._envelope()] if envelopes is None else envelopes
        current = sum(bool(item.get("fresh")) for item in records)
        return {
            "count": len(records),
            "current_count": current,
            "stale_count": len(records) - current,
            "envelopes": records,
            "note": "Evidence transport freshness is not a security verdict.",
        }

    def _environment(self, **overrides):
        values = {
            "WARDVEIL_STATUS_ENABLED": "true",
            "MESH_API_URL": "https://mesh.internal.example.test",
            "MESH_WARDVEIL_EVIDENCE_TOKEN": self.TOKEN,
            "MESH_WARDVEIL_EVIDENCE_TOKEN_FILE": "",
            "WARDVEIL_STATUS_TIMEOUT_SECONDS": "5",
        }
        values.update(overrides)
        return patch.dict(os.environ, values, clear=False)

    @patch("integrations.wardveil.httpx.get")
    def test_current_status_preserves_wardveil_authority_and_scope(self, mocked_get):
        mocked_get.return_value = self._response(payload=self._payload())
        with self._environment():
            snapshot = wardveil_snapshot()

        self.assertEqual(snapshot.state, "available")
        self.assertEqual(snapshot.condition, "current")
        self.assertEqual(snapshot.current_count, 1)
        self.assertEqual(snapshot.stale_count, 0)
        self.assertEqual(len(snapshot.records), 1)
        record = snapshot.records[0]
        self.assertEqual(record.outcome, "attention")
        self.assertEqual(record.subject_id, "goreecloud-manager")
        self.assertEqual(record.subject_scope, "runtime")
        self.assertTrue(record.fresh)
        self.assertNotIn("Protected by Wardveil", snapshot.detail)

        args, kwargs = mocked_get.call_args
        self.assertEqual(args[0], "https://mesh.internal.example.test/v1/evidence/envelopes")
        self.assertEqual(kwargs["headers"]["Authorization"], f"Bearer {self.TOKEN}")
        self.assertEqual(
            kwargs["params"],
            {
                "producer": "wardveil-security",
                "authority_domain": "security",
                "assertion": "security-status",
            },
        )
        self.assertNotIn(self.TOKEN, snapshot.detail)

    @patch("integrations.wardveil.httpx.get")
    def test_disabled_integration_makes_no_network_request(self, mocked_get):
        with self._environment(WARDVEIL_STATUS_ENABLED="false"):
            snapshot = wardveil_snapshot()
        self.assertEqual(snapshot.state, "disabled")
        mocked_get.assert_not_called()

    @patch("integrations.wardveil.httpx.get")
    def test_uses_separate_evidence_credential_not_registry_or_event_token(self, mocked_get):
        mocked_get.return_value = self._response(payload=self._payload())
        with self._environment(
            MESH_ACCESS_TOKEN="registry-token-must-not-be-used",
            MESH_EVENTS_ACCESS_TOKEN="event-token-must-not-be-used",
        ):
            snapshot = wardveil_snapshot()
        self.assertEqual(snapshot.state, "available")
        authorization = mocked_get.call_args.kwargs["headers"]["Authorization"]
        self.assertEqual(authorization, f"Bearer {self.TOKEN}")
        self.assertNotIn("registry-token", authorization)
        self.assertNotIn("event-token", authorization)

    @patch("integrations.wardveil.httpx.get")
    def test_mutually_exclusive_token_sources_fail_closed(self, mocked_get):
        with self._environment(MESH_WARDVEIL_EVIDENCE_TOKEN_FILE="/tmp/also-set"):
            snapshot = wardveil_snapshot()
        self.assertEqual(snapshot.state, "misconfigured")
        mocked_get.assert_not_called()
        self.assertNotIn(self.TOKEN, snapshot.detail)

    @patch("integrations.wardveil.httpx.get")
    def test_non_loopback_http_is_rejected(self, mocked_get):
        with self._environment(MESH_API_URL="http://mesh.internal.example.test"):
            snapshot = wardveil_snapshot()
        self.assertEqual(snapshot.condition, "misconfigured")
        mocked_get.assert_not_called()

    @patch("integrations.wardveil.httpx.get")
    def test_loopback_http_is_allowed_for_development(self, mocked_get):
        mocked_get.return_value = self._response(payload=self._payload())
        with self._environment(MESH_API_URL="http://127.0.0.1:8080"):
            snapshot = wardveil_snapshot()
        self.assertEqual(snapshot.state, "available")
        self.assertEqual(
            mocked_get.call_args.args[0],
            "http://127.0.0.1:8080/v1/evidence/envelopes",
        )

    @patch("integrations.wardveil.httpx.get")
    def test_empty_transport_does_not_manufacture_security_state(self, mocked_get):
        mocked_get.return_value = self._response(payload=self._payload(envelopes=[]))
        with self._environment():
            snapshot = wardveil_snapshot()
        self.assertEqual(snapshot.state, "unknown")
        self.assertEqual(snapshot.condition, "empty")
        self.assertEqual(snapshot.records, ())

    @patch("integrations.wardveil.httpx.get")
    def test_stale_protected_outcome_is_historical_not_current_claim(self, mocked_get):
        envelope = self._envelope(outcome="protected", fresh=False)
        mocked_get.return_value = self._response(payload=self._payload(envelopes=[envelope]))
        with self._environment():
            snapshot = wardveil_snapshot()
        self.assertEqual(snapshot.state, "stale")
        self.assertEqual(snapshot.current_count, 0)
        self.assertEqual(snapshot.records[0].outcome, "protected")
        self.assertFalse(snapshot.records[0].fresh)
        self.assertIn("not current security claims", snapshot.detail)

    @patch("integrations.wardveil.httpx.get")
    def test_wrong_producer_repository_or_contract_fails_closed(self, mocked_get):
        for field, value in (
            ("system", "goreecloud-manager"),
            ("repository", "GoreeCloud/goreecloud-manager"),
            ("contract", "contracts/wardveil.runtime.schema.json"),
        ):
            envelope = self._envelope()
            envelope["producer"][field] = value
            mocked_get.return_value = self._response(payload=self._payload(envelopes=[envelope]))
            with self._environment():
                snapshot = wardveil_snapshot()
            self.assertEqual(snapshot.condition, "schema-invalid")
            self.assertEqual(snapshot.records, ())

    @patch("integrations.wardveil.httpx.get")
    def test_wrong_authority_or_assertion_fails_closed(self, mocked_get):
        envelope = self._envelope()
        envelope["authority_domain"] = "privacy"
        mocked_get.return_value = self._response(payload=self._payload(envelopes=[envelope]))
        with self._environment():
            snapshot = wardveil_snapshot()
        self.assertEqual(snapshot.condition, "schema-invalid")

        envelope = self._envelope()
        envelope["assertion"] = "protection-result"
        mocked_get.return_value = self._response(payload=self._payload(envelopes=[envelope]))
        with self._environment():
            snapshot = wardveil_snapshot()
        self.assertEqual(snapshot.condition, "schema-invalid")

    @patch("integrations.wardveil.httpx.get")
    def test_user_content_or_secret_material_is_rejected(self, mocked_get):
        for field in ("contains_user_content", "contains_secret_material"):
            envelope = self._envelope()
            envelope[field] = True
            mocked_get.return_value = self._response(payload=self._payload(envelopes=[envelope]))
            with self._environment():
                snapshot = wardveil_snapshot()
            self.assertEqual(snapshot.condition, "schema-invalid")

    @patch("integrations.wardveil.httpx.get")
    def test_future_observation_and_invalid_freshness_fail_closed(self, mocked_get):
        envelope = self._envelope()
        envelope["observed_at"] = "2099-09-05T12:00:00Z"
        mocked_get.return_value = self._response(payload=self._payload(envelopes=[envelope]))
        with self._environment():
            snapshot = wardveil_snapshot()
        self.assertEqual(snapshot.condition, "schema-invalid")

        envelope = self._envelope(fresh=False)
        envelope["valid_until"] = "2099-09-05T13:00:00Z"
        mocked_get.return_value = self._response(payload=self._payload(envelopes=[envelope]))
        with self._environment():
            snapshot = wardveil_snapshot()
        self.assertEqual(snapshot.condition, "schema-invalid")

    @patch("integrations.wardveil.httpx.get")
    def test_unknown_fields_and_unsupported_outcome_fail_closed(self, mocked_get):
        envelope = self._envelope()
        envelope["unexpected"] = "value"
        mocked_get.return_value = self._response(payload=self._payload(envelopes=[envelope]))
        with self._environment():
            snapshot = wardveil_snapshot()
        self.assertEqual(snapshot.condition, "schema-invalid")

        envelope = self._envelope(outcome="safe")
        mocked_get.return_value = self._response(payload=self._payload(envelopes=[envelope]))
        with self._environment():
            snapshot = wardveil_snapshot()
        self.assertEqual(snapshot.condition, "schema-invalid")

    @patch("integrations.wardveil.httpx.get")
    def test_authorization_failure_is_sanitized(self, mocked_get):
        mocked_get.return_value = self._response(status_code=403, payload={})
        with self._environment():
            snapshot = wardveil_snapshot()
        self.assertEqual(snapshot.condition, "authorization-denied")
        self.assertNotIn(self.TOKEN, snapshot.detail)
        self.assertIn("mesh.evidence.read", snapshot.detail)

    @patch("integrations.wardveil.httpx.get")
    def test_oversized_response_is_rejected(self, mocked_get):
        mocked_get.return_value = self._response(
            payload=self._payload(),
            content=b"x" * ((1 << 20) + 1),
        )
        with self._environment():
            snapshot = wardveil_snapshot()
        self.assertEqual(snapshot.condition, "response-too-large")

    @patch("integrations.wardveil.httpx.get")
    def test_latest_observation_per_subject_is_presented_without_local_history(self, mocked_get):
        older = self._envelope(outcome="degraded")
        older["id"] = "wardveil-status-old"
        older["observed_at"] = "2026-09-05T11:00:00Z"
        newer = self._envelope(outcome="attention")
        newer["id"] = "wardveil-status-new"
        newer["observed_at"] = "2026-09-05T12:00:00Z"
        mocked_get.return_value = self._response(payload=self._payload(envelopes=[older, newer]))
        with self._environment():
            snapshot = wardveil_snapshot()
        self.assertEqual(len(snapshot.records), 1)
        self.assertEqual(snapshot.records[0].outcome, "attention")
