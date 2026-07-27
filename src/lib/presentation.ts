import type { Job, JobStatus, TranscriptSegment } from "../types";

export type TranscriptTurn = {
  id: string;
  speaker: string;
  start: number;
  end: number;
  segments: TranscriptSegment[];
};

/**
 * Pool consecutive segments from one speaker into a single turn.
 *
 * Whisper emits a segment per sentence, so a speaker holding the floor produces
 * a run of them. Rendering each with its own speaker label reads as staccato and
 * buries who is talking. The underlying segments are left untouched: SRT export
 * needs short cues, and per-sentence times stay available for seeking.
 */
export function groupSegmentsBySpeaker(segments: TranscriptSegment[]): TranscriptTurn[] {
  const turns: TranscriptTurn[] = [];

  for (const segment of segments) {
    const current = turns.at(-1);
    if (current && current.speaker === segment.speaker) {
      current.segments.push(segment);
      current.end = Math.max(current.end, segment.end);
      continue;
    }

    turns.push({
      id: segment.id,
      speaker: segment.speaker,
      start: segment.start,
      end: segment.end,
      segments: [segment],
    });
  }

  return turns;
}

export function statusTone(status: JobStatus): "good" | "bad" | "live" | "idle" {
  switch (status) {
    case "completed":
      return "good";
    case "failed":
      return "bad";
    case "running":
      return "live";
    default:
      return "idle";
  }
}

export function canPollJob(job: Job | null): job is Job {
  return job?.status === "queued" || job?.status === "running";
}

/**
 * Render a turn as one flowing paragraph.
 *
 * Whisper's segments are sentence fragments; shown as separate lines they read
 * as a list rather than as someone talking. Falls back to verbatim per segment,
 * so a transcript made before cleanup existed still reads correctly.
 */
export function turnText(turn: TranscriptTurn, tidy: boolean): string {
  return turn.segments
    .map((segment) => (tidy ? segment.clean_text || segment.text : segment.text).trim())
    .filter(Boolean)
    .join(" ");
}

export function speakerCountLabel(count: number): string {
  return `${count} ${count === 1 ? "speaker" : "speakers"}`;
}
