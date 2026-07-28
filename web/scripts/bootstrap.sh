#!/usr/bin/env bash
# Install the toolchain the site build needs, at the versions it expects.
#
#   ./scripts/bootstrap.sh
set -euo pipefail

CARGO_LEPTOS_VERSION="0.3.5"
WORKER_BUILD_VERSION="0.7.5"

command -v cargo >/dev/null 2>&1 || {
  echo "cargo not found. Install Rust from https://rustup.rs" >&2
  exit 1
}
command -v bun >/dev/null 2>&1 || {
  echo "bun not found. See https://bun.sh" >&2
  exit 1
}

echo "==> wasm32 target"
rustup target add wasm32-unknown-unknown

echo "==> cargo-leptos $CARGO_LEPTOS_VERSION"
cargo install cargo-leptos --version "$CARGO_LEPTOS_VERSION" --locked

echo "==> worker-build $WORKER_BUILD_VERSION"
cargo install worker-build --version "$WORKER_BUILD_VERSION" --locked

echo
echo "Ready. Next: ./scripts/build-edge.sh"
