from __future__ import annotations

from datetime import datetime, timezone

from integrations.provider_authority import (
    EVERKEEP,
    PRIVACY_SHIELD,
    normalize_provider_evidence,
    provider_status_record,
)

NOW = datetime(2026, 9, 12, 5, 0, tzinfo=timezone.utc)


def evidence(authority, *, outcome: str = "provider-owned-state", valid_until: str = "2026-09-12T05:30:00Z"):
    return {
        "producer": {
            "system": authority.system,
            "repository": authority.repository,
            "revision": "a" * 40,
        },
        "authority_domain": authority.authority_domain,
        "assertion": authority.assertion,
        "outcome": outcome,
        "observed_at": "2026-09-12T04:30:00Z",
        "valid_until": valid_until,
        "evidence_reference": "evidence+sha256:provider-record",
        "payload_digest": "sha256:" + "b" * 64,
        "contains_user_content": False,
        "contains_secret_material": False,
        "authority_transfer": False,
    }


def test_structured_record_keeps_provider_outcome_separate_from_manager_prose() -> None:
    view = normalize_provider_evidence(
        evidence(PRIVACY_SHIELD, outcome="<b>provider-claim</b>"),
        authority=PRIVACY_SHIELD,
        now=NOW,
    )
    record = provider_status_record(view)

    assert record["provider_outcome"] == "<b>provider-claim</b>"
    assert "<b>provider-claim</b>" not in record["manager_detail"]
    assert record["manager_display_state"] == "available"
    assert record["manager_authority"] is False
    assert record["authority_transfer"] is False
    assert record["observed_at"] == "2026-09-12T04:30:00Z"
    assert record["valid_until"] == "2026-09-12T05:30:00Z"


def test_structured_record_preserves_stale_provider_evidence_as_attention() -> None:
    view = normalize_provider_evidence(
        evidence(EVERKEEP, valid_until="2026-09-12T04:45:00Z"),
        authority=EVERKEEP,
        now=NOW,
    )
    record = provider_status_record(view)

    assert record["provider_system"] == "everkeep"
    assert record["authority_domain"] == "recovery"
    assert record["manager_display_state"] == "attention"
    assert record["manager_authority"] is False
