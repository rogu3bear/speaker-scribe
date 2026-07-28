#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

cleanup() {
  jobs -pr | xargs -r kill
}
trap cleanup EXIT

# Naming the extra here makes the dev command self-sufficient: a checkout that has
# only ever run `uv sync --extra test` still gets the real engine installed before
# uvicorn starts, instead of failing on the first upload.
# Use SPEAKER_SCRIBE_EXTRA=test with SPEAKER_SCRIBE_ENGINE=mock for the light lane.
EXTRA="${SPEAKER_SCRIBE_EXTRA:-ml}"

# Watch only the backend package. Watching the whole tree meant a write anywhere
# under data/ -- a scratch script, an export -- restarted the worker and killed
# whatever transcript was in flight, which takes minutes on a long recording.
uv run --extra "$EXTRA" uvicorn speaker_scribe_backend.app:app \
  --app-dir backend \
  --host 127.0.0.1 \
  --port 8118 \
  --reload \
  --reload-dir backend/speaker_scribe_backend &

pnpm dev
