#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

cleanup() {
  jobs -pr | xargs -r kill
}
trap cleanup EXIT

uv run uvicorn speaker_scribe_backend.app:app \
  --app-dir backend \
  --host 127.0.0.1 \
  --port 8118 \
  --reload &

pnpm dev
