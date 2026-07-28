# Packaging Speaker Scribe as a macOS app

```bash
./scripts/build-ffmpeg.sh     # once: a decode-only LGPL ffmpeg
./scripts/build-runtime.sh    # once: a relocatable Python with the speech stack
./scripts/build-models.sh     # once: the weights that ship inside the app
./scripts/build-app.sh        # the bundle and the disk image
./scripts/verify-bundle.sh    # prove the result runs on its own
```

The first three are slow and their output does not change between app builds, so
`build-app.sh` reuses them and only rebuilds the runtime if it is missing. Delete
`build/` to start over.

The result is a self-contained application. It carries its own Python, the whole
speech stack, an ffmpeg, and enough model weights to transcribe and diarize the
first file the user opens. It runs on a Mac with no Python, no Homebrew, no Rust
and no network. Building it needs a Rust toolchain; running it does not.

| | |
| --- | --- |
| `Speaker Scribe.app` | ~1.6 GB |
| `Speaker Scribe_0.1.0_aarch64.dmg` | ~900 MB |

The app opens a native window, not a browser tab. On launch it shows a loading
page immediately, starts the local API, points the window at it when it answers,
and stops the server again when the window closes — unless a server was already
running, in which case it attaches to that one and leaves it alone. The API
serves the built frontend itself, so vite is only involved in development.

## What is inside

```
Speaker Scribe.app/Contents/Resources/
  runtime/      CPython 3.12 with mlx-whisper, torch, speechbrain, sklearn
  models/       hub/ for Whisper weights, speechbrain/ for speaker embeddings
  backend/      the FastAPI application, as source
  dist/         the built UI, served by that application
  ffmpeg        a 2.9 MB decode-only build
```

A development build has none of this and falls back to running the checkout
through `uv`, which is what `./scripts/dev.sh` and a local `cargo run` use.

### The runtime is not a virtualenv

This matters enough to state plainly, because the wrong version of it looks
correct on the build machine and fails everywhere else. A virtualenv records the
absolute path of its base interpreter in `pyvenv.cfg` and reads it at every
startup. Build one here, copy it into a bundle, and it still points at
`/Users/you/dev/speaker-scribe`. It works perfectly until it reaches a machine
where that path does not exist.

`python-build-standalone` interpreters resolve their prefix from `argv[0]`
instead, so `build-runtime.sh` installs the dependencies directly into the
interpreter and ships that. `verify-bundle.sh` exists to keep this honest.

### Where the app reads and writes

Nothing is written inside the bundle: it is signed, it may sit in a read-only
`/Applications`, and it is replaced wholesale on update. The Rust shell points
the server at `~/Library/Application Support/com.mlnavigator.speaker-scribe` for
transcripts, uploads and model caches.

The shipped weights are copied out of the bundle into that cache on first run
(`catalog.seed_bundled_models`). After that a bundled model is indistinguishable
from a downloaded one: it can be deleted to reclaim space, and it stays deleted.

### Which model ships

`small`, plus the speaker embedding model. Not a quality judgement — a size one.
GitHub rejects release assets over 2 GB, and the app is already a ~400 MB image
before any weights, so `large-v3-turbo` at 1.5 GB would leave almost no headroom.
`small` fits, works the moment the app opens, and the model picker downloads
anything larger on request. Change it with `BUNDLED_WHISPER=medium
./scripts/build-models.sh` if you are distributing some other way.

The embedding model is not optional. Diarization cannot run without it, and an
app that has to reach the network before it can tell two speakers apart is not
an offline app.

### ffmpeg licensing

Audio decoding shells out to ffmpeg, and the usual builds — including
Homebrew's — are configured `--enable-gpl`. Shipping one inside an MIT
application would put the whole bundle under the GPL.

`build-ffmpeg.sh` configures `--disable-gpl --disable-nonfree --disable-everything`
and switches on only the decoders needed to turn common audio formats into 16 kHz
mono PCM. Every one of those is LGPL, so nothing is lost. The result is 2.9 MB
rather than eighty, and its licence is unambiguous. The script prints the GPL
configure flags at the end, which should be empty.

## Verifying

```bash
./scripts/verify-bundle.sh
```

`./scripts/check.sh` says the source is correct. This says the artefact is
correct, which is a different claim and the one that has actually broken. It
starts the bundled server the way the Rust shell does, using nothing outside
`Contents/Resources`, with `HF_HUB_OFFLINE=1` and empty caches, then transcribes
a file end to end and checks speakers came back.

The offline flag is the point. Without it the script passes on any machine with a
warm model cache and a network connection, which is exactly the case it needs to
tell apart from a working install.

## Signing

Ad-hoc signing (the default) is enough to run the app on the machine that built
it. Gatekeeper will refuse it anywhere else.

```bash
security find-identity -v -p codesigning    # list available identities
SIGN_IDENTITY="Developer ID Application: YOUR NAME (TEAMID)" ./scripts/build-app.sh
```

The script signs every Mach-O file inside the bundle before signing the bundle
itself. There are several thousand of them, because a Python installation is
mostly extension modules, and the notary service rejects a bundle containing any
unsigned binary. Tauri signs the app it built, which does not include these, so
the pass is done here and the DMG is built afterwards rather than by Tauri.

`src-tauri/entitlements.plist` relaxes three hardened-runtime defaults, each
because something in the bundle genuinely needs it: MLX and numba both compile
code at runtime, and Python loads extension modules that PyPI did not sign with
this team's certificate. The file says which is which.

## Notarization

**There is no open-source route to notarization.** Apple requires a paid
Developer Program membership and a Developer ID Application certificate, and
offers no waiver for open-source projects. Being MIT licensed does not change
what Apple asks for. If you can sign with a Developer ID, it is because you hold
that membership already.

Notarization is also worth thinking about before doing: it attaches a named
identity, often a company one, to whatever is signed. That is a choice about
attribution, not just a technical step.

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

`--wait` blocks until Apple returns a verdict, which for a bundle this size takes
longer than it does for a small one. On rejection,
`xcrun notarytool log <submission-id> --keychain-profile speaker-scribe` gives the
reason; the usual causes are a missing hardened runtime or an unsigned nested
binary.

## Icons

Regenerate with `uv run --extra ml python scripts/make-icon.py`, then
`./node_modules/.bin/tauri icon assets/AppIcon-1024.png` to refresh the platform
sizes. The icon is drawn from the same brand values as the UI rather than
committed as an opaque binary.

`scripts/app-launcher.sh` is the previous shell-based launcher, kept only as a
fallback for a machine with no Rust toolchain. It opens the default browser
instead of a window, and it needs the checkout.
