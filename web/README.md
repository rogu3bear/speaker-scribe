# The Speaker Scribe website

A Leptos 0.8 site rendered on Cloudflare Workers. It exists to explain the app
and hand over the download; it stores nothing and asks for nothing.

```bash
./scripts/bootstrap.sh     # once: wasm target, cargo-leptos, worker-build
./scripts/build-edge.sh    # build
bunx wrangler@4.83.0 dev --local --ip 127.0.0.1 --port 57581
```

## Why it lives in this repository

Because the site and the app say the same things, and one of them is the app.

`build.rs` renders `../docs/legal/*.md` into the terms and privacy pages, so the
text on the website is the same file the desktop app ships inside its bundle and
the same file GitHub renders. Editing the privacy policy is one edit. In separate
repositories it would be one edit and a note to remember the other one.

The download button points at `releases/latest`, so shipping a new version of the
app does not require redeploying the site.

## What was removed from the template

This started from `leptos-cf`, which is a full-stack starter: D1 for
persistence, server functions under `/api/`, session cookies, a contact form with
abuse caps. None of it is here.

A static marketing page has no state to keep, and a page describing a tool whose
entire claim is that it stores nothing about you should not be issuing session
cookies to make that point. What was kept is the part that is genuinely hard: the
Worker entrypoint, the SSR-and-hydrate feature split, content-hashed assets, and
a Content-Security-Policy that allows the inline hydration script by hash rather
than by `unsafe-inline`.

## Build order

`scripts/build-edge.sh` runs the steps in an order that matters:

1. `cargo leptos build --release` produces the client bundle and stylesheet.
2. `hash-assets.mjs` renames them to include content hashes and exports those
   hashes.
3. `worker-build` compiles the Worker **with those hashes set**.
4. `write-worker-shim.mjs` wraps it so `/pkg/` is served from the asset binding.

Steps 2 and 3 cannot swap. The CSP allows the inline hydration script by the hash
of its exact text, and that text names the hashed asset files — so the filenames
have to be settled before the header is computed. Build the Worker first and the
site renders correctly and never hydrates, with a console error about a blocked
script and nothing else wrong.

## Deploying

```bash
bunx wrangler@4.83.0 deploy
```

Needs a Cloudflare account and a configured `wrangler` login. There is no D1
database to provision, which is most of the setup the template's README covers.

## State

Both feature sets compile clean for `wasm32-unknown-unknown`. The full edge build
and a deploy have not been run — `bootstrap.sh` installs a toolchain, which is a
decision for whoever runs it rather than something to do implicitly.
