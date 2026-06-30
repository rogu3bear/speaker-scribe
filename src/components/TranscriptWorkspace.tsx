import { Captions, CheckCircle2, FileAudio, Loader2, PlayCircle } from "lucide-react";
import { formatClock, formatDuration, progressLabel } from "../lib/format";
import { speakerCountLabel, statusTone } from "../lib/presentation";
import type { Job } from "../types";

type TranscriptWorkspaceProps = {
  job: Job | null;
};

export function TranscriptWorkspace({ job }: TranscriptWorkspaceProps) {
  if (!job) {
    return (
      <section className="workspace" aria-label="Transcript editor">
        <div className="empty-state">
          <Captions size={28} />
          <h3>No transcript selected</h3>
          <p>Upload audio to create a local transcription job.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="workspace" aria-label="Transcript editor">
      <header className="workspace-header">
        <div>
          <div className="file-title">
            <FileAudio size={22} />
            <h2>{job.original_name}</h2>
          </div>
          <p>
            {job.model} · {formatDuration(job.duration)} · {speakerCountLabel(job.speakers.length)}
          </p>
        </div>
        <span className={`status-pill ${statusTone(job.status)}`}>
          {job.status === "completed" ? <CheckCircle2 size={16} /> : null}
          {job.status === "running" ? <Loader2 className="spin" size={16} /> : null}
          {job.status}
        </span>
      </header>

      <div className="progress-card">
        <div>
          <strong>{job.stage}</strong>
          <span>{progressLabel(job.progress)}</span>
        </div>
        <div className="progress-track" aria-label={`Progress ${progressLabel(job.progress)}`}>
          <span style={{ width: progressLabel(job.progress) }} />
        </div>
        {job.error ? <p className="error-text">{job.error}</p> : null}
      </div>

      {job.audio_url ? (
        <div className="player-row">
          <PlayCircle size={18} />
          <audio controls src={job.audio_url} />
        </div>
      ) : null}

      <TranscriptTimeline job={job} />
    </section>
  );
}

function TranscriptTimeline({ job }: { job: Job }) {
  if (job.segments.length === 0) {
    return (
      <div className="timeline">
        <div className="empty-state">
          <Captions size={28} />
          <h3>No transcript segments yet</h3>
          <p>Upload audio and the backend will stream job state here while MLX Whisper runs.</p>
        </div>
      </div>
    );
  }

  const speakersById = new Map(job.speakers.map((speaker) => [speaker.id, speaker]));

  return (
    <ol className="timeline" aria-label="Transcript segments">
      {job.segments.map((segment) => {
        const speaker = speakersById.get(segment.speaker);
        return (
          <li className="segment-row" key={segment.id}>
            <div className="segment-time">
              <span>{formatClock(segment.start)}</span>
              <small>{formatClock(segment.end)}</small>
            </div>
            <div className="segment-body">
              <div className="segment-speaker">
                <span
                  className="speaker-swatch"
                  style={{ backgroundColor: speaker?.color ?? "#64748b" }}
                />
                <strong>{speaker?.name ?? segment.speaker}</strong>
              </div>
              <p>{segment.text}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
