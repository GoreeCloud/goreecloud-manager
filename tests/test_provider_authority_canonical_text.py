from datetime import datetime, timezone
import unittest

from integrations.provider_authority import (
    PRIVACY_SHIELD,
    ProviderEvidenceError,
    normalize_provider_evidence,
)

NOW = datetime(2026, 9, 12, 8, 20, tzinfo=timezone.utc)


def evidence() -> dict:
    return {
        "producer": {
            "system": PRIVACY_SHIELD.system,
            "repository": PRIVACY_SHIELD.repository,
            "revision": "a" * 40,
        },
        "authority_domain": PRIVACY_SHIELD.authority_domain,
        "assertion": PRIVACY_SHIELD.assertion,
        "outcome": "provider-owned-state",
        "observed_at": "2026-09-12T08:00:00Z",
        "valid_until": "2026-09-12T09:00:00Z",
        "evidence_reference": "evidence+sha256:provider-record",
        "payload_digest": "sha256:" + "b" * 64,
        "contains_user_content": False,
        "contains_secret_material": False,
        "authority_transfer": False,
    }


class ProviderAuthorityCanonicalTextTests(unittest.TestCase):
    def test_authority_evidence_does_not_accept_whitespace_normalization(self) -> None:
        mutations = (
            ("producer.revision", lambda raw: raw["producer"].__setitem__("revision", " " + "a" * 40)),
            ("outcome", lambda raw: raw.__setitem__("outcome", "provider-owned-state ")),
            ("evidence_reference", lambda raw: raw.__setitem__("evidence_reference", " evidence+sha256:provider-record")),
            ("payload_digest", lambda raw: raw.__setitem__("payload_digest", "sha256:" + "b" * 64 + " ")),
            ("observed_at", lambda raw: raw.__setitem__("observed_at", " 2026-09-12T08:00:00Z")),
        )

        for field, mutate in mutations:
            with self.subTest(field=field):
                raw = evidence()
                mutate(raw)
                with self.assertRaisesRegex(ProviderEvidenceError, "canonical"):
                    normalize_provider_evidence(raw, authority=PRIVACY_SHIELD, now=NOW)


if __name__ == "__main__":
    unittest.main()
