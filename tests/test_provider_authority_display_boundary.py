from datetime import datetime, timedelta, timezone

from integrations.provider_authority import (
    PRIVACY_SHIELD,
    integration_status,
    normalize_provider_evidence,
)


def test_manager_authored_status_does_not_echo_opaque_provider_outcome():
    raw = {
        "producer": {
            "system": PRIVACY_SHIELD.system,
            "repository": PRIVACY_SHIELD.repository,
            "revision": "a" * 40,
        },
        "authority_domain": PRIVACY_SHIELD.authority_domain,
        "assertion": PRIVACY_SHIELD.assertion,
        "outcome": "<b>protected-everywhere</b>",
        "observed_at": "2026-09-12T06:00:00Z",
        "valid_until": "2026-09-12T08:00:00Z",
        "evidence_reference": "evidence+sha256:provider-record",
        "payload_digest": "sha256:" + "b" * 64,
        "contains_user_content": False,
        "contains_secret_material": False,
        "authority_transfer": False,
    }
    view = normalize_provider_evidence(
        raw,
        authority=PRIVACY_SHIELD,
        max_evidence_age=timedelta(hours=2),
        now=datetime(2026, 9, 12, 7, 0, tzinfo=timezone.utc),
    )

    status = integration_status(view)
    assert status["state"] == "available"
    assert view.producer_outcome == "<b>protected-everywhere</b>"
    assert view.producer_outcome not in status["detail"]
    assert "does not reinterpret" in status["detail"]
