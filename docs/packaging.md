# Packaging Speaker Scribe as a macOS app

```bash
./scripts/build-app.sh
```

Produces `src-tauri/target/release/bundle/macos/Speaker Scribe.app` and a DMG
beside it. Around 4 MB and 1.5 MB respectively, because Tauri uses the system
WebView rather than shipping a browser.

The app opens a native window, not a browser tab. On launch it starts the local
API, waits for it to answer, points the window at it, and stops the server again
when the window closes — unless a server was already running, in which case it
attaches to that one and leaves it alone. The API serves the built frontend
itself, so vite is only involved in development.

Building needs a Rust toolchain (`rustup`). Running the built app does not.

Regenerate the icon with `uv run --extra ml python scripts/make-icon.py`, then
`./node_modules/.bin/tauri icon assets/AppIcon-1024.png` to refresh the platform
sizes. It is drawn from the same brand values as the UI rather than committed as
an opaque binary.

`scripts/app-launcher.sh` is the previous shell-based launcher, kept only as a
fallback for a machine with no Rust toolchain. It opens the default browser
instead of a window.

## What the bundle is, and is not

The window and the server are packaged; **the Python environment is not**. The
app records the path of the checkout it was built from and runs that. Move or
delete the checkout and it reports the problem rather than failing obscurely.

This is deliberate. Vendoring the backend has to solve three problems:

- **Size.** The speech stack is several gigabytes before any model weights, and
  the weights are several more. The shell is 4 MB; the environment behind it is
  roughly a thousand times that.
- **ffmpeg licensing.** Audio decoding shells out to `ffmpeg`, and the common
  builds are GPL. Speaker Scribe is MIT. Shipping a GPL binary inside an MIT
  application in one bundle is a licensing decision, not a packaging detail.
  Distributing would mean an LGPL-only ffmpeg build, or keeping the dependency
  external as it is now.
- **MLX and Metal.** Bundling a framework that compiles Metal shaders at runtime
  is fiddly, and failures show up on other people's hardware rather than yours.

None of these are unsolvable. They are just a different project from "make it
double-clickable", which is what this script does.

## Signing

Ad-hoc signing (the default) is enough to run the app on the machine that built
it. Gatekeeper will refuse it anywhere else.

To sign properly:

```bash
security find-identity -v -p codesigning    # list available identities
SIGN_IDENTITY="Developer ID Application: YOUR NAME (TEAMID)" ./scripts/build-app.sh
```

The script sets `APPLE_SIGNING_IDENTITY` and enables the hardened runtime, both
of which notarization requires.

## Notarization

**There is no open-source route to notarization.** Apple requires a paid
Developer Program membership and a Developer ID Application certificate, and
offers no waiver for open-source projects. Being MIT licensed does not change
what Apple asks for. If you can sign with a Developer ID, it is because you hold
that membership already.

Notarization is also worth thinking about before doing: it attaches a named
identity, often a company one, to whatever is signed. That is a choice about
attribution, not just a technical step.

The steps, once you have decided:

```bash
# One time: store credentials in the keychain. This prompts for an
# app-specific password created at appleid.apple.com, not your Apple password.
xcrun notarytool store-credentials speaker-scribe \
  --apple-id "you@example.com" --team-id TEAMID

# Per release
SIGN_IDENTITY="Developer ID Application: YOUR NAME (TEAMID)" ./scripts/build-app.sh

BUNDLE=src-tauri/target/release/bundle
xcrun notarytool submit "$BUNDLE"/dmg/*.dmg --keychain-profile speaker-scribe --wait
xcrun stapler staple "$BUNDLE"/dmg/*.dmg
xcrun stapler staple "$BUNDLE/macos/Speaker Scribe.app"
spctl --assess --type execute -vv "$BUNDLE/macos/Speaker Scribe.app"
```

`--wait` blocks until Apple returns a verdict. On rejection,
`xcrun notarytool log <submission-id> --keychain-profile speaker-scribe` gives
the reason; the usual causes are a missing hardened runtime or an unsigned
nested binary.

Note that notarizing the launcher only vouches for the launcher. It says nothing
about the Python environment it starts, which lives outside the bundle. That is
another reason the launcher is a convenience rather than a distribution channel.
