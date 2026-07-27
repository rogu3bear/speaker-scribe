import type { Job, TranscriptSegment } from "../types";
import { groupSegmentsBySpeaker } from "./presentation";

export type VoiceMetrics = {
  speaker: string;
  seconds: number;
  shareOfTalk: number;
  words: number;
  wordsPerMinute: number;
  turns: number;
  averageTurnSeconds: number;
  averageTurnWords: number;
  longestTurnSeconds: number;
  questions: number;
  /** Words cleanup removed: fillers, stutters, repeats. A hesitancy signal. */
  fillerWords: number;
  fillerRate: number;
  firstHeardAt: number | null;
  lastHeardAt: number | null;
  /** Whose turn this voice most often follows — who they answer. */
  respondsTo: { speaker: string; count: number } | null;
  /** Who most often takes the floor after this voice. */
  answeredBy: { speaker: string; count: number } | null;
};

function countWords(text: string): number {
  const trimmed = text.trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

function segmentWords(segment: TranscriptSegment): number {
  return countWords(segment.text);
}

function topEntry(counts: Map<string, number>): { speaker: string; count: number } | null {
  let best: { speaker: string; count: number } | null = null;
  // Ties break on the speaker label so the panel does not flicker between equals.
  for (const speaker of [...counts.keys()].sort()) {
    const count = counts.get(speaker) ?? 0;
    if (!best || count > best.count) {
      best = { speaker, count };
    }
  }
  return best;
}

/**
 * Per-voice statistics for one conversation.
 *
 * Derived from segments rather than stored, so it stays correct when speakers
 * are renamed or the cleanup rules change.
 */
export function voiceMetrics(job: Job): Map<string, VoiceMetrics> {
  const turns = groupSegmentsBySpeaker(job.segments);
  const totalTalk = job.segments.reduce(
    (sum, segment) => sum + Math.max(0, segment.end - segment.start),
    0,
  );

  const respondsTo = new Map<string, Map<string, number>>();
  const answeredBy = new Map<string, Map<string, number>>();
  turns.forEach((turn, index) => {
    const previous = turns[index - 1];
    if (!previous) {
      return;
    }
    const answering = respondsTo.get(turn.speaker) ?? new Map<string, number>();
    answering.set(previous.speaker, (answering.get(previous.speaker) ?? 0) + 1);
    respondsTo.set(turn.speaker, answering);

    const answered = answeredBy.get(previous.speaker) ?? new Map<string, number>();
    answered.set(turn.speaker, (answered.get(turn.speaker) ?? 0) + 1);
    answeredBy.set(previous.speaker, answered);
  });

  const metrics = new Map<string, VoiceMetrics>();

  for (const speaker of new Set(job.segments.map((segment) => segment.speaker))) {
    const mine = job.segments.filter((segment) => segment.speaker === speaker);
    const myTurns = turns.filter((turn) => turn.speaker === speaker);

    const seconds = mine.reduce(
      (sum, segment) => sum + Math.max(0, segment.end - segment.start),
      0,
    );
    const words = mine.reduce((sum, segment) => sum + segmentWords(segment), 0);
    // Nullish, not falsy: an empty clean_text means cleanup removed every word,
    // which is the most filler-dense segment there is. Falling back to verbatim
    // there would score it as containing no filler at all.
    const cleanWords = mine.reduce(
      (sum, segment) => sum + countWords(segment.clean_text ?? segment.text),
      0,
    );
    const turnSeconds = myTurns.map((turn) => Math.max(0, turn.end - turn.start));

    metrics.set(speaker, {
      speaker,
      seconds,
      shareOfTalk: totalTalk > 0 ? seconds / totalTalk : 0,
      words,
      wordsPerMinute: seconds > 0 ? (words / seconds) * 60 : 0,
      turns: myTurns.length,
      averageTurnSeconds: myTurns.length ? seconds / myTurns.length : 0,
      averageTurnWords: myTurns.length ? words / myTurns.length : 0,
      longestTurnSeconds: turnSeconds.length ? Math.max(...turnSeconds) : 0,
      questions: mine.filter((segment) => segment.text.trim().endsWith("?")).length,
      fillerWords: Math.max(0, words - cleanWords),
      fillerRate: words > 0 ? Math.max(0, words - cleanWords) / words : 0,
      firstHeardAt: mine.length ? Math.min(...mine.map((segment) => segment.start)) : null,
      lastHeardAt: mine.length ? Math.max(...mine.map((segment) => segment.end)) : null,
      respondsTo: topEntry(respondsTo.get(speaker) ?? new Map()),
      answeredBy: topEntry(answeredBy.get(speaker) ?? new Map()),
    });
  }

  return metrics;
}
