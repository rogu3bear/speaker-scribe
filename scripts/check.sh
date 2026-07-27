#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

pnpm build
pnpm test

# Exercise the engine the app actually runs. Without the ml extra the diarization
# golden guard silently skips, so the gate would report green while proving less
# than it claims. SPEAKER_SCRIBE_EXTRA=test drops to the light lane for machines
# that cannot install the speech stack.
if [ "${SPEAKER_SCRIBE_EXTRA:-ml}" = "ml" ]; then
  uv run --extra ml --extra test pytest
else
  uv run --extra test pytest
fi
