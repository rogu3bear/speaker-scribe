export type JobStatus = "queued" | "running" | "completed" | "failed";

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
  text: string;
  speaker: string;
};

export type Speaker = {
  id: string;
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

export type Health = {
  ok: boolean;
  engine: string;
  ml_ready: boolean;
  detail?: string | null;
};
