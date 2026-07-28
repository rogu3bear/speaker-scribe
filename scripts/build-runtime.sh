#!/usr/bin/env bash
# Build the self-contained Python runtime that ships inside Speaker Scribe.app.
#
#   ./scripts/build-runtime.sh
#
# The result is build/runtime/py: a relocatable CPython with the whole speech
# stack installed into its own site-packages. Copy it anywhere and it still
# runs, which is what lets it live inside an .app the user drags to any folder.
#
# Deliberately NOT a virtualenv. A venv records the absolute path of its base
# interpreter in pyvenv.cfg and reads it at every startup, so a venv built here
# and copied into a bundle keeps pointing at this checkout: it appears to work
# on the build machine and fails on any other. python-build-standalone resolves
# its prefix from argv[0] instead, so installing straight into the interpreter
# is the layout that actually survives being moved.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY_VERSION="${RUNTIME_PYTHON_VERSION:-3.12}"
OUT="$ROOT/build/runtime"
RUNTIME="$OUT/py"
REQUIREMENTS="$OUT/requirements.txt"

command -v uv >/dev/null 2>&1 || {
  echo "uv not found. See https://docs.astral.sh/uv/" >&2
  exit 1
}

mkdir -p "$OUT"

echo "==> Fetching a standalone CPython $PY_VERSION"
uv python install --install-dir "$OUT/download" "$PY_VERSION" >/dev/null

# uv leaves a version-agnostic symlink beside the real directory, and it is
# relative to the current directory rather than to itself, so it breaks the
# moment anything reads it from elsewhere. Take the concrete directory only.
SOURCE="$(find "$OUT/download" -maxdepth 1 -type d -name 'cpython-*' | sort | tail -1)"
[ -n "$SOURCE" ] || {
  echo "No standalone CPython found under $OUT/download" >&2
  exit 1
}
echo "    $(basename "$SOURCE")"

echo "==> Copying it to $RUNTIME"
rm -rf "$RUNTIME"
mkdir -p "$RUNTIME"
# -R without -P would follow the internal symlinks and double the tree.
cp -RP "$SOURCE/." "$RUNTIME/"

PYTHON="$RUNTIME/bin/python3"
[ -x "$PYTHON" ] || {
  echo "No interpreter at $PYTHON" >&2
  exit 1
}

# uv marks its interpreters externally managed (PEP 668) so that nobody installs
# into the shared copy it manages. This is a private copy that exists to be
# installed into, so the marker no longer describes it.
find "$RUNTIME/lib" -maxdepth 2 -name 'EXTERNALLY-MANAGED' -delete

echo "==> Exporting the locked dependency set"
# The bundle runs the app, not the test suite, so only the ml extra is included.
uv export --extra ml --no-hashes --no-emit-project --no-dev \
  --format requirements-txt -o "$REQUIREMENTS" >/dev/null

echo "==> Installing into the runtime's own site-packages"
"$PYTHON" -m pip install --quiet --no-cache-dir --no-input -r "$REQUIREMENTS"

echo "==> Pruning what an app never runs"
# Test suites, C headers and static archives are build-time artefacts. On this
# stack they are most of a gigabyte, and nothing imports them at runtime.
find "$RUNTIME/lib" -type d -name 'test' -prune -exec rm -rf {} + 2>/dev/null || true
find "$RUNTIME/lib" -type d -name 'tests' -prune -exec rm -rf {} + 2>/dev/null || true
find "$RUNTIME/lib" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "$RUNTIME/lib" -type f -name '*.a' -delete 2>/dev/null || true
rm -rf "$RUNTIME/lib/python3.12/site-packages/torch/include" 2>/dev/null || true
rm -rf "$RUNTIME/lib/python3.12/site-packages/torch/utils/benchmark" 2>/dev/null || true
rm -rf "$RUNTIME/share/man" "$RUNTIME/share/doc" 2>/dev/null || true

echo
echo "Built $RUNTIME"
du -sh "$RUNTIME" | awk '{print "  size: " $1}'
"$PYTHON" -c "import sys; print('  python:', sys.version.split()[0])"
