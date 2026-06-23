import type { Job } from "./types";

export const demoJob: Job = {
  id: "demo",
  original_name: "founder-interview-demo.wav",
  filename: "founder-interview-demo.wav",
  created_at: new Date().toISOString(),
  status: "completed",
  progress: 1,
  stage: "Demo transcript loaded",
  model: "large-v3",
  diarize: true,
  language: "en",
  duration: 312,
  audio_url: null,
  speakers: [
    { id: "SPEAKER_00", name: "Interviewer", color: "#0f766e", seconds: 162 },
    { id: "SPEAKER_01", name: "Guest", color: "#b45309", seconds: 139 },
  ],
  segments: [
    {
      id: "seg-1",
      start: 0.3,
      end: 7.8,
      speaker: "SPEAKER_00",
      text: "Thanks for joining. I want to start with the workflow you use to review long recordings.",
    },
    {
      id: "seg-2",
      start: 8.1,
      end: 19.4,
      speaker: "SPEAKER_01",
      text: "The first pass is usually just getting an accurate transcript with speaker turns, then I rename the speakers before exporting.",
    },
    {
      id: "seg-3",
      start: 20.2,
      end: 34.9,
      speaker: "SPEAKER_00",
      text: "So the main value is local transcription, reliable timestamps, and a clean way to correct speaker names before sharing.",
    },
    {
      id: "seg-4",
      start: 35.6,
      end: 49.5,
      speaker: "SPEAKER_01",
      text: "Exactly. The names are never magic; the system detects speaker identities and lets me label them once.",
    },
  ],
};
