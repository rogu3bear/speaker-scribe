# Terms

Speaker Scribe is free and open-source software, licensed under the MIT licence
in `LICENSE`. That licence is the agreement. This page says in ordinary language
what it means and what using the software makes you responsible for.

## The software is provided as is

There is no warranty, express or implied, and no guarantee of accuracy,
availability or fitness for any purpose. Nobody is liable for any damage arising
from its use. This is the MIT licence's disclaimer, and it is not boilerplate
here: automatic transcription gets things wrong.

## It is not a service

Nothing is hosted. Installing the app does not create an account or an
arrangement with anyone. There is no support commitment, no uptime, and no
promise that a future version will exist or keep any current behaviour. You are
running a program on your own computer.

## Transcripts are drafts

Speech recognition misreads names, numbers, technical terms and crosstalk, and
speaker separation guesses at how many people are present and can merge or split
them. Output can be confidently wrong in ways that read as fluent.

Do not rely on it unreviewed where accuracy matters — medical, legal, financial,
journalistic, disciplinary or safety contexts. The tidy-text toggle exists partly
so that you can always read what was actually said rather than the cleaned-up
version.

## Recording other people is your responsibility

The software will process any audio you give it. Whether you were allowed to
record that audio, and whether you may now analyse it, is a question about your
situation and not about this program.

Recording consent law varies: some jurisdictions require every participant to
agree, not just one. Voice prints are biometric data under the GDPR, the Illinois
Biometric Information Privacy Act and similar laws, which impose their own
requirements even for local processing. Employment, education and healthcare
settings frequently add more.

By using Speaker Scribe you confirm that you have the rights and consents needed
for the recordings you process. That obligation is yours, and the design of the
software — local-only, no stored voice profiles, no identification of strangers —
reduces the surface but does not discharge it.

## What it will not do

Speaker Scribe does not identify unknown people from their voices, and will not
be extended to. It distinguishes voices within a single recording and lets you
label them. Matching a voice against a population is a different product and is
out of scope deliberately, not for lack of time.

## Third-party components

The app bundles open-source software under its own licences, including
`mlx-whisper` (MIT), `silero-vad` (MIT), SpeechBrain (Apache-2.0), PyTorch
(BSD-3-Clause), CPython (PSF) and an LGPL build of ffmpeg. Model weights are
covered by their own terms, published by whoever released them.

The ffmpeg included is compiled `--disable-gpl` specifically so that the bundle
stays MIT-licensed. If you rebuild it with GPL components enabled, what you
distribute is no longer under these terms.
