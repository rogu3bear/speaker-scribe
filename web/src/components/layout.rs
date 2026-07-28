use leptos::prelude::*;
use leptos_router::components::A;

/// Header and footer shared by every page.
///
/// Lives inside `Router` so the navigation links resolve client-side once
/// hydration has run, and as ordinary anchors before it.
#[component]
pub fn Layout(children: Children) -> impl IntoView {
    view! {
        <header class="masthead">
            <A href="/" attr:class="wordmark">
                <span class="wordmark-mark" aria-hidden="true"></span>
                "Speaker Scribe"
            </A>
            <nav>
                <a href="https://github.com/rogu3bear/speaker-scribe">"Source"</a>
                <A href="/privacy">"Privacy"</A>
                <A href="/terms">"Terms"</A>
            </nav>
        </header>

        {children()}

        <footer class="colophon">
            <p>
                "MIT licensed. Built with "
                <a href="https://github.com/ml-explore/mlx">"MLX"</a>", "
                <a href="https://github.com/snakers4/silero-vad">"Silero VAD"</a>" and "
                <a href="https://speechbrain.github.io/">"SpeechBrain"</a>"."
            </p>
            <p>"Your recordings stay on your Mac."</p>
        </footer>
    }
}
