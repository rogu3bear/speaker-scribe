import type { TranscribeOptions } from "./types";

export const DEFAULT_TRANSCRIBE_OPTIONS = {
  // Unchanged deliberately: switching the default would silently change the
  // quality of your next transcript. Turbo is the better pick for most
  // interviews — the picker now shows why, so it stays your call.
  model: "large-v3",
  diarize: true,
  min_speakers: undefined,
  max_speakers: undefined,
  language: "",
} satisfies TranscribeOptions;

// Model metadata lives in the backend catalog (GET /api/models), which is the
// only place that knows what is actually on disk. Keeping a second copy here
// would guarantee the two drift.
