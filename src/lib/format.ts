export function formatClock(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return "00:00";
  }

  const total = Math.floor(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${secs
      .toString()
      .padStart(2, "0")}`;
  }

  return `${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

export function formatDuration(seconds?: number | null): string {
  if (seconds === undefined || seconds === null) {
    return "duration pending";
  }
  return formatClock(seconds);
}

export function progressLabel(progress: number): string {
  const bounded = Math.max(0, Math.min(1, progress));
  return `${Math.round(bounded * 100)}%`;
}
