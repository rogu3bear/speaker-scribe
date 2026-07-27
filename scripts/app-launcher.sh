#!/bin/bash
# Launcher inside Speaker Scribe.app. Starts the local API, waits for it to
# answer, then opens the UI in the default browser.
#
# The bundle deliberately contains no Python runtime and no model weights: the
# speech stack alone is several gigabytes and the weights several more. It runs
# the checkout recorded at build time, which makes this a convenient way to
# start the app rather than something to hand to another machine.
set -uo pipefail

ROOT="__SPEAKER_SCRIBE_ROOT__"
PORT="${SPEAKER_SCRIBE_PORT:-8118}"
URL="http://127.0.0.1:${PORT}"
LOG="${HOME}/Library/Logs/SpeakerScribe.log"

mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
echo "--- launch $(date) ---"

die() {
  echo "$1"
  osascript -e "display alert \"Speaker Scribe\" message \"$1\" as critical" >/dev/null 2>&1
  exit 1
}

[ -d "$ROOT" ] || die "The project folder has moved. Rebuild the app with scripts/build-app.sh."

cd "$ROOT" || die "Could not open $ROOT"

# Already running? Just show it rather than starting a second copy.
if curl -fsS --max-time 2 "${URL}/api/health" >/dev/null 2>&1; then
  open "$URL"
  exit 0
fi

command -v uv >/dev/null 2>&1 || die "uv is not installed. See https://docs.astral.sh/uv/"

uv run --extra ml uvicorn speaker_scribe_backend.app:app \
  --app-dir backend --host 127.0.0.1 --port "$PORT" &
SERVER=$!

# First run syncs the environment, which can take a while.
for _ in $(seq 1 240); do
  if ! kill -0 "$SERVER" 2>/dev/null; then
    die "Speaker Scribe failed to start. See ${LOG}"
  fi
  if curl -fsS --max-time 2 "${URL}/api/health" >/dev/null 2>&1; then
    open "$URL"
    wait "$SERVER"
    exit 0
  fi
  sleep 1
done

kill "$SERVER" 2>/dev/null
die "Speaker Scribe did not come up in time. See ${LOG}"
