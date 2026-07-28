import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchLegal } from "../api";
import type { Block, Inline } from "../lib/markdown";
import { parseMarkdown } from "../lib/markdown";

export type LegalDocument = "terms" | "privacy";

const TITLES: Record<LegalDocument, string> = {
  terms: "Terms",
  privacy: "Privacy",
};

function Spans({ spans }: { spans: Inline[] }) {
  return (
    <>
      {spans.map((span, index) => {
        const key = `${index}-${span.text}`;
        if (span.code) {
          return <code key={key}>{span.text}</code>;
        }
        if (span.strong) {
          return <strong key={key}>{span.text}</strong>;
        }
        return <span key={key}>{span.text}</span>;
      })}
    </>
  );
}

function Rendered({ blocks }: { blocks: Block[] }) {
  return (
    <>
      {blocks.map((block, index) => {
        const key = `${block.kind}-${index}`;
        switch (block.kind) {
          case "heading": {
            // The document's own h1 is the panel title, so its headings start a
            // level down and never compete with the app's own heading order.
            const Tag = (block.level === 1 ? "h3" : "h4") as "h3" | "h4";
            return (
              <Tag key={key}>
                <Spans spans={block.spans} />
              </Tag>
            );
          }
          case "list":
            return (
              <ul key={key}>
                {block.items.map((item, itemIndex) => (
                  <li key={`${key}-${itemIndex}`}>
                    <Spans spans={item} />
                  </li>
                ))}
              </ul>
            );
          case "code":
            return <pre key={key}>{block.text}</pre>;
          default:
            return (
              <p key={key}>
                <Spans spans={block.spans} />
              </p>
            );
        }
      })}
    </>
  );
}

/**
 * Shows the terms and privacy documents the app ships with.
 *
 * Read from the backend rather than compiled into the bundle so that what the
 * app displays is the same file the repository publishes. Both are fetched from
 * disk inside the app, so this works with no network.
 */
export function LegalPanel({
  document: name,
  onClose,
}: {
  document: LegalDocument;
  onClose: () => void;
}) {
  const [blocks, setBlocks] = useState<Block[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setBlocks(null);
    setError(null);
    fetchLegal(name)
      .then((text) => {
        if (live) {
          // The leading h1 duplicates the panel title.
          setBlocks(parseMarkdown(text).slice(1));
        }
      })
      .catch((cause: unknown) => {
        if (live) {
          setError(cause instanceof Error ? cause.message : "Could not load that document");
        }
      });
    return () => {
      live = false;
    };
  }, [name]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="legal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="legal-panel"
        role="dialog"
        aria-modal="true"
        aria-label={TITLES[name]}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="legal-head">
          <h2>{TITLES[name]}</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </header>
        <div className="legal-body">
          {error ? <p className="legal-error">{error}</p> : null}
          {blocks ? <Rendered blocks={blocks} /> : error ? null : <p>Loading…</p>}
        </div>
      </div>
    </div>
  );
}
