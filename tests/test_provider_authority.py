from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta, timezone

from integrations.provider_authority import (
    EVERKEEP,
    PRIVACY_SHIELD,
    ProviderEvidenceError,
    integration_status,
    normalize_provider_evidence,
)

NOW = datetime(2026, 9, 12, 5, 0, tzinfo=timezone.utc)
MAX_EVIDENCE_AGE = timedelta(hours=1)


def evidence(authority):
    return {
        "producer": {
            "system": authority.system,
            "repository": authority.repository,
            "revision": "a" * 40,
        },
        "authority_domain": authority.authority_domain,
        "assertion": authority.assertion,
        "outcome": "provider-owned-state",
        "observed_at": "2026-09-12T04:30:00Z",
        "valid_until": "2026-09-12T05:30:00Z",
        "evidence_reference": "evidence+sha256:provider-record",
        "payload_digest": "sha256:" + "b" * 64,
        "contains_user_content": False,
        "contains_secret_material": False,
        "authority_transfer": False,
    }


class ProviderAuthorityTests(unittest.TestCase):
    def test_privacy_shield_current_evidence_remains_provider_owned(self):
        view = normalize_provider_evidence(
            evidence(PRIVACY_SHIELD),
            authority=PRIVACY_SHIELD,
            max_evidence_age=MAX_EVIDENCE_AGE,
            now=NOW,
        )
        self.assertEqual(view.state, "current")
        self.assertEqual(view.producer_outcome, "provider-owned-state")
        status = integration_status(view)
        self.assertEqual(status["state"], "available")
        self.assertIn("provider evidence only", status["detail"])

    def test_everkeep_current_evidence_remains_provider_owned(self):
        view = normalize_provider_evidence(
            evidence(EVERKEEP),
            authority=EVERKEEP,
            max_evidence_age=MAX_EVIDENCE_AGE,
            now=NOW,
        )
        self.assertEqual(view.authority_domain, "recovery")
        self.assertEqual(view.provider_system, "everkeep")
        self.assertTrue(view.current)

    def test_missing_manager_freshness_policy_cannot_produce_current_display(self):
        view = normalize_provider_evidence(evidence(PRIVACY_SHIELD), authority=PRIVACY_SHIELD, now=NOW)
        self.assertEqual(view.state, "stale")
        self.assertEqual(integration_status(view)["state"], "attention")

    def test_provider_validity_cannot_extend_manager_freshness_ceiling(self):
        raw = evidence(PRIVACY_SHIELD)
        raw["valid_until"] = "2027-09-12T05:30:00Z"
        view = normalize_provider_evidence(
            raw,
            authority=PRIVACY_SHIELD,
            max_evidence_age=timedelta(minutes=20),
            now=NOW,
        )
        self.assertEqual(view.state, "stale")
        self.assertEqual(view.effective_valid_until, datetime(2026, 9, 12, 4, 50, tzinfo=timezone.utc))

    def test_invalid_manager_freshness_policy_fails_closed(self):
        for value in (timedelta(0), timedelta(seconds=-1), "one hour"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ProviderEvidenceError, "positive duration"):
                    normalize_provider_evidence(
                        evidence(PRIVACY_SHIELD),
                        authority=PRIVACY_SHIELD,
                        max_evidence_age=value,
                        now=NOW,
                    )

    def test_stale_evidence_never_becomes_current_manager_truth(self):
        raw = evidence(EVERKEEP)
        raw["valid_until"] = "2026-09-12T04:45:00Z"
        view = normalize_provider_evidence(
            raw,
            authority=EVERKEEP,
            max_evidence_age=MAX_EVIDENCE_AGE,
            now=NOW,
        )
        self.assertEqual(view.state, "stale")
        self.assertEqual(integration_status(view)["state"], "attention")

    def test_wrong_repository_or_authority_fails_closed(self):
        raw = evidence(PRIVACY_SHIELD)
        raw["producer"]["repository"] = "GoreeCloud/goreecloud-manager"
        with self.assertRaises(ProviderEvidenceError):
            normalize_provider_evidence(raw, authority=PRIVACY_SHIELD, now=NOW)

        raw = evidence(PRIVACY_SHIELD)
        raw["authority_domain"] = "security"
        with self.assertRaises(ProviderEvidenceError):
            normalize_provider_evidence(raw, authority=PRIVACY_SHIELD, now=NOW)

    def test_authority_transfer_or_sensitive_payload_fails_closed(self):
        for field in ("authority_transfer", "contains_user_content", "contains_secret_material"):
            raw = evidence(EVERKEEP)
            raw[field] = True
            with self.assertRaises(ProviderEvidenceError):
                normalize_provider_evidence(raw, authority=EVERKEEP, now=NOW)

    def test_future_or_invalid_window_fails_closed(self):
        future = evidence(PRIVACY_SHIELD)
        future["observed_at"] = "2026-09-12T05:10:00Z"
        with self.assertRaises(ProviderEvidenceError):
            normalize_provider_evidence(future, authority=PRIVACY_SHIELD, now=NOW)

        inverted = evidence(PRIVACY_SHIELD)
        inverted["valid_until"] = "2026-09-12T04:00:00Z"
        with self.assertRaises(ProviderEvidenceError):
            normalize_provider_evidence(inverted, authority=PRIVACY_SHIELD, now=NOW)

    def test_naive_evaluation_clock_fails_closed(self):
        with self.assertRaises(ProviderEvidenceError):
            normalize_provider_evidence(
                evidence(PRIVACY_SHIELD),
                authority=PRIVACY_SHIELD,
                max_evidence_age=MAX_EVIDENCE_AGE,
                now=datetime(2026, 9, 12, 5, 0),
            )

    def test_extended_or_duplicate_semantics_are_not_silently_accepted(self):
        raw = evidence(EVERKEEP)
        raw["manager_override"] = "ready"
        with self.assertRaises(ProviderEvidenceError):
            normalize_provider_evidence(raw, authority=EVERKEEP, now=NOW)

        raw = copy.deepcopy(evidence(EVERKEEP))
        raw["payload_digest"] = "sha256:not-a-digest"
        with self.assertRaises(ProviderEvidenceError):
            normalize_provider_evidence(raw, authority=EVERKEEP, now=NOW)


if __name__ == "__main__":
    unittest.main()
