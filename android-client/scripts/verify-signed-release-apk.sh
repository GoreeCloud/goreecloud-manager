#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash android-client/scripts/verify-signed-release-apk.sh \
    <unsigned-apk> \
    <signed-apk> \
    <android-package-metadata.txt> \
    <expected-signing-certificate-sha256> \
    <evidence-output>

The expected signing-certificate SHA-256 fingerprint is public identity evidence.
Private signing keys, keystores, and passwords are not read by this verifier.

Required Android SDK tools:
  apkanalyzer
  apksigner

Optional environment variables:
  APKANALYZER  Absolute path to the Android SDK apkanalyzer binary.
  APKSIGNER    Absolute path to the Android SDK apksigner binary.
EOF
}

if [[ $# -ne 5 ]]; then
  usage >&2
  exit 2
fi

UNSIGNED_APK="$1"
SIGNED_APK="$2"
METADATA_FILE="$3"
EXPECTED_CERT_SHA256_RAW="$4"
EVIDENCE_OUTPUT="$5"

for path in "$UNSIGNED_APK" "$SIGNED_APK" "$METADATA_FILE"; do
  if [[ ! -f "$path" ]]; then
    echo "Required input not found: $path" >&2
    exit 2
  fi
done

if [[ -e "$EVIDENCE_OUTPUT" ]]; then
  echo "Refusing to overwrite existing signed-release evidence: $EVIDENCE_OUTPUT" >&2
  exit 2
fi

resolve_tool() {
  local explicit_path="$1"
  local command_name="$2"
  local sdk_subdir="$3"

  if [[ -n "$explicit_path" ]]; then
    printf '%s\n' "$explicit_path"
    return
  fi

  if command -v "$command_name" >/dev/null 2>&1; then
    command -v "$command_name"
    return
  fi

  local sdk_root="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
  if [[ -n "$sdk_root" && -d "${sdk_root}/${sdk_subdir}" ]]; then
    find "${sdk_root}/${sdk_subdir}" -type f -name "$command_name" -print \
      | sort -V \
      | tail -n 1
  fi
}

APKANALYZER_BIN="$(resolve_tool "${APKANALYZER:-}" apkanalyzer cmdline-tools)"
APKSIGNER_BIN="$(resolve_tool "${APKSIGNER:-}" apksigner build-tools)"

if [[ -z "$APKANALYZER_BIN" || ! -x "$APKANALYZER_BIN" ]]; then
  echo "Unable to locate an executable Android SDK apkanalyzer binary." >&2
  exit 2
fi

if [[ -z "$APKSIGNER_BIN" || ! -x "$APKSIGNER_BIN" ]]; then
  echo "Unable to locate an executable Android SDK apksigner binary." >&2
  exit 2
fi

normalize_fingerprint() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | tr -d '[:space:]:'
}

EXPECTED_CERT_SHA256="$(normalize_fingerprint "$EXPECTED_CERT_SHA256_RAW")"
if [[ ! "$EXPECTED_CERT_SHA256" =~ ^[0-9a-f]{64}$ ]]; then
  echo "Expected signing-certificate SHA-256 fingerprint must contain exactly 64 hexadecimal characters." >&2
  exit 2
fi

metadata_value() {
  local key="$1"
  local values=()
  mapfile -t values < <(
    awk -F= -v key="$key" '
      $1 == key {
        sub(/^[^=]*=/, "")
        print
      }
    ' "$METADATA_FILE"
  )

  if [[ ${#values[@]} -ne 1 ]]; then
    echo "Metadata must contain exactly one '$key=' entry." >&2
    exit 1
  fi

  printf '%s\n' "${values[0]}"
}

query() {
  local apk="$1"
  local field="$2"
  "$APKANALYZER_BIN" manifest "$field" "$apk" | tr -d '\r' | tail -n 1
}

require_equal() {
  local label="$1"
  local actual="$2"
  local expected="$3"
  if [[ "$actual" != "$expected" ]]; then
    echo "$label mismatch: expected '$expected', got '$actual'." >&2
    exit 1
  fi
}

METADATA_RELEASE_SHA256="$(metadata_value release.sha256)"
METADATA_APPLICATION_ID="$(metadata_value release.application_id)"
METADATA_VERSION_NAME="$(metadata_value release.version_name)"
METADATA_VERSION_CODE="$(metadata_value release.version_code)"
METADATA_MIN_SDK="$(metadata_value release.min_sdk)"
METADATA_TARGET_SDK="$(metadata_value release.target_sdk)"
METADATA_DEBUGGABLE="$(metadata_value release.debuggable)"

require_equal "Metadata release application ID" "$METADATA_APPLICATION_ID" "com.goreecloud.manager"
require_equal "Metadata release version name" "$METADATA_VERSION_NAME" "0.1.0"
require_equal "Metadata release version code" "$METADATA_VERSION_CODE" "1"
require_equal "Metadata release minimum SDK" "$METADATA_MIN_SDK" "26"
require_equal "Metadata release target SDK" "$METADATA_TARGET_SDK" "35"
require_equal "Metadata release debuggable state" "$METADATA_DEBUGGABLE" "false"

UNSIGNED_SHA256="$(sha256sum "$UNSIGNED_APK" | awk '{print $1}')"
require_equal "Unsigned release APK SHA-256" "$UNSIGNED_SHA256" "$METADATA_RELEASE_SHA256"

for apk_label in unsigned signed; do
  if [[ "$apk_label" == "unsigned" ]]; then
    apk="$UNSIGNED_APK"
  else
    apk="$SIGNED_APK"
  fi

  application_id="$(query "$apk" application-id)"
  version_name="$(query "$apk" version-name)"
  version_code="$(query "$apk" version-code)"
  min_sdk="$(query "$apk" min-sdk)"
  target_sdk="$(query "$apk" target-sdk)"
  debuggable="$(query "$apk" debuggable)"

  require_equal "${apk_label^} application ID" "$application_id" "$METADATA_APPLICATION_ID"
  require_equal "${apk_label^} version name" "$version_name" "$METADATA_VERSION_NAME"
  require_equal "${apk_label^} version code" "$version_code" "$METADATA_VERSION_CODE"
  require_equal "${apk_label^} minimum SDK" "$min_sdk" "$METADATA_MIN_SDK"
  require_equal "${apk_label^} target SDK" "$target_sdk" "$METADATA_TARGET_SDK"
  require_equal "${apk_label^} debuggable state" "$debuggable" "$METADATA_DEBUGGABLE"
done

SIGNATURE_OUTPUT="$(mktemp)"
trap 'rm -f "$SIGNATURE_OUTPUT"' EXIT

"$APKSIGNER_BIN" verify --verbose --print-certs "$SIGNED_APK" > "$SIGNATURE_OUTPUT"

mapfile -t CERT_SHA256_VALUES < <(
  sed -n -E \
    's/^Signer #[0-9]+ certificate SHA-256 digest:[[:space:]]*//p' \
    "$SIGNATURE_OUTPUT"
)

if [[ ${#CERT_SHA256_VALUES[@]} -ne 1 ]]; then
  echo "Expected exactly one signer certificate SHA-256 digest in apksigner evidence." >&2
  exit 1
fi

ACTUAL_CERT_SHA256="$(normalize_fingerprint "${CERT_SHA256_VALUES[0]}")"
if [[ ! "$ACTUAL_CERT_SHA256" =~ ^[0-9a-f]{64}$ ]]; then
  echo "apksigner returned an invalid signer certificate SHA-256 digest." >&2
  exit 1
fi

require_equal "Signing certificate SHA-256" "$ACTUAL_CERT_SHA256" "$EXPECTED_CERT_SHA256"

SIGNED_SHA256="$(sha256sum "$SIGNED_APK" | awk '{print $1}')"

mkdir -p "$(dirname "$EVIDENCE_OUTPUT")"
umask 077
cat > "$EVIDENCE_OUTPUT" <<EOF
GoreeCloud Manager Android signed release acceptance evidence

unsigned.sha256=$UNSIGNED_SHA256
signed.sha256=$SIGNED_SHA256
release.application_id=$METADATA_APPLICATION_ID
release.version_name=$METADATA_VERSION_NAME
release.version_code=$METADATA_VERSION_CODE
release.min_sdk=$METADATA_MIN_SDK
release.target_sdk=$METADATA_TARGET_SDK
release.debuggable=$METADATA_DEBUGGABLE
signing.certificate_sha256=$ACTUAL_CERT_SHA256
signature.verifier=apksigner
signature.verified=true
EOF

echo "Signed Android release evidence verified."
echo "Evidence: $EVIDENCE_OUTPUT"
