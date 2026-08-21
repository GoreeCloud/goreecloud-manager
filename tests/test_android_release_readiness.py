import hashlib
import os
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "client-packaging.yml"
SIGNING_SCRIPT = REPOSITORY_ROOT / "android-client" / "scripts" / "sign-release-apk.sh"
METADATA_SCRIPT = REPOSITORY_ROOT / "android-client" / "scripts" / "verify-apk-metadata.sh"
SIGNED_RELEASE_VERIFIER = REPOSITORY_ROOT / "android-client" / "scripts" / "verify-signed-release-apk.sh"
SIGNING_DOC = REPOSITORY_ROOT / "docs" / "android-release-signing.md"
BUILD_GRADLE = REPOSITORY_ROOT / "android-client" / "app" / "build.gradle.kts"
GITIGNORE = REPOSITORY_ROOT / ".gitignore"


class AndroidReleaseReadinessContractTests(TestCase):
    def test_client_packaging_builds_debug_and_unsigned_release_variants(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("assembleDebug assembleRelease", source)
        self.assertIn("app-debug.apk", source)
        self.assertIn("app-release-unsigned.apk", source)
        self.assertIn("goreecloud-manager-android-debug", source)
        self.assertIn("goreecloud-manager-android-release-unsigned", source)
        self.assertIn("Verify release acceptance APK is unsigned", source)
        self.assertIn("APKSIGNER_BIN", source)
        self.assertIn("unexpectedly signed", source)
        self.assertIn("Verify Android package identity and release metadata", source)
        self.assertIn("verify-apk-metadata.sh", source)
        self.assertIn("android-package-metadata.txt", source)
        self.assertNotIn("ANDROID_KEYSTORE_PASSWORD", source)
        self.assertNotIn("ANDROID_KEY_PASSWORD", source)

    def test_release_variant_has_no_repository_signing_configuration(self):
        source = BUILD_GRADLE.read_text(encoding="utf-8")
        self.assertIn('applicationId = "com.goreecloud.manager"', source)
        self.assertIn('versionName = "0.1.0"', source)
        self.assertIn("versionCode = 1", source)
        self.assertIn("minSdk = 26", source)
        self.assertIn("targetSdk = 35", source)
        self.assertIn("release {", source)
        self.assertIn("isDebuggable = false", source)
        self.assertIn('applicationIdSuffix = ".debug"', source)
        self.assertIn('versionNameSuffix = "-debug"', source)
        self.assertNotIn("signingConfig", source)
        self.assertNotIn("signingConfigs", source)

    def test_metadata_helper_enforces_production_and_debug_package_identities(self):
        source = METADATA_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("set -euo pipefail", source)
        self.assertIn("APKANALYZER", source)
        self.assertIn("apkanalyzer", source)
        self.assertIn('"com.goreecloud.manager.debug"', source)
        self.assertIn('"com.goreecloud.manager"', source)
        self.assertIn('"0.1.0-debug"', source)
        self.assertIn('"0.1.0"', source)
        self.assertIn('"26"', source)
        self.assertIn('"35"', source)
        self.assertIn('"true"', source)
        self.assertIn('"false"', source)
        self.assertIn("sha256sum", source)
        self.assertIn("debug.sha256=", source)
        self.assertIn("release.sha256=", source)
        self.assertIn("release.application_id=", source)
        self.assertIn("release.debuggable=", source)

    def test_metadata_helper_has_valid_bash_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(METADATA_SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

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

    def test_signing_helper_has_valid_bash_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(SIGNING_SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

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
        self.assertIn("com.goreecloud.manager.debug", source)
        self.assertIn("com.goreecloud.manager", source)
        self.assertIn("android-package-metadata.txt", source)
        self.assertIn("SHA-256", source)

    def test_signed_release_verifier_binds_package_and_public_signer_identity(self):
        source = SIGNED_RELEASE_VERIFIER.read_text(encoding="utf-8")
        self.assertIn("set -euo pipefail", source)
        self.assertIn("release.sha256", source)
        self.assertIn("release.application_id", source)
        self.assertIn("com.goreecloud.manager", source)
        self.assertIn("verify --verbose --print-certs", source)
        self.assertIn("certificate SHA-256 digest", source)
        self.assertIn("signing.certificate_sha256=", source)
        self.assertIn("signature.verified=true", source)
        self.assertIn("Refusing to overwrite existing signed-release evidence", source)
        self.assertNotIn("ANDROID_KEYSTORE_PASSWORD", source)
        self.assertNotIn("ANDROID_KEY_PASSWORD", source)

    def test_signed_release_verifier_has_valid_bash_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(SIGNED_RELEASE_VERIFIER)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_signed_release_verifier_accepts_matching_public_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unsigned_apk = root / "app-release-unsigned.apk"
            signed_apk = root / "goreecloud-manager-release.apk"
            metadata = root / "android-package-metadata.txt"
            evidence = root / "signed-release-evidence.txt"
            apkanalyzer = root / "apkanalyzer"
            apksigner = root / "apksigner"

            unsigned_apk.write_bytes(b"accepted unsigned release")
            signed_apk.write_bytes(b"signed release")
            unsigned_sha256 = hashlib.sha256(unsigned_apk.read_bytes()).hexdigest()
            certificate_sha256 = "ab" * 32

            metadata.write_text(
                "\n".join(
                    (
                        "GoreeCloud Manager Android package metadata acceptance",
                        "",
                        f"release.sha256={unsigned_sha256}",
                        "release.application_id=com.goreecloud.manager",
                        "release.version_name=0.1.0",
                        "release.version_code=1",
                        "release.min_sdk=26",
                        "release.target_sdk=35",
                        "release.debuggable=false",
                        "",
                    )
                ),
                encoding="utf-8",
            )
            apkanalyzer.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
case "$2" in
  application-id) echo "com.goreecloud.manager" ;;
  version-name) echo "0.1.0" ;;
  version-code) echo "1" ;;
  min-sdk) echo "26" ;;
  target-sdk) echo "35" ;;
  debuggable) echo "false" ;;
  *) exit 3 ;;
esac
""",
                encoding="utf-8",
            )
            apksigner.write_text(
                f"""#!/usr/bin/env bash
set -euo pipefail
echo "Verifies"
echo "Signer #1 certificate SHA-256 digest: {certificate_sha256}"
""",
                encoding="utf-8",
            )
            apkanalyzer.chmod(0o755)
            apksigner.chmod(0o755)

            env = os.environ.copy()
            env["APKANALYZER"] = str(apkanalyzer)
            env["APKSIGNER"] = str(apksigner)
            result = subprocess.run(
                [
                    "bash",
                    str(SIGNED_RELEASE_VERIFIER),
                    str(unsigned_apk),
                    str(signed_apk),
                    str(metadata),
                    certificate_sha256.upper(),
                    str(evidence),
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            accepted = evidence.read_text(encoding="utf-8")
            self.assertIn(f"unsigned.sha256={unsigned_sha256}", accepted)
            self.assertIn(
                f"signed.sha256={hashlib.sha256(signed_apk.read_bytes()).hexdigest()}",
                accepted,
            )
            self.assertIn(f"signing.certificate_sha256={certificate_sha256}", accepted)
            self.assertIn("signature.verified=true", accepted)

    def test_signed_release_verifier_rejects_unapproved_certificate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unsigned_apk = root / "app-release-unsigned.apk"
            signed_apk = root / "goreecloud-manager-release.apk"
            metadata = root / "android-package-metadata.txt"
            evidence = root / "signed-release-evidence.txt"
            apkanalyzer = root / "apkanalyzer"
            apksigner = root / "apksigner"

            unsigned_apk.write_bytes(b"accepted unsigned release")
            signed_apk.write_bytes(b"signed release")
            unsigned_sha256 = hashlib.sha256(unsigned_apk.read_bytes()).hexdigest()
            certificate_sha256 = "ab" * 32

            metadata.write_text(
                "\n".join(
                    (
                        f"release.sha256={unsigned_sha256}",
                        "release.application_id=com.goreecloud.manager",
                        "release.version_name=0.1.0",
                        "release.version_code=1",
                        "release.min_sdk=26",
                        "release.target_sdk=35",
                        "release.debuggable=false",
                        "",
                    )
                ),
                encoding="utf-8",
            )
            apkanalyzer.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
case "$2" in
  application-id) echo "com.goreecloud.manager" ;;
  version-name) echo "0.1.0" ;;
  version-code) echo "1" ;;
  min-sdk) echo "26" ;;
  target-sdk) echo "35" ;;
  debuggable) echo "false" ;;
  *) exit 3 ;;
esac
""",
                encoding="utf-8",
            )
            apksigner.write_text(
                f"""#!/usr/bin/env bash
set -euo pipefail
echo "Signer #1 certificate SHA-256 digest: {certificate_sha256}"
""",
                encoding="utf-8",
            )
            apkanalyzer.chmod(0o755)
            apksigner.chmod(0o755)

            env = os.environ.copy()
            env["APKANALYZER"] = str(apkanalyzer)
            env["APKSIGNER"] = str(apksigner)
            result = subprocess.run(
                [
                    "bash",
                    str(SIGNED_RELEASE_VERIFIER),
                    str(unsigned_apk),
                    str(signed_apk),
                    str(metadata),
                    "cd" * 32,
                    str(evidence),
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Signing certificate SHA-256 mismatch", result.stderr)
            self.assertFalse(evidence.exists())
