export type JobStatus = "queued" | "running" | "completed" | "failed";

/** Where a job is filed. Filing moves it, so a transcript has one home. */
export type JobCollection = "inbox" | "saved" | "archived";

export type TranscribeOptions = {
  model: string;
  diarize: boolean;
  min_speakers?: number;
  max_speakers?: number;
  language?: string;
};

export type TranscriptSegment = {
  id: string;
  start: number;
  end: number;
  /** Verbatim: what was actually said. */
  text: string;
  /** Tidied for reading. Empty on transcripts made before cleanup existed. */
  clean_text?: string;
  speaker: string;
};

export type Speaker = {
  id: string;
  /** Durable, globally unique handle for this voice. Derived server-side. */
  voice_id?: string;
  name: string;
  color: string;
  seconds: number;
};

export type Job = {
  id: string;
  original_name: string;
  filename: string;
  created_at: string;
  status: JobStatus;
  collection?: JobCollection;
  title?: string | null;
  progress: number;
  stage: string;
  error?: string | null;
  model: string;
  diarize: boolean;
  language?: string | null;
  duration?: number | null;
  audio_url?: string | null;
  speakers: Speaker[];
  segments: TranscriptSegment[];
};

export type SpeakerRenameRequest = {
  speakers: Record<string, string>;
};

export type ModelState = "available" | "missing" | "downloading" | "error";

export type ModelInfo = {
  value: string;
  repo: string;
  label: string;
  hint: string;
  speed: string;
  download_mb: number;
  state: ModelState;
  size_on_disk: number;
  detail?: string | null;
};

export type Health = {
  ok: boolean;
  engine: string;
  ml_ready: boolean;
  detail?: string | null;
};
