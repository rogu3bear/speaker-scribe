fn main() {
    // The window loads the local server, which needs the checkout it was built
    // from. scripts/build-app.sh sets this; a bare `cargo build` falls back to
    // the repository containing this file.
    let root = std::env::var("SPEAKER_SCRIBE_ROOT").unwrap_or_else(|_| {
        std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("src-tauri has a parent")
            .to_string_lossy()
            .into_owned()
    });
    println!("cargo:rustc-env=SPEAKER_SCRIBE_ROOT={root}");
    println!("cargo:rerun-if-env-changed=SPEAKER_SCRIBE_ROOT");

    tauri_build::build()
}
