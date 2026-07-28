import { describe, expect, it } from "vitest";
import type { Job, TranscriptSegment } from "../types";
import { voiceMetrics } from "./metrics";

function segment(
  id: string,
  speaker: string,
  start: number,
  end: number,
  text: string,
  clean_text?: string,
): TranscriptSegment {
  return { id, speaker, start, end, text, clean_text };
}

function job(segments: TranscriptSegment[]): Job {
  return {
    id: "job-1",
    original_name: "talk.m4a",
    filename: "job-1-talk.m4a",
    created_at: "2026-07-01T00:00:00Z",
    status: "completed",
    progress: 1,
    stage: "Transcript complete",
    model: "large-v3",
    diarize: true,
    speakers: [],
    segments,
  };
}

// A -> B -> A -> B, sixty seconds of talk split 40/20.
const CONVERSATION = job([
  segment("1", "A", 0, 20, "one two three four", "one two three four"),
  segment("2", "B", 20, 30, "um five six", "five six"),
  segment("3", "A", 30, 50, "seven eight nine ten?", "seven eight nine ten?"),
  segment("4", "B", 50, 60, "eleven twelve", "eleven twelve"),
]);

describe("voiceMetrics", () => {
  const metrics = voiceMetrics(CONVERSATION);
  const a = metrics.get("A")!;
  const b = metrics.get("B")!;

  it("reports one entry per voice heard", () => {
    expect([...metrics.keys()].sort()).toEqual(["A", "B"]);
  });

  it("totals speaking time and its share of the conversation", () => {
    expect(a.seconds).toBe(40);
    expect(b.seconds).toBe(20);
    expect(a.shareOfTalk).toBeCloseTo(2 / 3);
    expect(b.shareOfTalk).toBeCloseTo(1 / 3);
  });

  it("counts words and derives a speaking pace", () => {
    expect(a.words).toBe(8);
    expect(a.wordsPerMinute).toBeCloseTo(12);
  });

  it("counts turns rather than segments", () => {
    expect(a.turns).toBe(2);
    expect(a.averageTurnSeconds).toBe(20);
    expect(a.averageTurnWords).toBe(4);
  });

  it("counts questions", () => {
    expect(a.questions).toBe(1);
    expect(b.questions).toBe(0);
  });

  it("counts words that cleanup removed as filler", () => {
    // B speaks 5 words across both turns; cleanup drops one "um".
    expect(b.words).toBe(5);
    expect(b.fillerWords).toBe(1);
    expect(b.fillerRate).toBeCloseTo(1 / 5);
    expect(a.fillerWords).toBe(0);
  });

  it("reports when a voice was first and last heard", () => {
    expect(a.firstHeardAt).toBe(0);
    expect(a.lastHeardAt).toBe(50);
    expect(b.firstHeardAt).toBe(20);
  });

  it("identifies who a voice most often answers", () => {
    expect(b.respondsTo).toEqual({ speaker: "A", count: 2 });
    expect(a.respondsTo).toEqual({ speaker: "B", count: 1 });
  });

  it("identifies who most often answers a voice", () => {
    expect(a.answeredBy).toEqual({ speaker: "B", count: 2 });
  });

  it("leaves relations empty for a monologue", () => {
    const solo = voiceMetrics(job([segment("1", "A", 0, 10, "just me")])).get("A")!;

    expect(solo.respondsTo).toBeNull();
    expect(solo.answeredBy).toBeNull();
    expect(solo.shareOfTalk).toBe(1);
  });

  it("handles an empty transcript without dividing by zero", () => {
    const empty = voiceMetrics(job([]));

    expect(empty.size).toBe(0);
  });

  it("does not blow up on a zero-length segment", () => {
    const instant = voiceMetrics(job([segment("1", "A", 5, 5, "hi")])).get("A")!;

    expect(instant.seconds).toBe(0);
    expect(instant.wordsPerMinute).toBe(0);
    expect(instant.shareOfTalk).toBe(0);
  });

  it("counts a wholly-filler segment as all filler", () => {
    // clean_text "" means cleanup removed every word. Treating that as falsy and
    // falling back to verbatim scored the most filler-dense segment as clean.
    const hesitant = voiceMetrics(
      job([
        segment("1", "A", 0, 4, "real words here", "real words here"),
        segment("2", "A", 4, 6, "um uh hmm", ""),
      ]),
    ).get("A")!;

    expect(hesitant.words).toBe(6);
    expect(hesitant.fillerWords).toBe(3);
  });

  it("falls back to verbatim when a transcript predates cleanup", () => {
    const legacy = voiceMetrics(job([segment("1", "A", 0, 10, "um so it goes")])).get("A")!;

    expect(legacy.words).toBe(4);
    expect(legacy.fillerWords).toBe(0);
  });
});
