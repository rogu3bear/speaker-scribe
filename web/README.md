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

The download button points at the stable `Speaker.Scribe_aarch64.dmg` asset on
`releases/latest`, so it starts the download directly and shipping a new version
does not require redeploying the site.

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

Use an explicitly selected deployment-purpose cfctl profile pinned to the
intended account. From `web/`, register the repository with cfctl, qualify the
build, and require clean reviewed source before preparing the plan:

```bash
: "${SPEAKER_SCRIBE_CFCTL_PROFILE:?select a deployment-purpose profile}"
: "${SPEAKER_SCRIBE_CF_ACCOUNT_ID:?select its exact account}"
: "${SPEAKER_SCRIBE_ARTIFACT_SHA256:?supply the reviewed cfctl artifact-set digest}"
cfctl auth status "$SPEAKER_SCRIBE_CFCTL_PROFILE" --json
cfctl guide wrangler.deploy --json
```

Before preparing a plan, require `credential_available: true` in the auth
status result and verify that its profile ID and account ID equal the selected
profile and account above. Stop on any mismatch or unavailable credential;
passing `--account` explicitly does not prove that it matches the profile pin.

```bash
cfctl call wrangler.deploy \
  --profile "$SPEAKER_SCRIBE_CFCTL_PROFILE" \
  --account "$SPEAKER_SCRIBE_CF_ACCOUNT_ID" \
  --query "config=$(pwd)/wrangler.toml" \
  --query "name=speaker-scribe-web" \
  --query "message=source=$(git rev-parse HEAD) artifact-sha256=$SPEAKER_SCRIBE_ARTIFACT_SHA256" \
  --json
```

The digest must cover cfctl's complete artifact set with paths relative to the
owning Git repository, including `web/build/_worker.js` and `web/target/site`.
A hash of just the Worker, an asset-manifest hash, or a site-relative build
comparison digest is not interchangeable. No qualified artifact digest is
supplied here; cfctl validates the exact source and artifact identity.

The call prepares a plan. With the returned operation ID, inspect and approve
that exact plan, run it once, and inspect its verification:

```bash
: "${SPEAKER_SCRIBE_OPERATION_ID:?use the returned operation ID}"
cfctl plans show "$SPEAKER_SCRIBE_OPERATION_ID" --json
cfctl plans approve "$SPEAKER_SCRIBE_OPERATION_ID" --yes --json
cfctl plans run "$SPEAKER_SCRIBE_OPERATION_ID" --json
cfctl plans status "$SPEAKER_SCRIBE_OPERATION_ID" --json
```

Require successful verification and fresh domain/route readback before calling
the deployment complete. On uncertain execution, retain the operation ID and
inspect `cfctl plans status` for that ID and follow its reported recovery
action; do not replay the upload.

## State

Earlier local notes describe compilation, build, and deployment results; they
were not reverified for the current source in this documentation pass. Current
release status requires exact-source build evidence, the governed deployment
receipt, and fresh authenticated readback. This README is not that evidence.
