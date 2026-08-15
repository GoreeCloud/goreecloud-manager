#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
mkdir -p "$APP_DIR" "$ICON_DIR"
cp "$ROOT/assets/goreecloud-manager.svg" "$ICON_DIR/goreecloud-manager.svg"
cat > "$APP_DIR/goreecloud-manager.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=GoreeCloud Manager
Comment=Monitor and manage GoreeCloud infrastructure
Exec="$ROOT/scripts/start.sh"
Icon=goreecloud-manager
Terminal=false
Categories=System;Network;
StartupNotify=true
DESKTOP
chmod +x "$APP_DIR/goreecloud-manager.desktop"
echo "Desktop entry installed: $APP_DIR/goreecloud-manager.desktop"
