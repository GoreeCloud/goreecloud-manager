#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${MANAGER_VERSION:-0.2.7}"
ARCH="${MANAGER_ARCH:-amd64}"
BUILD_ROOT="${ROOT}/build/deb"
APP_ROOT="${BUILD_ROOT}/opt/goreecloud-manager"
BIN_ROOT="${BUILD_ROOT}/usr/bin"
DESKTOP_ROOT="${BUILD_ROOT}/usr/share/applications"

rm -rf "${BUILD_ROOT}"
mkdir -p "${APP_ROOT}" "${BIN_ROOT}" "${DESKTOP_ROOT}" "${BUILD_ROOT}/DEBIAN" "${ROOT}/dist"

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --name goreecloud-manager \
  --onedir \
  --distpath "${ROOT}/build/pyinstaller-dist" \
  --workpath "${ROOT}/build/pyinstaller-work" \
  --specpath "${ROOT}/build" \
  "${ROOT}/desktop-client/run.py"

cp -a "${ROOT}/build/pyinstaller-dist/goreecloud-manager/." "${APP_ROOT}/"

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
Depends: openssh-client
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
