from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from integrations.infrastructure import MAX_STATUS_BYTES, infrastructure_snapshot


def fresh_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


VALID_STATUS = {
    "schema_version": 1,
    "producer": {
        "service_id": "goreecloud-network",
        "adapter_id": "goreecloud-network/status-v1",
        "runtime_authority": "GoreeCloud/NetBirdDataPlane",
    },
    "generated_at": fresh_timestamp(),
    "state": "development",
    "privacy": {
        "contains_credentials": False,
        "contains_personal_data": False,
        "contains_raw_logs": False,
        "contains_network_identifiers": False,
        "contains_query_data": False,
        "contains_certificate_material": False,
    },
    "acceptance": {
        "runtime_acceptance_required": True,
        "production_approved": False,
    },
    "capabilities": [
        {"id": "private-connectivity", "state": "pending"},
        {"id": "access-policy", "state": "pending"},
    ],
}


def clone_valid() -> dict:
    payload = json.loads(json.dumps(VALID_STATUS))
    payload["generated_at"] = fresh_timestamp()
    return payload


def snapshot(payload: dict, *, service_id: str = "goreecloud-network"):
    env_name = {
        "goreecloud-gateway": "GOREECLOUD_GATEWAY_STATUS_FILE",
        "goreecloud-dns": "GOREECLOUD_DNS_STATUS_FILE",
        "goreecloud-network": "GOREECLOUD_NETWORK_STATUS_FILE",
    }[service_id]
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "status.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with patch.dict(os.environ, {env_name: str(path)}, clear=False):
            return infrastructure_snapshot(service_id)


def test_valid_network_status_is_accepted_without_inventory():
    result = snapshot(clone_valid())
    assert result.state == "development"
    assert result.service_id == "goreecloud-network"
    assert result.production_approved is False
    assert len(result.capabilities) == 2
    assert result.integration_status()["state"] == "development"


def test_sensitive_flag_fails_closed_without_leaking_sentinel():
    payload = clone_valid()
    payload["privacy"]["contains_network_identifiers"] = True
    payload["secret_sentinel"] = "PEER-IP-SHOULD-NEVER-ESCAPE"
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "PEER-IP-SHOULD-NEVER-ESCAPE" not in result.detail


def test_unapproved_nested_field_fails_closed():
    payload = clone_valid()
    payload["producer"]["token"] = "private-token"
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "private-token" not in result.detail


def test_wrong_service_identity_fails_closed():
    payload = clone_valid()
    payload["producer"]["service_id"] = "goreecloud-gateway"
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "producer identity" in result.detail


def test_non_goreecloud_runtime_authority_fails_closed():
    payload = clone_valid()
    payload["producer"]["runtime_authority"] = "netbird-direct"
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "runtime authority" in result.detail


def test_duplicate_capability_fails_closed():
    payload = clone_valid()
    payload["capabilities"].append({"id": "private-connectivity", "state": "verified"})
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "duplicated" in result.detail


def test_unapproved_capability_field_fails_closed_without_leak():
    payload = clone_valid()
    payload["capabilities"][0]["peer"] = "private-peer-name"
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "private-peer-name" not in result.detail


def test_invalid_timestamp_fails_closed():
    payload = clone_valid()
    payload["generated_at"] = "September 1 2026"
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "timestamp" in result.detail


def test_stale_timestamp_fails_closed():
    payload = clone_valid()
    payload["generated_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=6)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "stale" in result.detail


def test_future_timestamp_fails_closed():
    payload = clone_valid()
    payload["generated_at"] = (
        datetime.now(timezone.utc) + timedelta(minutes=2)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result = snapshot(payload)
    assert result.state == "unavailable"
    assert "future" in result.detail


def test_status_file_read_is_hard_bounded():
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "status.json"
        path.write_bytes(b" " * (MAX_STATUS_BYTES + 1))
        with patch.dict(
            os.environ,
            {"GOREECLOUD_NETWORK_STATUS_FILE": str(path)},
            clear=False,
        ):
            result = infrastructure_snapshot("goreecloud-network")
    assert result.state == "unavailable"
    assert "size bound" in result.detail


def test_non_utf8_status_file_fails_closed():
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "status.json"
        path.write_bytes(b"\xff\xfe\xfd")
        with patch.dict(
            os.environ,
            {"GOREECLOUD_NETWORK_STATUS_FILE": str(path)},
            clear=False,
        ):
            result = infrastructure_snapshot("goreecloud-network")
    assert result.state == "unavailable"
    assert "safely read" in result.detail


def test_missing_configuration_is_unavailable():
    with patch.dict(os.environ, {}, clear=True):
        result = infrastructure_snapshot("goreecloud-gateway")
    assert result.state == "unavailable"
    assert "GOREECLOUD_GATEWAY_STATUS_FILE" in result.detail


def test_unknown_service_identity_is_rejected():
    result = infrastructure_snapshot("netbird")
    assert result.state == "unavailable"
    assert "Unknown" in result.detail
