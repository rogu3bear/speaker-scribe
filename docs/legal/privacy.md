# Privacy

Speaker Scribe has no server, no account, and no telemetry. There is nothing to
sign into and nothing that reports back. This page describes what the software
actually does, not what it intends to do.

## Your recordings

Audio you open stays on your Mac. It is decoded, transcribed and diarized by
code running on your own machine, and it is never uploaded, because there is
nowhere for it to be uploaded to. The same is true of the transcripts, the
speaker names you type, and everything you export.

In the packaged app these live in:

```
~/Library/Application Support/com.mlnavigator.speaker-scribe/
```

Deleting that folder deletes everything the app has kept. Running from source,
it is the `data/` directory in the checkout instead.

## Voice data

Telling speakers apart works by turning short windows of speech into numerical
voice prints, which are biometric data under laws including the GDPR and the
Illinois Biometric Information Privacy Act.

Those vectors are computed in memory to group one recording's speakers, and are
discarded when the job finishes. They are not written to disk, not attached to
your transcripts, and not matched against anything outside the file you are
working on. Speaker Scribe has no database of voices, and cannot identify a
person it has not been told about.

`SPEAKER_00` is a label meaning "the first distinct voice in this file". Naming
it is something you do, and the name is just text stored beside the transcript.

## Network access

The app makes no network request in order to transcribe. The model it ships with
is inside the application, so a first run works with the machine offline.

It reaches the network in exactly one case: when you press Download on a model in
the picker, it fetches that model's weights from Hugging Face. That request
contains the model name and nothing else — no audio, no transcript, no
identifier. Deleting a model is a local file operation.

Two things happen outside the app's control and are worth naming, because
"offline" is otherwise easy to overclaim:

- **macOS checks the app's notarization** with Apple the first time you open it.
  That is Gatekeeper verifying the developer signature, and it happens for every
  signed Mac application. It tells Apple that a notarized app was launched. It
  does not involve your recordings.
- **Hugging Face sees your IP address** when you choose to download a model, as
  any download does.

## What is not collected

No analytics. No crash reports. No usage counts. No unique identifier. No email
address. No opt-out, because there is no collection to opt out of.

## Children

This is a general-purpose tool with no accounts and no data collection, and is
not directed at children.

## Changes

This file is versioned in the repository alongside the code it describes. Its
history is the change log.
