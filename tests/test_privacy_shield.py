"""Tests for the privacy-safe Privacy Shield Manager integration."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from integrations.privacy_shield import privacy_shield_snapshot


VALID_STATUS = {
    "schema_version": 1,
    "producer": {
        "adapter_id": "browser",
        "product": "GoreeCloud Browser",
        "runtime_authority": "GoreeCloud/goreecloud-browser",
        "adapter_contract_version": 1,
    },
    "generated_at": "2026-08-20T05:00:00Z",
    "state": "development",
    "capabilities": [
        {"id": "content-blocking", "state": "pending-acceptance"},
        {"id": "url-cleaning", "state": "pending-acceptance"},
    ],
    "privacy": {
        "raw_private_activity_included": False,
        "contains_credentials": False,
        "contains_identifiers": False,
    },
    "acceptance": {
        "runtime_acceptance_required": True,
        "production_approved": False,
    },
}


class PrivacyShieldSnapshotTests(unittest.TestCase):
    def _snapshot(self, payload: dict):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "privacy-shield-status.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.dict(os.environ, {"PRIVACY_SHIELD_STATUS_FILE": str(path)}, clear=False):
                return privacy_shield_snapshot()

    def test_valid_sanitized_status_is_accepted(self):
        snapshot = self._snapshot(VALID_STATUS)
        self.assertEqual(snapshot.state, "development")
        self.assertEqual(snapshot.product, "GoreeCloud Browser")
        self.assertFalse(snapshot.production_approved)
        self.assertEqual(len(snapshot.capabilities), 2)

    def test_raw_private_activity_is_rejected_fail_closed(self):
        payload = json.loads(json.dumps(VALID_STATUS))
        payload["privacy"]["raw_private_activity_included"] = True
        snapshot = self._snapshot(payload)
        self.assertEqual(snapshot.state, "unavailable")
        self.assertIn("raw private activity", snapshot.detail)

    def test_undeclared_privacy_guarantee_is_rejected(self):
        payload = json.loads(json.dumps(VALID_STATUS))
        del payload["privacy"]["contains_identifiers"]
        snapshot = self._snapshot(payload)
        self.assertEqual(snapshot.state, "unavailable")
        self.assertIn("identifying content", snapshot.detail)

    def test_runtime_acceptance_boundary_cannot_be_removed(self):
        payload = json.loads(json.dumps(VALID_STATUS))
        payload["acceptance"]["runtime_acceptance_required"] = False
        snapshot = self._snapshot(payload)
        self.assertEqual(snapshot.state, "unavailable")
        self.assertIn("acceptance boundary", snapshot.detail)

    def test_missing_configuration_is_safe_and_unavailable(self):
        with patch.dict(os.environ, {}, clear=True):
            snapshot = privacy_shield_snapshot()
        self.assertEqual(snapshot.state, "unavailable")
        self.assertIn("PRIVACY_SHIELD_STATUS_FILE", snapshot.detail)


if __name__ == "__main__":
    unittest.main()
