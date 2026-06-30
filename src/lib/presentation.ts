import type { Job, JobStatus } from "../types";

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

export function speakerCountLabel(count: number): string {
  return `${count} ${count === 1 ? "speaker" : "speakers"}`;
}
