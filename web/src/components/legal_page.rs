use leptos::prelude::*;
use leptos_meta::Title;

// Rendered from ../../docs/legal by build.rs — the same files the desktop app
// ships inside its bundle. In a monorepo the site's legal text and the app's
// can be one file rather than two that drift.
const TERMS_HTML: &str = include_str!(concat!(env!("OUT_DIR"), "/terms.html"));
const PRIVACY_HTML: &str = include_str!(concat!(env!("OUT_DIR"), "/privacy.html"));

#[component]
pub fn TermsPage() -> impl IntoView {
    view! {
        <Title text="Terms — Speaker Scribe"/>
        <LegalPage title="Terms" html=TERMS_HTML/>
    }
}

#[component]
pub fn PrivacyPage() -> impl IntoView {
    view! {
        <Title text="Privacy — Speaker Scribe"/>
        <LegalPage title="Privacy" html=PRIVACY_HTML/>
    }
}

#[component]
fn LegalPage(title: &'static str, html: &'static str) -> impl IntoView {
    view! {
        <main class="page prose">
            <h1>{title}</h1>
            // The markup is generated at build time from files in this
            // repository, so there is no untrusted input to sanitise.
            <div inner_html=html></div>
            <p class="prose-source">
                "This is the same text the app itself shows, rendered from "
                <a href="https://github.com/rogu3bear/speaker-scribe/tree/main/docs/legal">
                    "docs/legal"
                </a>
                "."
            </p>
        </main>
    }
}
