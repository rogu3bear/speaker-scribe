import type { TranscribeOptions } from "./types";

export const DEFAULT_TRANSCRIBE_OPTIONS = {
  // Unchanged deliberately: switching the default would silently change the
  // quality of your next transcript. Turbo is the better pick for most
  // interviews — the dropdown now shows why, so it stays your call.
  model: "large-v3",
  diarize: true,
  min_speakers: undefined,
  max_speakers: undefined,
  language: "",
} satisfies TranscribeOptions;

/**
 * Whisper sizes offered in the UI, fastest first.
 *
 * `size` is the one-off download, cached after the first run. `speed` is
 * transcription throughput measured on this machine against real recordings,
 * as a multiple of realtime — diarization adds a roughly fixed amount on top.
 */
export const MODEL_OPTIONS = [
  {
    value: "tiny",
    label: "Tiny",
    size: "~75 MB",
    speed: "fastest",
    hint: "Roughest accuracy. Good for checking that a file processes at all.",
  },
  {
    value: "base",
    label: "Base",
    size: "~145 MB",
    speed: "very fast",
    hint: "Still misses names and technical terms. Fine for a rough gist.",
  },
  {
    value: "small",
    label: "Small",
    size: "~480 MB",
    speed: "~60x realtime",
    hint: "Usable for clear speech. Struggles with crosstalk and accents.",
  },
  {
    value: "medium",
    label: "Medium",
    size: "~1.5 GB",
    speed: "fast",
    hint: "Close to large on clean audio, at half the download.",
  },
  {
    value: "large-v3-turbo",
    label: "Large v3 Turbo",
    size: "~1.6 GB",
    speed: "~4x faster than large-v3",
    hint: "Near-large accuracy for far less time. The best default for interviews.",
  },
  {
    value: "large-v3",
    label: "Large v3",
    size: "~3 GB",
    speed: "~30x realtime",
    hint: "Most accurate on accents, names and crosstalk. Slowest and largest.",
  },
] as const;

export function modelOption(value: string) {
  return MODEL_OPTIONS.find((option) => option.value === value);
}
