# Speaker Scribe Agent Notes

Read `/Users/star/.agent/CONTRACT.md` first.

## Repo

Speaker Scribe is a public open-source, local-first transcription web app. Keep work scoped to this repo and preserve the local-only processing boundary unless the user explicitly asks for a hosted service.

## Gates

- Frontend: `pnpm build` and `pnpm test`.
- Backend: `uv run --extra test pytest`.
- Full local gate: `./scripts/check.sh`.

## Protected Boundaries

- Do not create or disclose Hugging Face tokens.
- Do not upload user audio to external services.
- Do not enable pyannoteAI premium/cloud processing unless the user explicitly requests that exact service.
- Publishing or changing GitHub repo visibility is allowed only when the user explicitly asks for public open source release.
