import type { TranscribeOptions } from "./types";

export const DEFAULT_TRANSCRIBE_OPTIONS = {
  model: "large-v3",
  diarize: true,
  min_speakers: undefined,
  max_speakers: undefined,
  language: "",
} satisfies TranscribeOptions;

export const MODEL_OPTIONS = [
  { label: "large-v3", value: "large-v3" },
  { label: "large-v3-turbo", value: "large-v3-turbo" },
  { label: "mlx-community/whisper-large-v3-turbo", value: "mlx-community/whisper-large-v3-turbo" },
  { label: "mlx-community/whisper-small-mlx", value: "mlx-community/whisper-small-mlx" },
] as const;
