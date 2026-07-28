#!/usr/bin/env bash
# Record docs/demo.gif against a throwaway store of invented data.
#
# Runs its own server on port 8119 and its own Chrome profile, so a real job
# store and a real browser session are never involved.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CHROME" ] || { echo "Google Chrome not found" >&2; exit 1; }

cleanup() {
  [ -n "${SERVER:-}" ] && kill "$SERVER" 2>/dev/null || true
  [ -n "${BROWSER:-}" ] && kill "$BROWSER" 2>/dev/null || true
}
trap cleanup EXIT

echo "==> Building the UI"
pnpm build >/dev/null

echo "==> Seeding invented data"
uv run --extra ml python scripts/make-demo-store.py

echo "==> Starting a demo server on 8119"
SPEAKER_SCRIBE_DATA="$ROOT/data/demo-store" \
  uv run --extra ml uvicorn speaker_scribe_backend.app:app \
  --app-dir backend --host 127.0.0.1 --port 8119 >/dev/null 2>&1 &
SERVER=$!

for _ in $(seq 1 60); do
  curl -fsS --max-time 2 http://127.0.0.1:8119/api/health >/dev/null 2>&1 && break
  sleep 1
done

echo "==> Starting headless Chrome"
"$CHROME" --headless=new --remote-debugging-port=9222 \
  --user-data-dir="$ROOT/data/demo-chrome" \
  --hide-scrollbars --force-device-scale-factor=2 \
  about:blank >/dev/null 2>&1 &
BROWSER=$!
sleep 3

echo "==> Recording"
uv run --extra ml python scripts/record-demo.py
