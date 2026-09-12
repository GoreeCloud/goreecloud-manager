from copy import deepcopy
from datetime import datetime, timezone
from unittest import TestCase

from integrations.provider_authority import (
    MAX_PROVIDER_RECORDS,
    PRIVACY_SHIELD,
    ProviderEvidenceError,
    select_latest_provider_evidence,
)

NOW = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)


def evidence(*, observed_at: str, outcome: str, digest_char: str = "a") -> dict:
    return {
        "producer": {
            "system": PRIVACY_SHIELD.system,
            "repository": PRIVACY_SHIELD.repository,
            "revision": "b" * 40,
        },
        "authority_domain": PRIVACY_SHIELD.authority_domain,
        "assertion": PRIVACY_SHIELD.assertion,
        "outcome": outcome,
        "observed_at": observed_at,
        "valid_until": "2026-09-12T11:00:00Z",
        "evidence_reference": f"evidence:privacy:{digest_char}",
        "payload_digest": "sha256:" + digest_char * 64,
        "contains_user_content": False,
        "contains_secret_material": False,
        "authority_transfer": False,
    }


class LatestProviderEvidenceTests(TestCase):
    def test_selects_latest_observation_without_combining_outcomes(self) -> None:
        view = select_latest_provider_evidence(
            [
                evidence(
                    observed_at="2026-09-12T08:00:00Z",
                    outcome="older-provider-owned-state",
                ),
                evidence(
                    observed_at="2026-09-12T09:00:00Z",
                    outcome="latest-provider-owned-state",
                    digest_char="c",
                ),
            ],
            authority=PRIVACY_SHIELD,
            now=NOW,
        )
        self.assertEqual(view.producer_outcome, "latest-provider-owned-state")
        self.assertEqual(view.observed_at, datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc))

    def test_same_time_conflicting_latest_records_fail_closed(self) -> None:
        first = evidence(
            observed_at="2026-09-12T09:00:00Z",
            outcome="provider-state-a",
        )
        second = evidence(
            observed_at="2026-09-12T09:00:00Z",
            outcome="provider-state-b",
            digest_char="c",
        )
        with self.assertRaisesRegex(ProviderEvidenceError, "ambiguous"):
            select_latest_provider_evidence(
                [first, second],
                authority=PRIVACY_SHIELD,
                now=NOW,
            )

    def test_identical_latest_duplicates_do_not_manufacture_a_stronger_state(self) -> None:
        latest = evidence(
            observed_at="2026-09-12T09:00:00Z",
            outcome="provider-owned-state",
        )
        view = select_latest_provider_evidence(
            [latest, deepcopy(latest)],
            authority=PRIVACY_SHIELD,
            now=NOW,
        )
        self.assertEqual(view.producer_outcome, "provider-owned-state")
        self.assertEqual(view.provider_system, "privacy-shield")

    def test_invalid_older_record_still_fails_collection_closed(self) -> None:
        invalid = evidence(
            observed_at="2026-09-12T08:00:00Z",
            outcome="older-state",
        )
        invalid["authority_transfer"] = True
        with self.assertRaisesRegex(ProviderEvidenceError, "authority transfer"):
            select_latest_provider_evidence(
                [
                    invalid,
                    evidence(
                        observed_at="2026-09-12T09:00:00Z",
                        outcome="latest-state",
                        digest_char="c",
                    ),
                ],
                authority=PRIVACY_SHIELD,
                now=NOW,
            )

    def test_collection_size_is_bounded(self) -> None:
        sample = evidence(
            observed_at="2026-09-12T09:00:00Z",
            outcome="provider-owned-state",
        )
        with self.assertRaisesRegex(ProviderEvidenceError, "exceeds"):
            select_latest_provider_evidence(
                [deepcopy(sample) for _ in range(MAX_PROVIDER_RECORDS + 1)],
                authority=PRIVACY_SHIELD,
                now=NOW,
            )
