import { describe, expect, it } from "vitest";
import { parseInline, parseMarkdown } from "./markdown";

describe("parseInline", () => {
  it("keeps plain text as one span", () => {
    expect(parseInline("no markup here")).toEqual([{ text: "no markup here" }]);
  });

  it("marks backticked runs as code", () => {
    expect(parseInline("stored in `data/` locally")).toEqual([
      { text: "stored in " },
      { text: "data/", code: true },
      { text: " locally" },
    ]);
  });

  it("marks doubled asterisks as strong", () => {
    expect(parseInline("**macOS checks** the app")).toEqual([
      { text: "macOS checks", strong: true },
      { text: " the app" },
    ]);
  });

  it("drops the empty run between adjacent tokens", () => {
    expect(parseInline("`a``b`")).toEqual([
      { text: "a", code: true },
      { text: "b", code: true },
    ]);
  });
});

describe("parseMarkdown", () => {
  it("reads headings at their level", () => {
    expect(parseMarkdown("# Terms\n\n## Your recordings")).toEqual([
      { kind: "heading", level: 1, spans: [{ text: "Terms" }] },
      { kind: "heading", level: 2, spans: [{ text: "Your recordings" }] },
    ]);
  });

  it("joins hard-wrapped lines into one paragraph", () => {
    // The source files wrap at 80 columns; rendering each line separately would
    // break sentences at arbitrary points.
    const blocks = parseMarkdown("Audio you open stays\non your Mac.");

    expect(blocks).toEqual([
      { kind: "paragraph", spans: [{ text: "Audio you open stays on your Mac." }] },
    ]);
  });

  it("separates paragraphs on a blank line", () => {
    const blocks = parseMarkdown("First one.\n\nSecond one.");

    expect(blocks).toHaveLength(2);
    expect(blocks[0]).toEqual({ kind: "paragraph", spans: [{ text: "First one." }] });
    expect(blocks[1]).toEqual({ kind: "paragraph", spans: [{ text: "Second one." }] });
  });

  it("collects bullets into a single list", () => {
    const blocks = parseMarkdown("- No analytics.\n- No crash reports.");

    expect(blocks).toEqual([
      {
        kind: "list",
        items: [[{ text: "No analytics." }], [{ text: "No crash reports." }]],
      },
    ]);
  });

  it("keeps a wrapped bullet with its own item", () => {
    const blocks = parseMarkdown("- macOS checks the app\n  with Apple.\n- Hugging Face sees it.");

    expect(blocks).toEqual([
      {
        kind: "list",
        items: [
          [{ text: "macOS checks the app with Apple." }],
          [{ text: "Hugging Face sees it." }],
        ],
      },
    ]);
  });

  it("keeps fenced code verbatim, including blank lines", () => {
    const blocks = parseMarkdown("```\nline one\n\nline two\n```");

    expect(blocks).toEqual([{ kind: "code", text: "line one\n\nline two" }]);
  });

  it("does not read markup inside a code fence", () => {
    const blocks = parseMarkdown("```\n# not a heading\n```");

    expect(blocks).toEqual([{ kind: "code", text: "# not a heading" }]);
  });

  it("ends a list when a paragraph follows it", () => {
    const blocks = parseMarkdown("- one\n\nAfter the list.");

    expect(blocks).toHaveLength(2);
    expect(blocks[0].kind).toBe("list");
    expect(blocks[1]).toEqual({ kind: "paragraph", spans: [{ text: "After the list." }] });
  });

  it("reads the real privacy document without leaving markup behind", () => {
    const blocks = parseMarkdown("# Privacy\n\nNo `telemetry` at all.\n\n- Nothing **collected**.");

    expect(blocks).toHaveLength(3);
    const rendered = blocks
      .flatMap((block) =>
        block.kind === "code"
          ? [block.text]
          : block.kind === "list"
            ? block.items.flat().map((span) => span.text)
            : block.spans.map((span) => span.text),
      )
      .join(" ");
    expect(rendered).not.toMatch(/[`#*]/);
  });
});
