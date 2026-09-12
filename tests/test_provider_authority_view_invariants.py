from datetime import datetime, timezone
from unittest import TestCase

from integrations.provider_authority import (
    PRIVACY_SHIELD,
    ProviderEvidenceError,
    ProviderEvidenceView,
)


class ProviderEvidenceViewInvariantTests(TestCase):
    def valid_kwargs(self) -> dict:
        return {
            "provider_system": PRIVACY_SHIELD.system,
            "authority_domain": PRIVACY_SHIELD.authority_domain,
            "assertion": PRIVACY_SHIELD.assertion,
            "producer_revision": "a" * 40,
            "producer_outcome": "provider-owned-state",
            "observed_at": datetime(2026, 9, 12, 8, 0, tzinfo=timezone.utc),
            "valid_until": datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc),
            "evidence_reference": "evidence+sha256:provider-record",
            "payload_digest": "sha256:" + "b" * 64,
            "state": "current",
        }

    def test_direct_view_rejects_ungoverned_provider_system(self) -> None:
        values = self.valid_kwargs()
        values["provider_system"] = "manager"
        with self.assertRaisesRegex(ProviderEvidenceError, "system is not governed"):
            ProviderEvidenceView(**values)

    def test_direct_view_rejects_mismatched_authority_domain(self) -> None:
        values = self.valid_kwargs()
        values["authority_domain"] = "recovery"
        with self.assertRaisesRegex(ProviderEvidenceError, "authority domain mismatch"):
            ProviderEvidenceView(**values)

    def test_direct_view_rejects_noncanonical_provider_text(self) -> None:
        values = self.valid_kwargs()
        values["producer_outcome"] = " provider-owned-state"
        with self.assertRaisesRegex(ProviderEvidenceError, "canonical"):
            ProviderEvidenceView(**values)

    def test_direct_view_rejects_invalid_validity_window(self) -> None:
        values = self.valid_kwargs()
        values["valid_until"] = values["observed_at"]
        with self.assertRaisesRegex(ProviderEvidenceError, "validity window"):
            ProviderEvidenceView(**values)

    def test_direct_view_rejects_unknown_display_state(self) -> None:
        values = self.valid_kwargs()
        values["state"] = "protected"
        with self.assertRaisesRegex(ProviderEvidenceError, "state is invalid"):
            ProviderEvidenceView(**values)
