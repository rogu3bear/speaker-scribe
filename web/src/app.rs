use leptos::prelude::*;
use leptos_meta::{provide_meta_context, Meta, Title};
// Only rendered into the server-side document shell.
#[cfg(feature = "ssr")]
use leptos_meta::MetaTags;
use leptos_router::{
    components::{Route, Router, Routes},
    SsrMode, StaticSegment, WildcardSegment,
};

use crate::components::home_page::HomePage;
use crate::components::layout::Layout;
use crate::components::legal_page::{PrivacyPage, TermsPage};

/// The HTML document around the app.
///
/// Server-only: the browser hydrates a document that already exists, so nothing
/// here runs client-side. Gated rather than left dead so the wasm bundle does
/// not carry it, and so the build stays warning-free and worth reading.
#[cfg(feature = "ssr")]
pub fn shell(options: LeptosOptions) -> impl IntoView {
    view! {
        <!DOCTYPE html>
        <html lang="en">
            <head>
                <meta charset="utf-8"/>
                <meta name="viewport" content="width=device-width, initial-scale=1"/>
                <link rel="icon" href="/favicon.svg" type="image/svg+xml"/>
                <meta name="theme-color" content="#0f766e"/>
                <AutoReload options=options.clone()/>
                <HashedStylesheet options=options.clone()/>
                <HydrationScript options=options/>
                <MetaTags/>
            </head>
            <body>
                <App/>
            </body>
        </html>
    }
}

#[component]
pub fn App() -> impl IntoView {
    provide_meta_context();

    view! {
        <Title text="Speaker Scribe — local transcription with speaker turns"/>
        <Meta
            name="description"
            content="Turn recordings into transcripts with speaker turns, entirely on your Mac. No account, no API key, no upload."
        />

        <Router>
            <Layout>
                <Routes fallback=|| view! { <NotFoundPage/> }.into_view()>
                    <Route path=StaticSegment("") view=HomePage ssr=SsrMode::OutOfOrder/>
                    <Route path=StaticSegment("privacy") view=PrivacyPage ssr=SsrMode::OutOfOrder/>
                    <Route path=StaticSegment("terms") view=TermsPage ssr=SsrMode::OutOfOrder/>

                    // Must stay last: it is what gives deep links and
                    // pre-hydration requests a full SSR shell rather than a
                    // bare 404 from the asset handler.
                    <Route path=WildcardSegment("any") view=NotFoundPage ssr=SsrMode::OutOfOrder/>
                </Routes>
            </Layout>
        </Router>
    }
}

#[component]
fn NotFoundPage() -> impl IntoView {
    view! {
        <section class="page">
            <h1>"Not found"</h1>
            <p>"That page does not exist. " <a href="/">"Back to the start."</a></p>
        </section>
    }
}

#[cfg(feature = "ssr")]
#[component]
fn HashedStylesheet(options: LeptosOptions) -> impl IntoView {
    let href = asset_href(&options, "css", crate::asset_hashes::CSS_HASH);

    view! { <link id="leptos" rel="stylesheet" href=href/> }
}

#[cfg(feature = "ssr")]
#[component]
fn HydrationScript(options: LeptosOptions) -> impl IntoView {
    let js_href = asset_href(&options, "js", crate::asset_hashes::JS_HASH);
    let wasm_href = asset_href(&options, "wasm", crate::asset_hashes::WASM_HASH);

    view! {
        <link rel="modulepreload" href=js_href/>
        <link rel="preload" href=wasm_href r#as="fetch" r#type="application/wasm"/>
        <script type="module">{hydration_script(&options)}</script>
    }
}

/// The inline module that starts hydration.
///
/// Shared with the CSP builder in `lib.rs`, which hashes this exact string to
/// allow it. Two copies of the script would mean a hash that does not match what
/// the page actually contains, and a site that renders but never hydrates.
#[cfg(feature = "ssr")]
pub fn hydration_script(options: &LeptosOptions) -> String {
    let js_href = asset_href(options, "js", crate::asset_hashes::JS_HASH);
    let wasm_href = asset_href(options, "wasm", crate::asset_hashes::WASM_HASH);
    format!(
        "import({js_href:?}).then(mod => {{ mod.default({{ module_or_path: {wasm_href:?} }}).then(() => {{ mod.hydrate(); }}); }});"
    )
}

#[cfg(feature = "ssr")]
fn asset_href(options: &LeptosOptions, extension: &str, hash: &str) -> String {
    let output_name = options.output_name.as_ref();
    let output_name = if output_name.is_empty() {
        env!("CARGO_PKG_NAME")
    } else {
        output_name
    };
    let pkg_dir = options.site_pkg_dir.as_ref();

    if hash.is_empty() {
        format!("/{pkg_dir}/{output_name}.{extension}")
    } else {
        format!("/{pkg_dir}/{output_name}.{hash}.{extension}")
    }
}
