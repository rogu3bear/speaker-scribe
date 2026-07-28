/**
 * A markdown reader for the two legal documents the app ships.
 *
 * Deliberately not a markdown implementation. It handles the constructs those
 * files actually use — headings, paragraphs, bulleted lists, fenced code, and
 * inline code and bold — and treats everything else as text. Pulling in a full
 * parser to render two documents that live in this repository, and whose syntax
 * is therefore known, would be a dependency and a sanitisation problem in
 * exchange for features nothing uses.
 *
 * If a document starts using something this does not understand, the failure is
 * that the markup shows up literally, which is visible and harmless.
 */

export type Inline = { text: string; code?: boolean; strong?: boolean };

export type Block =
  | { kind: "heading"; level: number; spans: Inline[] }
  | { kind: "paragraph"; spans: Inline[] }
  | { kind: "list"; items: Inline[][] }
  | { kind: "code"; text: string };

const INLINE_PATTERN = /(`[^`]+`|\*\*[^*]+\*\*)/g;

/** Split one line into plain, code and bold runs. */
export function parseInline(source: string): Inline[] {
  const spans: Inline[] = [];
  let index = 0;

  for (const match of source.matchAll(INLINE_PATTERN)) {
    const start = match.index ?? 0;
    if (start > index) {
      spans.push({ text: source.slice(index, start) });
    }
    const token = match[0];
    if (token.startsWith("`")) {
      spans.push({ text: token.slice(1, -1), code: true });
    } else {
      spans.push({ text: token.slice(2, -2), strong: true });
    }
    index = start + token.length;
  }

  if (index < source.length) {
    spans.push({ text: source.slice(index) });
  }
  return spans.filter((span) => span.text !== "");
}

export function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = [];
  const lines = source.split("\n");
  let paragraph: string[] = [];
  let items: string[] = [];

  function flushParagraph() {
    if (paragraph.length > 0) {
      // Joined with a space: markdown treats a single newline as a soft wrap,
      // and these files are hard-wrapped at 80 columns.
      blocks.push({ kind: "paragraph", spans: parseInline(paragraph.join(" ")) });
      paragraph = [];
    }
  }

  function flushList() {
    if (items.length > 0) {
      blocks.push({ kind: "list", items: items.map(parseInline) });
      items = [];
    }
  }

  function flush() {
    flushParagraph();
    flushList();
  }

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];

    if (line.startsWith("```")) {
      flush();
      const body: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith("```")) {
        body.push(lines[index]);
        index += 1;
      }
      blocks.push({ kind: "code", text: body.join("\n") });
      continue;
    }

    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      flush();
      blocks.push({
        kind: "heading",
        level: heading[1].length,
        spans: parseInline(heading[2]),
      });
      continue;
    }

    const item = /^[-*]\s+(.*)$/.exec(line);
    if (item) {
      flushParagraph();
      items.push(item[1]);
      continue;
    }

    if (line.trim() === "") {
      flush();
      continue;
    }

    // A continuation line inside a list item belongs to that item, not to a new
    // paragraph. These documents wrap long bullets across several lines.
    if (items.length > 0 && line.startsWith("  ")) {
      items[items.length - 1] += ` ${line.trim()}`;
      continue;
    }

    flushList();
    paragraph.push(line);
  }

  flush();
  return blocks;
}
