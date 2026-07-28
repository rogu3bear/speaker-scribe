#!/usr/bin/env bash
# Prove that a built Speaker Scribe.app can actually run on its own.
#
#   ./scripts/verify-bundle.sh
#   ./scripts/verify-bundle.sh "/Applications/Speaker Scribe.app"
#
# Starts the server exactly the way the app's Rust shell starts it, using only
# what is inside the bundle, and checks that it comes up and reports the speech
# stack ready. A green ./scripts/check.sh says the source is correct; this says
# the thing that ships is correct, which is a different claim.
#
# Runs on a spare port and against a throwaway data directory, so it is safe to
# run while the development server and a real store are live.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="${1:-$ROOT/src-tauri/target/release/bundle/macos/Speaker Scribe.app}"
RESOURCES="$APP/Contents/Resources"
PORT="${VERIFY_PORT:-8119}"
DATA="$ROOT/build/bundle-smoke"
LOG="$ROOT/build/bundle-smoke.log"

[ -d "$RESOURCES" ] || {
  echo "No bundle at $APP" >&2
  exit 1
}

for required in runtime/bin/python3 ffmpeg backend/speaker_scribe_backend dist/index.html \
  models/hub models/speechbrain/spkrec-ecapa-voxceleb; do
  [ -e "$RESOURCES/$required" ] || {
    echo "Bundle is missing $required" >&2
    exit 1
  }
done
echo "==> Bundle contains a runtime, ffmpeg, weights, the backend and the UI"

# A link pointing outside the bundle resolves on the machine that built it and
# nowhere else, which is the failure this whole script exists to catch early.
ESCAPING="$(find "$RESOURCES/models" -type l -lname '/*' | head -5)"
[ -z "$ESCAPING" ] || {
  echo "Bundled weights contain absolute symlinks:" >&2
  echo "$ESCAPING" >&2
  exit 1
}

rm -rf "$DATA"
mkdir -p "$DATA"

echo "==> Starting the bundled server on port $PORT"
# HF_HUB_OFFLINE makes any attempt to reach Hugging Face fail rather than
# quietly download what should already be inside the bundle. Without it this
# script would pass on a machine with a warm cache and a network connection,
# which is precisely the situation it is meant to distinguish from a working
# offline install. The caches start empty, so everything used below has to have
# come out of the app.
SPEAKER_SCRIBE_DATA="$DATA" \
  SPEAKER_SCRIBE_UI="$RESOURCES/dist" \
  SPEAKER_SCRIBE_FFMPEG="$RESOURCES/ffmpeg" \
  SPEAKER_SCRIBE_BUNDLED_MODELS="$RESOURCES/models" \
  HF_HOME="$DATA/models" \
  SPEAKER_SCRIBE_MODEL_CACHE="$DATA/model-cache" \
  HF_HUB_OFFLINE=1 \
  PATH="$RESOURCES:$PATH" \
  "$RESOURCES/runtime/bin/python3" -m uvicorn speaker_scribe_backend.app:app \
  --app-dir "$RESOURCES/backend" --host 127.0.0.1 --port "$PORT" \
  >"$LOG" 2>&1 &
SERVER=$!
trap 'kill "$SERVER" 2>/dev/null || true' EXIT

HEALTH=""
for _ in $(seq 1 120); do
  if HEALTH="$(curl -fsS --max-time 2 "http://127.0.0.1:$PORT/api/health" 2>/dev/null)"; then
    break
  fi
  if ! kill -0 "$SERVER" 2>/dev/null; then
    echo "The bundled server exited while starting:" >&2
    tail -20 "$LOG" >&2
    exit 1
  fi
  sleep 1
done

[ -n "$HEALTH" ] || {
  echo "The bundled server never answered. Log:" >&2
  tail -20 "$LOG" >&2
  exit 1
}

echo "    health: $HEALTH"
case "$HEALTH" in
  *'"ml_ready":true'*) ;;
  *)
    echo "The bundled runtime reports the speech stack unavailable." >&2
    exit 1
    ;;
esac

echo "==> Checking the UI is served from inside the bundle"
curl -fsS --max-time 5 "http://127.0.0.1:$PORT/" | grep -q '<div id="root">' || {
  echo "The bundled server did not serve the UI." >&2
  exit 1
}

echo "==> Checking the bundled model was seeded into the empty cache"
MODELS="$(curl -fsS --max-time 10 "http://127.0.0.1:$PORT/api/models")"
case "$MODELS" in
  *'"value":"small","repo":"mlx-community/whisper-small-mlx"'*'"state":"available"'*) ;;
  *)
    echo "The bundled model did not appear as available. Got:" >&2
    echo "$MODELS" >&2
    exit 1
    ;;
esac
echo "    small: available"

AUDIO="${VERIFY_AUDIO:-$ROOT/data/fixtures/_probe_short.wav}"
if [ ! -f "$AUDIO" ]; then
  echo
  echo "No audio at $AUDIO, so the transcription check was skipped." >&2
  echo "Bundle verified as far as startup: $APP"
  exit 0
fi

echo "==> Transcribing offline with the bundled model"
JOB="$(curl -fsS --max-time 30 -X POST "http://127.0.0.1:$PORT/api/jobs" \
  -F "file=@$AUDIO" -F "model=small" -F "diarize=true")"
JOB_ID="$(printf '%s' "$JOB" | sed -n 's/.*"id":"\([a-f0-9]*\)".*/\1/p')"
[ -n "$JOB_ID" ] || {
  echo "Could not read a job id from: $JOB" >&2
  exit 1
}

for _ in $(seq 1 300); do
  STATE="$(curl -fsS --max-time 5 "http://127.0.0.1:$PORT/api/jobs/$JOB_ID")"
  case "$STATE" in
    *'"status":"completed"'*)
      echo "    completed"
      break
      ;;
    *'"status":"failed"'*)
      echo "The job failed:" >&2
      echo "$STATE" >&2
      exit 1
      ;;
  esac
  sleep 1
done

case "$STATE" in
  *'"status":"completed"'*) ;;
  *)
    echo "The job never finished." >&2
    exit 1
    ;;
esac

# A completed job with no speakers would mean diarization silently did nothing,
# which is the half of the pipeline that depends on the shipped embedding model.
case "$STATE" in
  *'"speakers":[{'*) echo "    speakers labelled" ;;
  *)
    echo "The transcript came back with no speakers:" >&2
    echo "$STATE" >&2
    exit 1
    ;;
esac

echo
echo "Bundle verified offline: $APP"
