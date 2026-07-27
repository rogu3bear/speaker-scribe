#!/usr/bin/env bash
# Build Speaker Scribe.app.
#
#   ./scripts/build-app.sh                     ad-hoc signed, this machine only
#   SIGN_IDENTITY="Developer ID Application: ..." ./scripts/build-app.sh
#
# Signing with a Developer ID is what notarization later requires; see
# docs/packaging.md for that step, which needs an Apple account and is not
# performed here.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

APP_NAME="Speaker Scribe"
BUNDLE_ID="com.mlnavigator.speaker-scribe"
OUT="${OUT_DIR:-$ROOT/build}"
APP="$OUT/${APP_NAME}.app"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)"

echo "==> Building the UI"
pnpm build

echo "==> Assembling ${APP}"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

sed "s|__SPEAKER_SCRIBE_ROOT__|$ROOT|g" scripts/app-launcher.sh \
  >"$APP/Contents/MacOS/SpeakerScribe"
chmod +x "$APP/Contents/MacOS/SpeakerScribe"

cat >"$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>${APP_NAME}</string>
  <key>CFBundleDisplayName</key><string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key><string>${BUNDLE_ID}</string>
  <key>CFBundleVersion</key><string>${VERSION}</string>
  <key>CFBundleShortVersionString</key><string>${VERSION}</string>
  <key>CFBundleExecutable</key><string>SpeakerScribe</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.productivity</string>
  <!-- The launcher opens a browser and exits nothing to the Dock beyond that. -->
  <key>LSUIElement</key><true/>
  <key>NSHumanReadableCopyright</key><string>MIT licensed. Audio never leaves this machine.</string>
</dict>
</plist>
PLIST

if [ -f "assets/AppIcon.icns" ]; then
  cp assets/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"
else
  echo "    (no assets/AppIcon.icns; the bundle will use the generic icon)"
fi

IDENTITY="${SIGN_IDENTITY:--}"
echo "==> Signing with: ${IDENTITY}"
# Hardened runtime and a timestamp are prerequisites for notarization; harmless
# when signing ad-hoc.
codesign --force --deep --options runtime --timestamp \
  --sign "$IDENTITY" "$APP" 2>&1 | sed 's/^/    /' || \
  codesign --force --deep --sign "$IDENTITY" "$APP"

echo "==> Verifying"
codesign --verify --deep --strict --verbose=2 "$APP" 2>&1 | sed 's/^/    /'

echo
echo "Built ${APP}"
if [ "$IDENTITY" = "-" ]; then
  echo "Ad-hoc signed: runs here, Gatekeeper will refuse it elsewhere."
fi
