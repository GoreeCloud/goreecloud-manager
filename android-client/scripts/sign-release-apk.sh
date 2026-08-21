#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash android-client/scripts/sign-release-apk.sh <unsigned-apk> <signed-apk>

Required environment variables:
  ANDROID_KEYSTORE_FILE
  ANDROID_KEYSTORE_PASSWORD
  ANDROID_KEY_ALIAS
  ANDROID_KEY_PASSWORD

Optional environment variable:
  APKSIGNER  Absolute path to the Android SDK apksigner binary.

The signing keystore and all passwords must remain outside the repository.
EOF
}

if [[ $# -ne 2 ]]; then
  usage >&2
  exit 2
fi

UNSIGNED_APK="$1"
SIGNED_APK="$2"

: "${ANDROID_KEYSTORE_FILE:?ANDROID_KEYSTORE_FILE is required}"
: "${ANDROID_KEYSTORE_PASSWORD:?ANDROID_KEYSTORE_PASSWORD is required}"
: "${ANDROID_KEY_ALIAS:?ANDROID_KEY_ALIAS is required}"
: "${ANDROID_KEY_PASSWORD:?ANDROID_KEY_PASSWORD is required}"

if [[ ! -f "$UNSIGNED_APK" ]]; then
  echo "Unsigned APK not found: $UNSIGNED_APK" >&2
  exit 2
fi

if [[ ! -f "$ANDROID_KEYSTORE_FILE" ]]; then
  echo "Android signing keystore not found." >&2
  exit 2
fi

if [[ "$UNSIGNED_APK" == "$SIGNED_APK" ]]; then
  echo "Signed output must use a different path from the unsigned input." >&2
  exit 2
fi

if [[ -e "$SIGNED_APK" || -e "${SIGNED_APK}.sha256" || -e "${SIGNED_APK}.signature.txt" ]]; then
  echo "Refusing to overwrite an existing signed artifact or evidence file." >&2
  exit 2
fi

resolve_apksigner() {
  if [[ -n "${APKSIGNER:-}" ]]; then
    printf '%s\n' "$APKSIGNER"
    return
  fi

  if command -v apksigner >/dev/null 2>&1; then
    command -v apksigner
    return
  fi

  if [[ -n "${ANDROID_HOME:-}" && -d "${ANDROID_HOME}/build-tools" ]]; then
    find "${ANDROID_HOME}/build-tools" -mindepth 2 -maxdepth 2 -type f -name apksigner -print \
      | sort -V \
      | tail -n 1
    return
  fi

  if [[ -n "${ANDROID_SDK_ROOT:-}" && -d "${ANDROID_SDK_ROOT}/build-tools" ]]; then
    find "${ANDROID_SDK_ROOT}/build-tools" -mindepth 2 -maxdepth 2 -type f -name apksigner -print \
      | sort -V \
      | tail -n 1
    return
  fi
}

APKSIGNER_BIN="$(resolve_apksigner)"
if [[ -z "$APKSIGNER_BIN" || ! -x "$APKSIGNER_BIN" ]]; then
  echo "Unable to locate an executable Android SDK apksigner binary." >&2
  exit 2
fi

mkdir -p "$(dirname "$SIGNED_APK")"
umask 077

"$APKSIGNER_BIN" sign \
  --ks "$ANDROID_KEYSTORE_FILE" \
  --ks-key-alias "$ANDROID_KEY_ALIAS" \
  --ks-pass env:ANDROID_KEYSTORE_PASSWORD \
  --key-pass env:ANDROID_KEY_PASSWORD \
  --out "$SIGNED_APK" \
  "$UNSIGNED_APK"

"$APKSIGNER_BIN" verify --verbose --print-certs "$SIGNED_APK" \
  | tee "${SIGNED_APK}.signature.txt"

sha256sum "$SIGNED_APK" > "${SIGNED_APK}.sha256"

echo "Signed APK created and verified: $SIGNED_APK"
echo "Checksum: ${SIGNED_APK}.sha256"
echo "Signature evidence: ${SIGNED_APK}.signature.txt"
