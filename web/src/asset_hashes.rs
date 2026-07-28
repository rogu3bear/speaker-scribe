//! Content hashes for the built assets, injected at compile time.
//!
//! `scripts/hash-assets.mjs` renames the built JS, wasm and CSS to include a
//! hash of their contents and exports these variables; the build then compiles
//! with them set. Empty means an unhashed development build, where the plain
//! filenames are correct.

pub const JS_HASH: &str = match option_env!("LEPTOS_EDGE_JS_HASH") {
    Some(hash) => hash,
    None => "",
};

pub const WASM_HASH: &str = match option_env!("LEPTOS_EDGE_WASM_HASH") {
    Some(hash) => hash,
    None => "",
};

pub const CSS_HASH: &str = match option_env!("LEPTOS_EDGE_CSS_HASH") {
    Some(hash) => hash,
    None => "",
};
