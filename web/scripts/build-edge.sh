#!/usr/bin/env bash
# Build the site for Cloudflare Workers.
#
#   ./scripts/build-edge.sh
#
# Order matters here. The assets have to be hashed before the Rust is compiled a
# second time, because the Content-Security-Policy allows the inline hydration
# script by the hash of its exact text, and that text contains the hashed asset
# filenames. Build the worker before hashing and the header describes a script
# the page no longer serves, so the site renders and never hydrates.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_CARGO_LEPTOS_VERSION="0.3.5"
EXPECTED_WORKER_BUILD_VERSION="0.7.5"

cd "$ROOT_DIR"

require_version() {
  local name="$1" expected="$2" actual="$3"
  if [ "$actual" != "$expected" ]; then
    printf '[build-edge] %s %s is required (found %s). Run ./scripts/bootstrap.sh.\n' \
      "$name" "$expected" "${actual:-nothing}" >&2
    exit 1
  fi
}

if ! cargo leptos --version >/dev/null 2>&1; then
  printf '[build-edge] cargo-leptos is not installed. Run ./scripts/bootstrap.sh.\n' >&2
  exit 1
fi
require_version cargo-leptos "$EXPECTED_CARGO_LEPTOS_VERSION" \
  "$(cargo leptos --version | awk '{print $2}')"

if ! command -v worker-build >/dev/null 2>&1; then
  printf '[build-edge] worker-build is not installed. Run ./scripts/bootstrap.sh.\n' >&2
  exit 1
fi
require_version worker-build "$EXPECTED_WORKER_BUILD_VERSION" \
  "$(worker-build --version | awk '{print $1}')"

if ! command -v bun >/dev/null 2>&1; then
  printf '[build-edge] bun is required. See https://bun.sh\n' >&2
  exit 1
fi

echo "==> Building the client bundle and stylesheet"
./scripts/with-wasm-bindgen-cli.sh cargo leptos build --release

echo "==> Hashing assets"
bun ./scripts/hash-assets.mjs
# shellcheck disable=SC1091
source "$ROOT_DIR/target/asset-hashes.env"

echo "==> Building the worker"
worker-build --release --features ssr

echo "==> Writing the worker shim"
bun ./scripts/write-worker-shim.mjs

echo
echo "Built build/_worker.js and target/site"
