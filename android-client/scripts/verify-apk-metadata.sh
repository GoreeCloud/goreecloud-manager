#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash android-client/scripts/verify-apk-metadata.sh <debug-apk> <unsigned-release-apk> <evidence-output>

The verifier requires Android SDK apkanalyzer, resolved from APKANALYZER,
PATH, ANDROID_HOME, or ANDROID_SDK_ROOT. It records only non-secret package
identity, release metadata, and SHA-256 artifact identity.
EOF
}

if [[ $# -ne 3 ]]; then
  usage >&2
  exit 2
fi

DEBUG_APK="$1"
RELEASE_APK="$2"
EVIDENCE_OUTPUT="$3"

for apk in "$DEBUG_APK" "$RELEASE_APK"; do
  if [[ ! -f "$apk" ]]; then
    echo "APK not found: $apk" >&2
    exit 2
  fi
done

resolve_apkanalyzer() {
  if [[ -n "${APKANALYZER:-}" ]]; then
    printf '%s\n' "$APKANALYZER"
    return
  fi

  if command -v apkanalyzer >/dev/null 2>&1; then
    command -v apkanalyzer
    return
  fi

  local sdk_root="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
  if [[ -n "$sdk_root" && -d "$sdk_root/cmdline-tools" ]]; then
    find "$sdk_root/cmdline-tools" -type f -name apkanalyzer -print \
      | sort -V \
      | tail -n 1
  fi
}

APKANALYZER_BIN="$(resolve_apkanalyzer)"
if [[ -z "$APKANALYZER_BIN" || ! -x "$APKANALYZER_BIN" ]]; then
  echo "Unable to locate an executable Android SDK apkanalyzer binary." >&2
  exit 2
fi

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

DEBUG_APPLICATION_ID="$(query "$DEBUG_APK" application-id)"
DEBUG_VERSION_NAME="$(query "$DEBUG_APK" version-name)"
DEBUG_VERSION_CODE="$(query "$DEBUG_APK" version-code)"
DEBUG_MIN_SDK="$(query "$DEBUG_APK" min-sdk)"
DEBUG_TARGET_SDK="$(query "$DEBUG_APK" target-sdk)"
DEBUG_DEBUGGABLE="$(query "$DEBUG_APK" debuggable)"
DEBUG_SHA256="$(sha256sum "$DEBUG_APK" | awk '{print $1}')"

RELEASE_APPLICATION_ID="$(query "$RELEASE_APK" application-id)"
RELEASE_VERSION_NAME="$(query "$RELEASE_APK" version-name)"
RELEASE_VERSION_CODE="$(query "$RELEASE_APK" version-code)"
RELEASE_MIN_SDK="$(query "$RELEASE_APK" min-sdk)"
RELEASE_TARGET_SDK="$(query "$RELEASE_APK" target-sdk)"
RELEASE_DEBUGGABLE="$(query "$RELEASE_APK" debuggable)"
RELEASE_SHA256="$(sha256sum "$RELEASE_APK" | awk '{print $1}')"

require_equal "Debug application ID" "$DEBUG_APPLICATION_ID" "com.goreecloud.manager.debug"
require_equal "Debug version name" "$DEBUG_VERSION_NAME" "0.1.0-debug"
require_equal "Debug version code" "$DEBUG_VERSION_CODE" "1"
require_equal "Debug minimum SDK" "$DEBUG_MIN_SDK" "26"
require_equal "Debug target SDK" "$DEBUG_TARGET_SDK" "35"
require_equal "Debug debuggable state" "$DEBUG_DEBUGGABLE" "true"

require_equal "Release application ID" "$RELEASE_APPLICATION_ID" "com.goreecloud.manager"
require_equal "Release version name" "$RELEASE_VERSION_NAME" "0.1.0"
require_equal "Release version code" "$RELEASE_VERSION_CODE" "1"
require_equal "Release minimum SDK" "$RELEASE_MIN_SDK" "26"
require_equal "Release target SDK" "$RELEASE_TARGET_SDK" "35"
require_equal "Release debuggable state" "$RELEASE_DEBUGGABLE" "false"

mkdir -p "$(dirname "$EVIDENCE_OUTPUT")"
umask 077
cat > "$EVIDENCE_OUTPUT" <<EOF
GoreeCloud Manager Android package metadata acceptance

debug.sha256=$DEBUG_SHA256
debug.application_id=$DEBUG_APPLICATION_ID
debug.version_name=$DEBUG_VERSION_NAME
debug.version_code=$DEBUG_VERSION_CODE
debug.min_sdk=$DEBUG_MIN_SDK
debug.target_sdk=$DEBUG_TARGET_SDK
debug.debuggable=$DEBUG_DEBUGGABLE

release.sha256=$RELEASE_SHA256
release.application_id=$RELEASE_APPLICATION_ID
release.version_name=$RELEASE_VERSION_NAME
release.version_code=$RELEASE_VERSION_CODE
release.min_sdk=$RELEASE_MIN_SDK
release.target_sdk=$RELEASE_TARGET_SDK
release.debuggable=$RELEASE_DEBUGGABLE
EOF

echo "Android APK metadata verified."
echo "Evidence: $EVIDENCE_OUTPUT"
