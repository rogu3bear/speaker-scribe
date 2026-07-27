import type { Health, Job, SpeakerRenameRequest, TranscribeOptions } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // Keep the HTTP status when the server returned a non-JSON error.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export async function fetchHealth(): Promise<Health> {
  const response = await fetch(`${API_BASE}/api/health`);
  return parseJson<Health>(response);
}

export async function fetchJobs(): Promise<Job[]> {
  const response = await fetch(`${API_BASE}/api/jobs`);
  return parseJson<Job[]>(response);
}

export async function fetchJob(id: string): Promise<Job> {
  const response = await fetch(`${API_BASE}/api/jobs/${id}`);
  return parseJson<Job>(response);
}

export async function uploadAudio(file: File, options: TranscribeOptions): Promise<Job> {
  const form = new FormData();
  form.append("file", file);
  form.append("model", options.model);
  form.append("diarize", String(options.diarize));

  if (options.min_speakers !== undefined) {
    form.append("min_speakers", String(options.min_speakers));
  }
  if (options.max_speakers !== undefined) {
    form.append("max_speakers", String(options.max_speakers));
  }
  if (options.language) {
    form.append("language", options.language);
  }

  const response = await fetch(`${API_BASE}/api/jobs`, {
    method: "POST",
    body: form,
  });
  return parseJson<Job>(response);
}

export async function renameSpeakers(
  id: string,
  body: SpeakerRenameRequest,
): Promise<Job> {
  const response = await fetch(`${API_BASE}/api/jobs/${id}/speakers`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseJson<Job>(response);
}

export function exportUrl(id: string, format: "txt" | "srt" | "json"): string {
  return `${API_BASE}/api/jobs/${id}/export?format=${format}`;
}
