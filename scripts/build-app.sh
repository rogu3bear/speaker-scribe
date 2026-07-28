#!/usr/bin/env bash
# Build Speaker Scribe.app and a DMG.
#
#   ./scripts/build-app.sh
#   SIGN_IDENTITY="Developer ID Application: NAME (TEAMID)" ./scripts/build-app.sh
#
# The app is self-contained: it carries its own Python, the speech stack, and a
# decode-only ffmpeg, so it runs on a Mac with no developer tooling installed.
# Needs a Rust toolchain to build. Notarization is a separate, credentialed step;
# see docs/packaging.md.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v cargo >/dev/null 2>&1 || {
  echo "cargo not found. Install Rust from https://rustup.rs" >&2
  exit 1
}

# One handler for every scratch path: separate `trap ... EXIT` calls replace each
# other rather than accumulating, so the earlier one would never run.
MACHO=""
STAGE=""
cleanup() {
  [ -n "$MACHO" ] && rm -f "$MACHO"
  [ -n "$STAGE" ] && rm -rf "$STAGE"
  return 0
}
trap cleanup EXIT

# Both are large and slow to produce, and neither changes between app builds, so
# they are built once and reused. Delete build/ to force a rebuild.
[ -x "build/runtime/py/bin/python3" ] || {
  echo "==> No bundled runtime yet"
  ./scripts/build-runtime.sh
}
[ -x "build/ffmpeg/bin/ffmpeg" ] || {
  echo "No ffmpeg at build/ffmpeg/bin/ffmpeg. Run ./scripts/build-ffmpeg.sh" >&2
  exit 1
}

echo "==> Building the UI"
pnpm build

# Only development builds use this: they have no bundled runtime and drive the
# checkout through uv instead.
export SPEAKER_SCRIBE_ROOT="$ROOT"

echo "==> Bundling"
# The DMG is built further down instead of by Tauri, because everything inside
# the app has to be signed first and Tauri would seal the image before that.
./node_modules/.bin/tauri build --bundles app

BUNDLE="$ROOT/src-tauri/target/release/bundle"
APP="$BUNDLE/macos/Speaker Scribe.app"
[ -d "$APP" ] || {
  echo "No app bundle at $APP" >&2
  exit 1
}

# Tauri copies resources by following symlinks. The Hugging Face cache layout
# stores each weight file once as a blob and links the snapshot at it, so that
# copy silently writes every model twice and adds half a gigabyte to the
# download. Replace the tree with one that keeps the links.
#
# Before signing, because signing seals the bundle's contents.
echo "==> Re-linking the bundled weights"
BEFORE="$(du -sk "$APP/Contents/Resources/models" | cut -f1)"
rm -rf "$APP/Contents/Resources/models"
cp -RP "$ROOT/build/models" "$APP/Contents/Resources/models"
AFTER="$(du -sk "$APP/Contents/Resources/models" | cut -f1)"
echo "    $((BEFORE / 1024)) MB -> $((AFTER / 1024)) MB"

if [ -n "${SIGN_IDENTITY:-}" ]; then
  echo "==> Signing as: ${SIGN_IDENTITY}"
  # Inside-out, and every Mach-O file rather than just the executable: the
  # notary service rejects a bundle containing any unsigned binary, and a Python
  # install is several thousand extension modules. Tauri signs the app it built,
  # which at that point did not include these.
  echo "    finding Mach-O files"
  MACHO="$(mktemp)"
  find "$APP/Contents/Resources" -type f \
    \( -name '*.so' -o -name '*.dylib' -o -perm -u+x \) -print0 |
    while IFS= read -r -d '' file; do
      # -perm -u+x also matches shell scripts and data; only sign real binaries.
      if file -b "$file" | grep -q 'Mach-O'; then
        printf '%s\0' "$file"
      fi
    done >"$MACHO"

  COUNT="$(tr -dc '\0' <"$MACHO" | wc -c | tr -d ' ')"
  echo "    signing $COUNT nested binaries"
  # With the same entitlements as the app, because the bundled interpreter is
  # spawned as its own process and a process gets the entitlements of its own
  # signature, not its parent's. Signed with the hardened runtime and nothing
  # else, Python would be refused the executable memory that MLX and numba both
  # need, and would fail at the first transcription rather than at launch.
  # Entitlements on a library are ignored, so applying them uniformly is simpler
  # than maintaining a list of which files are executables.
  xargs -0 -n 20 -P 8 codesign --force --timestamp --options runtime \
    --entitlements "$ROOT/src-tauri/entitlements.plist" \
    --sign "$SIGN_IDENTITY" <"$MACHO"

  echo "    signing the app"
  codesign --force --timestamp --options runtime \
    --entitlements "$ROOT/src-tauri/entitlements.plist" \
    --sign "$SIGN_IDENTITY" "$APP"
else
  echo "==> No SIGN_IDENTITY set: ad-hoc signing, this machine only"
  codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true
fi

echo
echo "==> Verifying signature"
codesign --verify --strict --verbose=2 "$APP" 2>&1 | sed 's/^/    /' || true

echo
echo "==> Building the DMG"
mkdir -p "$BUNDLE/dmg"
DMG="$BUNDLE/dmg/Speaker Scribe_$(node -p "require('$ROOT/src-tauri/tauri.conf.json').version")_aarch64.dmg"
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"
hdiutil create -volname "Speaker Scribe" -srcfolder "$STAGE" \
  -ov -format UDZO "$DMG" >/dev/null

if [ -n "${SIGN_IDENTITY:-}" ]; then
  codesign --force --timestamp --sign "$SIGN_IDENTITY" "$DMG"
fi

echo
echo "Built:"
echo "  $APP"
du -sh "$APP" | awk '{print "    " $1}'
echo "  $DMG"
du -sh "$DMG" | awk '{print "    " $1}'
if [ -z "${SIGN_IDENTITY:-}" ]; then
  echo
  echo "Ad-hoc signed: Gatekeeper will refuse this on another machine."
fi
