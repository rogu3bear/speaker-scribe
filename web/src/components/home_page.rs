use leptos::prelude::*;

/// Always points at whatever the newest published release is, so the site does
/// not need redeploying when the app ships a new version.
const DOWNLOAD_URL: &str = "https://github.com/rogu3bear/speaker-scribe/releases/latest";
const SOURCE_URL: &str = "https://github.com/rogu3bear/speaker-scribe";

struct Feature {
    title: &'static str,
    body: &'static str,
}

const FEATURES: [Feature; 6] = [
    Feature {
        title: "Speaker turns, not a wall of text",
        body: "Silero VAD finds the speech, SpeechBrain embeddings tell the voices apart, and \
               clustering works out how many people are talking. Turns are pooled into \
               paragraphs that read like a conversation.",
    },
    Feature {
        title: "Tidied or verbatim, your choice",
        body: "One toggle switches between cleaned-up prose and exactly what was said, fillers \
               and false starts intact. The verbatim text is always there, because a transcript \
               you cannot check against the recording is not much use.",
    },
    Feature {
        title: "Name the voices",
        body: "It detects that there are three people. You decide which one is Ana. Names apply \
               across the transcript and follow it into every export.",
    },
    Feature {
        title: "Pick your model",
        body: "Six Whisper models from Tiny to Large v3, with what each is good for and what it \
               costs in disk and time. Download and delete them from inside the app.",
    },
    Feature {
        title: "TXT, SRT or JSON",
        body: "Export with speaker names applied. Keep transcripts in an inbox, file them into \
               conversations, or archive them.",
    },
    Feature {
        title: "Works on a plane",
        body: "The model it needs is inside the app. First launch makes no network request to \
               transcribe, because there is nothing to ask for.",
    },
];

#[component]
pub fn HomePage() -> impl IntoView {
    view! {
        <main>
            <section class="hero">
                <h1>"Transcripts with speaker turns, entirely on your Mac."</h1>
                <p class="hero-sub">
                    "Speaker Scribe turns recordings into readable transcripts and works out who \
                     is speaking. No account, no API key, no upload — the whole speech stack runs \
                     on your own machine."
                </p>
                <div class="hero-actions">
                    <a class="button button--primary" href=DOWNLOAD_URL>
                        "Download for macOS"
                    </a>
                    <a class="button" href=SOURCE_URL>"Read the source"</a>
                </div>
                <p class="hero-note">
                    "Apple Silicon, macOS 13 or later. Signed and notarized. Around 1 GB, because \
                     the speech engine and a Whisper model come with it."
                </p>
            </section>

            <section class="band">
                <div class="band-inner">
                    <h2>"Why it is this size"</h2>
                    <p>
                        "Most local transcription tools ask you to install Python, a machine \
                         learning stack and ffmpeg first, then apologise when the versions do not \
                         line up. Speaker Scribe carries its own — a relocatable Python, MLX \
                         Whisper, the diarization stack, a small ffmpeg built for decoding audio \
                         and nothing else, and enough model weights to work the moment it opens."
                    </p>
                    <p>
                        "That is the download. What you get for it is an application that has no \
                         setup step and no way to be half-installed."
                    </p>
                </div>
            </section>

            <section class="features">
                <h2>"What it does"</h2>
                <div class="feature-grid">
                    {FEATURES
                        .iter()
                        .map(|feature| {
                            view! {
                                <article class="feature">
                                    <h3>{feature.title}</h3>
                                    <p>{feature.body}</p>
                                </article>
                            }
                        })
                        .collect_view()}
                </div>
            </section>

            <section class="band band--quiet">
                <div class="band-inner">
                    <h2>"What it will not do"</h2>
                    <p>
                        "It does not identify people from their voices. It tells voices apart \
                         within one recording and lets you label them; matching a voice against a \
                         population is a different product and is out of scope deliberately."
                    </p>
                    <p>
                        "It does not send your audio anywhere, and it collects nothing — no \
                         analytics, no crash reports, no identifier. The one time it uses the \
                         network is when you ask it to download a larger model."
                    </p>
                    <p>
                        "And it can be wrong. Speech recognition misreads names, numbers and \
                         crosstalk, sometimes fluently. Treat a transcript as a draft."
                    </p>
                </div>
            </section>

            <section class="closing">
                <h2>"Open source, MIT licensed"</h2>
                <p>
                    "Every part of the pipeline is inspectable, including how the diarizer decides \
                     where one speaker stops and the next begins."
                </p>
                <div class="hero-actions">
                    <a class="button button--primary" href=DOWNLOAD_URL>"Download"</a>
                    <a class="button" href=SOURCE_URL>"GitHub"</a>
                </div>
            </section>
        </main>
    }
}
