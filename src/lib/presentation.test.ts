import { describe, expect, it } from "vitest";
import type { ModelInfo, TranscriptSegment } from "../types";
import type { Job } from "../types";
import {
  groupSegmentsBySpeaker,
  jobTitle,
  jobsInCollection,
  preferredModel,
  turnText,
} from "./presentation";

function job(id: string, fields: Partial<Job> = {}): Job {
  return {
    id,
    original_name: `${id}.m4a`,
    filename: `${id}-audio.m4a`,
    created_at: "2026-07-01T00:00:00Z",
    status: "completed",
    progress: 1,
    stage: "Transcript complete",
    model: "large-v3",
    diarize: true,
    speakers: [],
    segments: [],
    ...fields,
  };
}

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

describe("jobsInCollection", () => {
  const jobs = [
    job("a", { collection: "inbox" }),
    job("b", { collection: "saved" }),
    job("c", { collection: "archived" }),
    job("d"),
  ];

  it("filters to one collection", () => {
    expect(jobsInCollection(jobs, "saved").map((item) => item.id)).toEqual(["b"]);
    expect(jobsInCollection(jobs, "archived").map((item) => item.id)).toEqual(["c"]);
  });

  it("treats a job with no collection as inbox", () => {
    expect(jobsInCollection(jobs, "inbox").map((item) => item.id)).toEqual(["a", "d"]);
  });

  it("never loses a job between collections", () => {
    const filed = (["inbox", "saved", "archived"] as const).flatMap((key) =>
      jobsInCollection(jobs, key),
    );

    expect(filed).toHaveLength(jobs.length);
  });
});

describe("jobTitle", () => {
  it("prefers a chosen title", () => {
    expect(jobTitle(job("a", { title: "Donella interview" }))).toBe("Donella interview");
  });

  it("falls back to the file name when the title is missing or blank", () => {
    expect(jobTitle(job("a"))).toBe("a.m4a");
    expect(jobTitle(job("a", { title: "   " }))).toBe("a.m4a");
    expect(jobTitle(job("a", { title: null }))).toBe("a.m4a");
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

describe("preferredModel", () => {
  function model(value: string, state: ModelInfo["state"]): ModelInfo {
    return {
      value,
      repo: `mlx-community/whisper-${value}`,
      label: value,
      hint: "",
      speed: "",
      download_mb: 100,
      state,
      size_on_disk: state === "available" ? 100 : 0,
    };
  }

  // The catalog arrives worst-first, so "best available" is the last one.
  it("picks the most accurate model already on disk", () => {
    const catalog = [
      model("tiny", "available"),
      model("small", "available"),
      model("large-v3", "missing"),
    ];

    expect(preferredModel(catalog)).toBe("small");
  });

  it("ignores models that are only part-way through downloading", () => {
    const catalog = [model("small", "available"), model("large-v3", "downloading")];

    expect(preferredModel(catalog)).toBe("small");
  });

  it("ignores a model that failed to download", () => {
    const catalog = [model("small", "available"), model("large-v3", "error")];

    expect(preferredModel(catalog)).toBe("small");
  });

  it("has no answer when nothing is downloaded yet", () => {
    expect(preferredModel([model("tiny", "missing")])).toBeUndefined();
  });

  it("has no answer before the catalog has loaded", () => {
    expect(preferredModel([])).toBeUndefined();
  });
});
