#!/usr/bin/env bash
# Build Speaker Scribe.app and a DMG with Tauri.
#
#   ./scripts/build-app.sh
#   SIGN_IDENTITY="Developer ID Application: NAME (TEAMID)" ./scripts/build-app.sh
#
# Needs a Rust toolchain. Notarization is a separate, credentialed step; see
# docs/packaging.md.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v cargo >/dev/null 2>&1 || {
  echo "cargo not found. Install Rust from https://rustup.rs" >&2
  exit 1
}

echo "==> Building the UI"
pnpm build

# The window loads the local server, which runs from this checkout. Baked in so
# the app reports a clear error if the folder later moves.
export SPEAKER_SCRIBE_ROOT="$ROOT"

if [ -n "${SIGN_IDENTITY:-}" ]; then
  echo "==> Signing as: ${SIGN_IDENTITY}"
  export APPLE_SIGNING_IDENTITY="$SIGN_IDENTITY"
  # Required for notarization; harmless otherwise.
  export APPLE_HARDENED_RUNTIME=1
else
  echo "==> No SIGN_IDENTITY set: ad-hoc signing, this machine only"
fi

echo "==> Bundling"
./node_modules/.bin/tauri build

BUNDLE="$ROOT/src-tauri/target/release/bundle"
APP="$BUNDLE/macos/Speaker Scribe.app"

echo
echo "==> Verifying signature"
codesign --verify --deep --strict --verbose=2 "$APP" 2>&1 | sed 's/^/    /' || true

echo
echo "Built:"
echo "  $APP"
ls "$BUNDLE/dmg/"*.dmg 2>/dev/null | sed 's/^/  /' || true
if [ -z "${SIGN_IDENTITY:-}" ]; then
  echo
  echo "Ad-hoc signed: Gatekeeper will refuse this on another machine."
fi
