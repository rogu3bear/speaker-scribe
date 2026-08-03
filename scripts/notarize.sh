#!/usr/bin/env bash
# Notarize the built disk image and prove the result.
#
#   ./scripts/notarize.sh
#   NOTARY_PROFILE=other-profile ./scripts/notarize.sh
#
# Submits to Apple, staples the ticket to both the image and the app inside it,
# and then checks what Gatekeeper actually says. Splitting these apart is how a
# release ends up stapled but never assessed, which reads as success and is not.
#
# Needs a notarytool keychain profile; see docs/packaging.md for creating one.
# Submission takes upwards of twenty minutes for an image this size.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROFILE="${NOTARY_PROFILE:-speaker-scribe}"
BUNDLE="$ROOT/src-tauri/target/release/bundle"
APP="$BUNDLE/macos/Speaker Scribe.app"
DMG="$BUNDLE/dmg/Speaker.Scribe_aarch64.dmg"

[ -f "$DMG" ] || {
  echo "No disk image at $DMG. Run ./scripts/build-app.sh first." >&2
  exit 1
}

# Notarizing an unsigned build wastes twenty minutes to be told it is unsigned.
#
# Read into a variable rather than piped into `grep -q`. Under `set -o pipefail`
# that pipeline reports the failure of whichever side exits non-zero, and grep -q
# closes the pipe the instant it matches, so codesign dies of SIGPIPE and the
# pipeline exits 141 — a successful match reported as a failure. Whether it
# happens at all depends on how codesign flushes, which makes it intermittent.
SIGNATURE="$(codesign -dv "$APP" 2>&1 || true)"
case "$SIGNATURE" in
  *TeamIdentifier=[A-Z0-9]*) ;;
  *)
    echo "$APP is not Developer ID signed." >&2
    echo "Rebuild with SIGN_IDENTITY set; see docs/packaging.md." >&2
    exit 1
    ;;
esac

echo "==> Submitting $(basename "$DMG") ($(du -h "$DMG" | cut -f1))"
xcrun notarytool submit "$DMG" --keychain-profile "$PROFILE" --wait

echo
echo "==> Stapling"
xcrun stapler staple "$DMG"
xcrun stapler staple "$APP"

echo
echo "==> Asking Gatekeeper"
# Against the copy inside the image rather than the build directory: that copy
# is what a user receives, and the two can differ if anything has run the app
# in place since it was built.
MOUNT="$ROOT/build/dmg-verify"
rm -rf "$MOUNT"
hdiutil attach "$DMG" -nobrowse -readonly -mountpoint "$MOUNT" >/dev/null
ASSESSMENT="$(spctl --assess --type execute -vv "$MOUNT/Speaker Scribe.app" 2>&1 || true)"
hdiutil detach "$MOUNT" >/dev/null
rm -rf "$MOUNT"

echo "$ASSESSMENT" | sed 's/^/    /'
case "$ASSESSMENT" in
  *"source=Notarized Developer ID"*) ;;
  *)
    echo "Gatekeeper did not accept the notarized image." >&2
    exit 1
    ;;
esac

echo
echo "Ready to publish:"
echo "  $DMG"
shasum -a 256 "$DMG" | awk '{print "  sha256: " $1}'
