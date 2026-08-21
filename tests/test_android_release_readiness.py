from pathlib import Path
from unittest import TestCase


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "client-packaging.yml"
SIGNING_SCRIPT = REPOSITORY_ROOT / "android-client" / "scripts" / "sign-release-apk.sh"
SIGNING_DOC = REPOSITORY_ROOT / "docs" / "android-release-signing.md"
GITIGNORE = REPOSITORY_ROOT / ".gitignore"


class AndroidReleaseReadinessContractTests(TestCase):
    def test_client_packaging_builds_debug_and_unsigned_release_variants(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("assembleDebug assembleRelease", source)
        self.assertIn("app-debug.apk", source)
        self.assertIn("app-release-unsigned.apk", source)
        self.assertIn("goreecloud-manager-android-debug", source)
        self.assertIn("goreecloud-manager-android-release-unsigned", source)
        self.assertNotIn("ANDROID_KEYSTORE_PASSWORD", source)
        self.assertNotIn("ANDROID_KEY_PASSWORD", source)

    def test_signing_helper_requires_external_key_material_and_fails_closed(self):
        source = SIGNING_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("set -euo pipefail", source)
        for name in (
            "ANDROID_KEYSTORE_FILE",
            "ANDROID_KEYSTORE_PASSWORD",
            "ANDROID_KEY_ALIAS",
            "ANDROID_KEY_PASSWORD",
        ):
            self.assertIn(name, source)
        self.assertIn("--ks-pass env:ANDROID_KEYSTORE_PASSWORD", source)
        self.assertIn("--key-pass env:ANDROID_KEY_PASSWORD", source)
        self.assertIn("verify --verbose --print-certs", source)
        self.assertIn("sha256sum", source)
        self.assertIn("Refusing to overwrite", source)
        self.assertNotIn("--ks-pass pass:", source)
        self.assertNotIn("--key-pass pass:", source)

    def test_common_android_signing_containers_are_ignored(self):
        source = GITIGNORE.read_text(encoding="utf-8")
        for pattern in ("*.jks", "*.keystore", "*.p12", "*.pfx"):
            self.assertIn(pattern, source)

    def test_documentation_keeps_production_signing_separate_from_ci(self):
        source = SIGNING_DOC.read_text(encoding="utf-8")
        self.assertIn("intentionally unsigned", source)
        self.assertIn("outside the repository", source)
        self.assertIn("approved physical Android device", source)
        self.assertIn("protected signing environment", source)
        self.assertIn("does not by itself make an Android package a production or Stable release", source)
