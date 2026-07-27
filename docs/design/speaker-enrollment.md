# Speaker Enrollment — Design

Status: design only. No enrollment code exists yet.

## Why This Is Now Possible

Diarization moved to SpeechBrain ECAPA embeddings, which are exactly the vectors a voice
profile would store. Recognizing a returning speaker is the same cosine-distance
comparison the diarizer already performs between cluster centroids; see
`_widest_centroid_distance` in `backend/speaker_scribe_backend/diarize.py`.

The product value is specific: a transcription tool that remembers *your* recurring
speakers, locally. A hosted service structurally cannot offer this, because it requires
retaining voice prints — the thing nobody wants to upload.

## Boundaries

Read `ANCHOR.md` first. Its Privacy Truth section governs this feature and is normative.
The short version: embeddings only, local only, explicit action only, deletable, and
never used to identify anyone the user has not enrolled.

## Storage

`data/speakers.json`, alongside the existing job store and gitignored for the same reason.

```jsonc
{
  "id": "spk-<uuid4-hex>",
  "name": "Ryan",
  "centroid": [/* 192 floats, the ECAPA embedding dimension */],
  "samples": 37,          // windows the centroid averages, for later refinement
  "source_job_id": "…",   // provenance, so the user can see where it came from
  "created_at": "…"
}
```

Reuse `JobStore`'s conventions rather than inventing new ones: a `threading.Lock`, whole
file read/write through a pydantic `TypeAdapter`, and a model in `models.py`. A
`SpeakerProfileStore` alongside `JobStore` in `store.py` is the natural shape.

Storing the centroid rather than every window keeps the file small and bounds what a
leak of `data/` would expose. `samples` is retained so a later enrollment can update the
centroid as a running mean without re-deriving from audio.

## Enrollment Flow

Enrollment attaches to the rename interaction that already exists
(`PATCH /api/jobs/{id}/speakers`, `SpeakerPanel.tsx`), which is where the user already
tells the app who a speaker is.

1. User renames `SPEAKER_01` to "Ryan" on a completed job.
2. The UI offers, as a distinct opt-in control, "remember this voice".
3. On opt-in, the backend recomputes that cluster's window embeddings for the job's
   audio and stores their mean as a profile.

Step 3 needs the window embeddings, which are currently discarded after
`LocalDiarizer.diarize` returns. Two options, to decide when implementing:

- **Recompute on enrollment.** No storage cost, no change to the diarization path, and
  costs roughly the ~15s the golden test takes. Simplest, and enrollment is rare.
- **Cache embeddings per job.** Faster, but persists voice prints for every job whether
  or not the user ever enrolls anyone — which is exactly what the Privacy Truth says not
  to do by default.

Recompute is the default choice. It keeps "no enrollment without explicit action" true at
the storage layer, not just the UI layer.

## Matching

After `cluster_labels` produces clusters, and before `merge_turns`:

1. Compute each cluster's centroid.
2. Compare against every enrolled profile by cosine distance.
3. Adopt the profile's name when the distance is below `PROFILE_MATCH_DISTANCE` and the
   match is unambiguous — the runner-up must be meaningfully further away, or an
   ambiguous match should be left as an anonymous `SPEAKER_NN`.
4. Never merge two clusters just because both matched one profile. Report the conflict
   and stay anonymous; a wrong confident name is worse than no name.

Unmatched clusters keep today's `SPEAKER_NN` labels, so the feature degrades to current
behavior when no profile fits.

## The Open Question

`PROFILE_MATCH_DISTANCE` is unknown. It is a sibling of `MIN_SPEAKER_DISTANCE` (0.25),
which was itself chosen by reasoning rather than measurement.

This should be settled with data, not opinion. `backend/tests/test_diarize_golden.py`
established the pattern: freeze real output, measure the effect of a change. Extending
that harness to enrollment — same speaker across two recordings should match, different
speakers should not — is a prerequisite for choosing the threshold honestly.

Note the asymmetry in cost. A false positive puts a real person's name on someone else's
words; a false negative just leaves a label the user fixes by hand. The threshold should
be tuned conservatively against that asymmetry rather than for accuracy alone.

## Deletion

A profile delete endpoint plus a UI affordance, removing the entry and its vectors from
`data/speakers.json`. Existing transcripts keep the names already written into their job
records — deleting a voice print stops future recognition, it does not rewrite history.
This distinction should be stated in the UI so it is not mistaken for erasure.
