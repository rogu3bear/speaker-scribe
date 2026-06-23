import { Braces, Captions, FileText } from "lucide-react";

export const DEFAULT_TRANSCRIBE_OPTIONS = {
  model: "large-v3",
  diarize: true,
  min_speakers: undefined,
  max_speakers: undefined,
  language: "",
};

export const MODEL_OPTIONS = [
  { label: "large-v3", value: "large-v3" },
  { label: "large-v3-turbo", value: "large-v3-turbo" },
  { label: "mlx-community/whisper-large-v3-turbo", value: "mlx-community/whisper-large-v3-turbo" },
  { label: "mlx-community/whisper-small-mlx", value: "mlx-community/whisper-small-mlx" },
];

export const EXPORT_FORMATS = [
  { format: "txt", label: "TXT", icon: FileText },
  { format: "srt", label: "SRT", icon: Captions },
  { format: "json", label: "JSON", icon: Braces },
] as const;
