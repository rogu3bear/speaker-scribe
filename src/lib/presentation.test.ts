import { describe, expect, it } from "vitest";
import type { TranscriptSegment } from "../types";
import { groupSegmentsBySpeaker, turnText } from "./presentation";

function segment(
  id: string,
  speaker: string,
  start: number,
  end: number,
  text = "line",
  clean_text?: string,
): TranscriptSegment {
  return { id, speaker, start, end, text, clean_text };
}

describe("groupSegmentsBySpeaker", () => {
  it("pools a run of segments from one speaker into a single turn", () => {
    const turns = groupSegmentsBySpeaker([
      segment("a", "SPEAKER_00", 0, 2, "one"),
      segment("b", "SPEAKER_00", 2, 4, "two"),
      segment("c", "SPEAKER_00", 4, 6, "three"),
    ]);

    expect(turns).toHaveLength(1);
    expect(turns[0].segments.map((item) => item.text)).toEqual(["one", "two", "three"]);
    expect(turns[0].start).toBe(0);
    expect(turns[0].end).toBe(6);
  });

  it("starts a new turn when the speaker changes", () => {
    const turns = groupSegmentsBySpeaker([
      segment("a", "SPEAKER_00", 0, 2),
      segment("b", "SPEAKER_01", 2, 4),
      segment("c", "SPEAKER_00", 4, 6),
    ]);

    expect(turns.map((turn) => turn.speaker)).toEqual([
      "SPEAKER_00",
      "SPEAKER_01",
      "SPEAKER_00",
    ]);
    expect(turns.every((turn) => turn.segments.length === 1)).toBe(true);
  });

  it("spans a turn from its first segment start to its last segment end", () => {
    const turns = groupSegmentsBySpeaker([
      segment("a", "SPEAKER_00", 1.5, 3.25),
      segment("b", "SPEAKER_00", 3.4, 9.75),
    ]);

    expect(turns[0].start).toBe(1.5);
    expect(turns[0].end).toBe(9.75);
  });

  it("does not let an out-of-order segment shrink a turn", () => {
    const turns = groupSegmentsBySpeaker([
      segment("a", "SPEAKER_00", 0, 10),
      segment("b", "SPEAKER_00", 2, 4),
    ]);

    expect(turns[0].end).toBe(10);
  });

  it("keeps every segment, so nothing is dropped from the transcript", () => {
    const segments = [
      segment("a", "SPEAKER_00", 0, 1),
      segment("b", "SPEAKER_01", 1, 2),
      segment("c", "SPEAKER_01", 2, 3),
      segment("d", "SPEAKER_00", 3, 4),
    ];

    const pooled = groupSegmentsBySpeaker(segments).flatMap((turn) => turn.segments);

    expect(pooled).toEqual(segments);
  });

  it("takes its key from the first segment of the turn", () => {
    const turns = groupSegmentsBySpeaker([
      segment("first", "SPEAKER_00", 0, 1),
      segment("second", "SPEAKER_00", 1, 2),
    ]);

    expect(turns[0].id).toBe("first");
  });

  it("returns nothing for an empty transcript", () => {
    expect(groupSegmentsBySpeaker([])).toEqual([]);
  });
});

describe("turnText", () => {
  const turn = groupSegmentsBySpeaker([
    segment("a", "SPEAKER_00", 0, 2, "um so I was thinking", "So I was thinking"),
    segment("b", "SPEAKER_00", 2, 4, "that the the plan works", "that the plan works"),
  ])[0];

  it("joins a turn into one flowing paragraph", () => {
    expect(turnText(turn, false)).toBe("um so I was thinking that the the plan works");
  });

  it("prefers the tidied text when asked", () => {
    expect(turnText(turn, true)).toBe("So I was thinking that the plan works");
  });

  it("falls back to verbatim for transcripts made before cleanup existed", () => {
    const legacy = groupSegmentsBySpeaker([
      segment("a", "SPEAKER_00", 0, 2, "spoken words", ""),
      segment("b", "SPEAKER_00", 2, 4, "and more", undefined),
    ])[0];

    expect(turnText(legacy, true)).toBe("spoken words and more");
  });

  it("drops segments that cleanup emptied out", () => {
    const withFiller = groupSegmentsBySpeaker([
      segment("a", "SPEAKER_00", 0, 1, "real content", "real content"),
      segment("b", "SPEAKER_00", 1, 2, "um", " "),
      segment("c", "SPEAKER_00", 2, 3, "more content", "more content"),
    ])[0];

    expect(turnText(withFiller, true)).toBe("real content more content");
  });
});
