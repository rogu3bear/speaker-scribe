#!/usr/bin/env bun
// Wrap the generated Worker so static files are served from the asset binding
// rather than rendered by Leptos.
//
// Without this every request for a stylesheet or the wasm bundle goes through
// SSR and comes back as the 404 page with a 200 status, which is a page that
// looks like it loaded and has no styles.

import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";

const root = process.cwd();
const workerBundle = join(root, "build/index.js");
const shimPath = join(root, "build/_worker.js");

if (!existsSync(workerBundle)) {
  console.error(`[write-worker-shim] missing worker bundle: ${workerBundle}`);
  process.exit(1);
}

await mkdir(dirname(shimPath), { recursive: true });
await writeFile(
  shimPath,
  [
    'import LeptosWorker from "./index.js";',
    "",
    "const STATIC_ASSET_PATHS = [",
    '  "/asset-manifest.json",',
    '  "/favicon.svg",',
    "];",
    "",
    "const STATIC_ASSET_PREFIXES = [",
    '  "/pkg/",',
    "];",
    "",
    "function shouldServeAsset(pathname) {",
    "  return STATIC_ASSET_PATHS.includes(pathname)",
    "    || STATIC_ASSET_PREFIXES.some((prefix) => pathname.startsWith(prefix));",
    "}",
    "",
    "export default class extends LeptosWorker {",
    "  async fetch(request) {",
    "    const url = new URL(request.url);",
    "",
    "    if (shouldServeAsset(url.pathname)) {",
    "      return this.env.ASSETS.fetch(request);",
    "    }",
    "",
    "    return super.fetch(request);",
    "  }",
    "}",
    "",
  ].join("\n"),
);

console.log("[write-worker-shim] wrote build/_worker.js");
