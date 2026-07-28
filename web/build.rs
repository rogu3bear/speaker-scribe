//! Renders the legal documents to HTML at build time.
//!
//! The site and the app show the same terms and privacy text, and in a monorepo
//! that can be literally the same file rather than a copy somebody remembers to
//! update. `docs/legal/*.md` is what the desktop app ships inside its bundle and
//! what GitHub renders; this compiles it into the site.
//!
//! Rendering here rather than at request time keeps a markdown parser out of the
//! wasm bundle, and the documents cannot change between deploys anyway.

use std::env;
use std::fs;
use std::path::Path;

const DOCUMENTS: [&str; 2] = ["terms", "privacy"];

fn main() {
    let out_dir = env::var("OUT_DIR").expect("OUT_DIR is set by cargo");
    // ../docs/legal relative to this crate, i.e. the repository's own copy.
    let source_dir = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("the crate has a parent directory")
        .join("docs/legal");

    for name in DOCUMENTS {
        let source = source_dir.join(format!("{name}.md"));
        // Rebuild when the document changes, not only when the Rust changes.
        println!("cargo:rerun-if-changed={}", source.display());

        let markdown = fs::read_to_string(&source).unwrap_or_else(|error| {
            panic!(
                "could not read {}: {error}. The site renders the same legal text the app ships; \
                 if that file has moved, this path has to move with it.",
                source.display()
            )
        });

        // The first heading is the document title, which the page renders itself
        // as a real <h1>. Leaving it in would show it twice.
        let body: String = markdown
            .lines()
            .skip_while(|line| !line.starts_with("# "))
            .skip(1)
            .collect::<Vec<_>>()
            .join("\n");

        let parser = pulldown_cmark::Parser::new_ext(&body, pulldown_cmark::Options::empty());
        let mut html = String::new();
        pulldown_cmark::html::push_html(&mut html, parser);

        fs::write(Path::new(&out_dir).join(format!("{name}.html")), html)
            .unwrap_or_else(|error| panic!("could not write {name}.html: {error}"));
    }
}
