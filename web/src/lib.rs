mod app;
// Only the server builds asset URLs; the browser is handed them in the HTML.
#[cfg(feature = "ssr")]
mod asset_hashes;
mod components;

#[cfg(feature = "ssr")]
const CONTENT_SECURITY_POLICY_HEADER: &str = "content-security-policy";
#[cfg(feature = "ssr")]
const X_FRAME_OPTIONS_HEADER: &str = "x-frame-options";

/// The Worker entrypoint.
///
/// This site is entirely static: it renders the same pages for everybody, holds
/// no state, sets no cookies and has no server functions. The template this came
/// from carries sessions, a D1 binding and an origin-checked `/api/` surface for
/// its demo, and none of that is here — a page that describes a local-first app
/// should not be collecting anything to describe it.
#[cfg(feature = "ssr")]
#[worker::event(fetch)]
async fn fetch(
    req: worker::HttpRequest,
    _env: worker::Env,
    _ctx: worker::Context,
) -> worker::Result<axum::http::Response<axum::body::Body>> {
    use axum::Router;
    use leptos::prelude::*;
    use leptos_axum::{generate_route_list, LeptosRoutes};
    use tower_service::Service;

    let conf =
        get_configuration(None).map_err(|error| worker::Error::RustError(error.to_string()))?;
    let leptos_options = conf.leptos_options;
    let content_security_policy = content_security_policy(&leptos_options)?;

    let routes = generate_route_list(app::App);
    let mut router = Router::new()
        .leptos_routes(&leptos_options, routes, {
            let leptos_options = leptos_options.clone();
            move || app::shell(leptos_options.clone())
        })
        .with_state(leptos_options);

    let mut response = router.call(req).await?;
    apply_response_headers(&mut response, &content_security_policy)?;

    Ok(response)
}

#[cfg(feature = "ssr")]
fn apply_response_headers(
    response: &mut axum::http::Response<axum::body::Body>,
    content_security_policy: &axum::http::header::HeaderValue,
) -> worker::Result<()> {
    use axum::http::header::{HeaderValue, REFERRER_POLICY, X_CONTENT_TYPE_OPTIONS};
    use axum::http::HeaderName;

    let headers = response.headers_mut();
    headers.insert(X_CONTENT_TYPE_OPTIONS, HeaderValue::from_static("nosniff"));
    headers.insert(
        REFERRER_POLICY,
        HeaderValue::from_static("strict-origin-when-cross-origin"),
    );
    headers.insert(
        HeaderName::from_static(CONTENT_SECURITY_POLICY_HEADER),
        content_security_policy.clone(),
    );
    headers.insert(
        HeaderName::from_static(X_FRAME_OPTIONS_HEADER),
        HeaderValue::from_static("DENY"),
    );

    Ok(())
}

/// The policy is strict because the site genuinely needs nothing: no third-party
/// scripts, no fonts, no analytics, no embeds.
///
/// The hydration script is inline, so in release it is allowed by the hash of
/// its exact contents rather than by `unsafe-inline`. That hash depends on the
/// asset filenames, which carry content hashes, so it changes with every deploy
/// and is computed here from the same inputs that build the script.
#[cfg(feature = "ssr")]
fn content_security_policy(
    options: &leptos::prelude::LeptosOptions,
) -> worker::Result<axum::http::header::HeaderValue> {
    let script_sources = if cfg!(debug_assertions) {
        "'self' 'unsafe-inline' 'wasm-unsafe-eval'".to_string()
    } else {
        let hash = hydration_script_hash(options);
        format!("'self' 'sha256-{hash}' 'wasm-unsafe-eval'")
    };
    let value = format!(
        "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; \
         form-action 'none'; img-src 'self' data:; connect-src 'self'; \
         style-src 'self'; script-src {script_sources};"
    );
    axum::http::header::HeaderValue::from_str(&value)
        .map_err(|error| worker::Error::RustError(error.to_string()))
}

#[cfg(feature = "ssr")]
fn hydration_script_hash(options: &leptos::prelude::LeptosOptions) -> String {
    use base64::Engine;
    use sha2::{Digest, Sha256};

    let digest = Sha256::digest(app::hydration_script(options).as_bytes());
    base64::engine::general_purpose::STANDARD.encode(digest)
}

#[cfg(feature = "hydrate")]
#[wasm_bindgen::prelude::wasm_bindgen]
pub fn hydrate() {
    console_error_panic_hook::set_once();
    leptos::mount::hydrate_body(app::App);
}
