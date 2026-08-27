from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from integrations.everkeep import everkeep_snapshot


VALID_STATUS = {
    "schema_version": 1,
    "producer": {
        "adapter_id": "backup",
        "runtime_authority": "GoreeCloud/goreecloud-backup",
    },
    "generated_at": "2026-08-26T23:00:00Z",
    "state": "development",
    "privacy": {
        "contains_backup_contents": False,
        "contains_file_inventory": False,
        "contains_recovery_secrets": False,
        "contains_credentials": False,
        "contains_private_paths": False,
        "contains_personal_records": False,
        "contains_raw_legacy_records": False,
    },
    "acceptance": {
        "runtime_acceptance_required": True,
        "production_approved": False,
    },
    "resilience": {
        "recovery_readiness": "pending",
        "backup_verification": "verified",
        "backup_verification_age_seconds": 3600,
        "portability_continuity": "pending",
        "preservation": "verified",
    },
    "capabilities": [
        {"id": "restore-readiness", "state": "pending"},
        {"id": "backup-verification", "state": "verified"},
    ],
}


def snapshot(payload: dict):
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "everkeep-status.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with patch.dict(os.environ, {"EVERKEEP_STATUS_FILE": str(path)}, clear=False):
            return everkeep_snapshot()


def clone_valid() -> dict:
    return json.loads(json.dumps(VALID_STATUS))


def test_valid_sanitized_status_is_accepted():
    result = snapshot(VALID_STATUS)
    assert result.state == "development"
    assert result.backup_verification == "verified"
    assert result.backup_verification_age_seconds == 3600
    assert result.production_approved is False
    assert len(result.capabilities) == 2


def test_sensitive_recovery_content_fails_closed_without_leaking_sentinel():
    payload = clone_valid()
    payload["privacy"]["contains_recovery_secrets"] = True
    payload["secret_sentinel"] = "RECOVERY-CODE-SHOULD-NEVER-ESCAPE"
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "RECOVERY-CODE-SHOULD-NEVER-ESCAPE" not in result.detail


def test_duplicate_capability_fails_closed():
    payload = clone_valid()
    payload["capabilities"].append({"id": "restore-readiness", "state": "verified"})
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "duplicated" in result.detail


def test_unapproved_top_level_field_fails_closed():
    payload = clone_valid()
    payload["private_path"] = "/srv/private/backup"
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "/srv/private/backup" not in result.detail


def test_unapproved_nested_field_fails_closed():
    payload = clone_valid()
    payload["producer"]["credential"] = "secret-like-token"
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "secret-like-token" not in result.detail


def test_invalid_timestamp_fails_closed():
    payload = clone_valid()
    payload["generated_at"] = "26 August 2026 23:00"
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "timestamp" in result.detail


def test_non_utc_timestamp_fails_closed():
    payload = clone_valid()
    payload["generated_at"] = "2026-08-26T19:00:00-04:00"
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "timestamp" in result.detail


def test_backup_verification_recency_is_bounded():
    payload = clone_valid()
    payload["resilience"]["backup_verification_age_seconds"] = 31 * 24 * 60 * 60 + 1
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "recency" in result.detail


def test_boolean_is_not_accepted_as_recency_integer():
    payload = clone_valid()
    payload["resilience"]["backup_verification_age_seconds"] = True
    result = snapshot(payload)
    assert result.state == "unavailable"


def test_capability_extra_field_fails_closed():
    payload = clone_valid()
    payload["capabilities"][0]["raw_detail"] = "private restore path"
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "private restore path" not in result.detail


def test_missing_configuration_is_unavailable():
    with patch.dict(os.environ, {}, clear=True):
        result = everkeep_snapshot()
    assert result.state == "unavailable"
    assert "EVERKEEP_STATUS_FILE" in result.detail
