# Packaging Speaker Scribe as a macOS app

```bash
./scripts/build-app.sh          # build/Speaker Scribe.app, ad-hoc signed
```

Double-clicking the result starts the local API, waits for it to answer, and
opens the UI in the default browser. The API serves the built frontend itself,
so no vite dev server is involved. Logs go to `~/Library/Logs/SpeakerScribe.log`.

Regenerate the icon with `uv run --extra ml python scripts/make-icon.py`. It is
drawn from the same brand values as the UI rather than committed as an opaque
binary.

## What the bundle is, and is not

It is a **launcher**, not a self-contained application. It records the path of
the checkout it was built from and runs that. Move or delete the checkout and
the app reports the problem and exits.

This is deliberate. A genuinely portable bundle has to solve three problems that
a launcher sidesteps:

- **Size.** The speech stack is several gigabytes before any model weights, and
  the weights are several more. A self-contained app would be a very large
  download for a tool most people run on one machine.
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
SIGN_IDENTITY="Developer ID Application: YOUR NAME (TEAMID)" ./scripts/build-app.sh
security find-identity -v -p codesigning    # list available identities
```

The build already passes `--options runtime --timestamp`, both of which
notarization requires.

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
ditto -c -k --keepParent "build/Speaker Scribe.app" build/SpeakerScribe.zip
xcrun notarytool submit build/SpeakerScribe.zip --keychain-profile speaker-scribe --wait
xcrun stapler staple "build/Speaker Scribe.app"
spctl --assess --type execute -vv "build/Speaker Scribe.app"
```

`--wait` blocks until Apple returns a verdict. On rejection,
`xcrun notarytool log <submission-id> --keychain-profile speaker-scribe` gives
the reason; the usual causes are a missing hardened runtime or an unsigned
nested binary.

Note that notarizing the launcher only vouches for the launcher. It says nothing
about the Python environment it starts, which lives outside the bundle. That is
another reason the launcher is a convenience rather than a distribution channel.
