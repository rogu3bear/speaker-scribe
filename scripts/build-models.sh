#!/usr/bin/env bash
# Fetch the model weights that ship inside Speaker Scribe.app.
#
#   ./scripts/build-models.sh
#   BUNDLED_WHISPER=base ./scripts/build-models.sh
#
# Produces build/models, laid out the way catalog.seed_bundled_models() expects:
#
#   build/models/hub/models--mlx-community--whisper-small-mlx
#   build/models/speechbrain/spkrec-ecapa-voxceleb
#
# Which Whisper model ships is a size decision, not a quality one. GitHub refuses
# release assets over 2 GB, and the app on its own is already a 387 MB disk
# image, so large-v3-turbo would leave almost no headroom and take an hour to
# upload. Small fits comfortably, works offline the moment the app opens, and the
# model picker downloads anything larger on request.
#
# The speaker embedding model is not a choice: diarization cannot run without it,
# it is only 85 MB, and an app that has to reach the network before it can label
# a second speaker is not an offline app.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WHISPER="${BUNDLED_WHISPER:-small}"
OUT="$ROOT/build/models"
PYTHON="$ROOT/build/runtime/py/bin/python3"

[ -x "$PYTHON" ] || {
  echo "No bundled runtime. Run ./scripts/build-runtime.sh first." >&2
  exit 1
}

mkdir -p "$OUT"

echo "==> Fetching weights into $OUT"
HF_HOME="$OUT" \
  SPEAKER_SCRIBE_MODEL_CACHE="$OUT/speechbrain" \
  PYTHONPATH="$ROOT/backend" \
  "$PYTHON" - "$WHISPER" <<'PYTHON'
import sys

from huggingface_hub import snapshot_download

from speaker_scribe_backend import catalog
from speaker_scribe_backend.diarize import model_cache_dir

wanted = sys.argv[1]
entry = catalog.entry_for(wanted)
if entry is None:
    names = ", ".join(item.value for item in catalog.CATALOG)
    raise SystemExit(f"Unknown model {wanted!r}. Choose one of: {names}")

print(f"    {entry.label} ({entry.download_mb} MB)")
snapshot_download(entry.repo)

# Fetched through SpeechBrain rather than the hub API, so that what lands on
# disk is the directory layout SpeechBrain looks for at load time. Downloading
# the repo directly would produce a hub cache the loader does not read.
print("    Speaker embeddings (85 MB)")
from speechbrain.inference.speaker import EncoderClassifier

EncoderClassifier.from_hparams(
    source=catalog.EMBEDDING_REPO,
    savedir=str(model_cache_dir() / "spkrec-ecapa-voxceleb"),
    run_opts={"device": "cpu"},
)
PYTHON

# HF_HOME holds more than the cache; only the hub directory is worth shipping.
[ -d "$OUT/hub" ] || {
  echo "No hub cache produced under $OUT" >&2
  exit 1
}
rm -rf "$OUT/hub/.locks" "$OUT/token" "$OUT/stored_tokens" 2>/dev/null || true

# SpeechBrain fills its savedir with absolute symlinks into whichever hub cache
# happened to be in use. Shipping those verbatim produces an app that installs
# cleanly and then fails at the first diarization on every machine but this one,
# because the paths they point at do not exist there. Replace them with the real
# files, and drop the hub copy they pointed at so the weights ship exactly once.
SAVEDIR="$OUT/speechbrain/spkrec-ecapa-voxceleb"
[ -d "$SAVEDIR" ] || {
  echo "No embedding model produced at $SAVEDIR" >&2
  exit 1
}
echo "==> Resolving the embedding model's symlinks"
cp -RL "$SAVEDIR" "$SAVEDIR.real"
rm -rf "$SAVEDIR"
mv "$SAVEDIR.real" "$SAVEDIR"
rm -rf "$OUT/hub/models--speechbrain--spkrec-ecapa-voxceleb"

# Anything still dangling would fail the same way, just later and less obviously.
echo "==> Checking for links that point outside the bundle"
BROKEN="$(find "$OUT" -type l ! -exec test -e {} \; -print | head -5)"
[ -z "$BROKEN" ] || {
  echo "Broken symlinks would ship:" >&2
  echo "$BROKEN" >&2
  exit 1
}
ESCAPING="$(find "$OUT" -type l -lname '/*' | head -5)"
[ -z "$ESCAPING" ] || {
  echo "Absolute symlinks would ship and break on another machine:" >&2
  echo "$ESCAPING" >&2
  exit 1
}

echo
echo "Built $OUT"
du -sh "$OUT/hub" | awk '{print "  whisper:    " $1}'
du -sh "$OUT/speechbrain" | awk '{print "  embeddings: " $1}'
du -sh "$OUT" | awk '{print "  total:      " $1}'
