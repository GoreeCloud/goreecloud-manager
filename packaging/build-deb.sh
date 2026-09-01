#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${MANAGER_VERSION:-0.2.9}"
ARCH="${MANAGER_ARCH:-amd64}"
SOURCE_REVISION="${MANAGER_SOURCE_REVISION:-local}"
BUILD_ROOT="${ROOT}/build/deb"
APP_ROOT="${BUILD_ROOT}/opt/goreecloud-manager"
BIN_ROOT="${BUILD_ROOT}/usr/bin"
DESKTOP_ROOT="${BUILD_ROOT}/usr/share/applications"
ICON_ROOT="${BUILD_ROOT}/usr/share/icons/hicolor/scalable/apps"
DOC_ROOT="${BUILD_ROOT}/usr/share/doc/goreecloud-manager"
THIRD_PARTY_ROOT="${DOC_ROOT}/third-party"

rm -rf "${BUILD_ROOT}"
mkdir -p "${APP_ROOT}" "${BIN_ROOT}" "${DESKTOP_ROOT}" "${ICON_ROOT}" \
  "${DOC_ROOT}" "${THIRD_PARTY_ROOT}" "${BUILD_ROOT}/DEBIAN" "${ROOT}/dist"

SOURCE_VERSION="$(python3 -c 'from pathlib import Path; ns={}; exec(Path("desktop-client/goreecloud_manager/__init__.py").read_text(), ns); print(ns["__version__"])')"
if [[ "${SOURCE_VERSION}" != "${VERSION}" ]]; then
  echo "Package version ${VERSION} does not match desktop client ${SOURCE_VERSION}." >&2
  exit 1
fi

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --name goreecloud-manager \
  --onedir \
  --collect-all PySide6 \
  --distpath "${ROOT}/build/pyinstaller-dist" \
  --workpath "${ROOT}/build/pyinstaller-work" \
  --specpath "${ROOT}/build" \
  "${ROOT}/desktop-client/run.py"

PYI_ROOT="${ROOT}/build/pyinstaller-dist/goreecloud-manager"
XCB_PLUGIN="$(find "${PYI_ROOT}" -type f -name 'libqxcb.so' -print -quit)"
if [[ -z "${XCB_PLUGIN}" ]]; then
  echo "PyInstaller output is missing the Qt xcb platform plugin (libqxcb.so)." >&2
  exit 1
fi

cp -a "${PYI_ROOT}/." "${APP_ROOT}/"
install -m 0644 "${ROOT}/desktop-client/assets/goreecloud-manager.svg" "${ICON_ROOT}/goreecloud-manager.svg"
install -m 0644 "${ROOT}/LICENSE" "${DOC_ROOT}/LICENSE"
install -m 0644 "${ROOT}/THIRD_PARTY_NOTICES.md" "${DOC_ROOT}/THIRD_PARTY_NOTICES.md"
python3 "${ROOT}/packaging/collect-python-license-material.py" "${THIRD_PARTY_ROOT}"

cat > "${DOC_ROOT}/copyright" <<'EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: GoreeCloud Manager
Source: https://github.com/GoreeCloud/goreecloud-manager
Files: *
Copyright: 2026 LaDamian Goree / GoreeCloud
License: AGPL-3.0-only
 The GoreeCloud Manager license notice is installed as
 /usr/share/doc/goreecloud-manager/LICENSE.
 Third-party and separately licensed material is documented in
 /usr/share/doc/goreecloud-manager/THIRD_PARTY_NOTICES.md and the
 /usr/share/doc/goreecloud-manager/third-party/ directory.
EOF

cat > "${DOC_ROOT}/SOURCE" <<EOF
GoreeCloud Manager Corresponding Source
Repository: https://github.com/GoreeCloud/goreecloud-manager
Source revision: ${SOURCE_REVISION}

This package was produced from the repository above. For acceptance and release
artifacts, use the exact source revision recorded here to obtain the corresponding
source and build scripts. Third-party components remain governed by their own terms.
EOF

if [[ ! -s "${DOC_ROOT}/LICENSE" || ! -s "${DOC_ROOT}/copyright" || ! -s "${DOC_ROOT}/SOURCE" ]]; then
  echo "Required GoreeCloud Manager package licensing material is missing." >&2
  exit 1
fi
if ! find "${THIRD_PARTY_ROOT}" -type f -size +0c -print -quit | grep -q .; then
  echo "Bundled third-party license material is missing." >&2
  exit 1
fi

cat > "${BIN_ROOT}/goreecloud-manager" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exec /opt/goreecloud-manager/goreecloud-manager "$@"
EOF
chmod 0755 "${BIN_ROOT}/goreecloud-manager"

cat > "${DESKTOP_ROOT}/goreecloud-manager.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=GoreeCloud Manager
Comment=Read-only GoreeCloud administration and operations console
Exec=/usr/bin/goreecloud-manager
Icon=goreecloud-manager
Terminal=false
Categories=System;Monitor;
StartupNotify=true
EOF
chmod 0644 "${DESKTOP_ROOT}/goreecloud-manager.desktop"

cat > "${BUILD_ROOT}/DEBIAN/control" <<EOF
Package: goreecloud-manager
Version: ${VERSION}
Section: admin
Priority: optional
Architecture: ${ARCH}
Maintainer: GoreeCloud
Depends: openssh-client, libgl1, libegl1, libdbus-1-3, libxkbcommon0, libxkbcommon-x11-0, libxcb1, libxcb-cursor0, libxcb-xinerama0, libxcb-xkb1
Description: GoreeCloud Manager desktop operations console
 Privacy-first, read-only GoreeCloud administration and monitoring client using the Glaze UI design language and Wardveil Security conventions.
EOF

cat > "${BUILD_ROOT}/DEBIAN/postinst" <<'EOF'
#!/usr/bin/env bash
set -e
chmod -R go-w /opt/goreecloud-manager
exit 0
EOF
chmod 0755 "${BUILD_ROOT}/DEBIAN/postinst"

dpkg-deb --root-owner-group --build "${BUILD_ROOT}" "${ROOT}/dist/goreecloud-manager_${VERSION}_${ARCH}.deb"
sha256sum "${ROOT}/dist/goreecloud-manager_${VERSION}_${ARCH}.deb" > "${ROOT}/dist/goreecloud-manager_${VERSION}_${ARCH}.deb.sha256"
