import {
  AlertTriangle,
  Braces,
  Captions,
  CheckCircle2,
  Download,
  FileAudio,
  FileText,
  Loader2,
  Mic2,
  PlayCircle,
  RefreshCcw,
  UploadCloud,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { exportUrl, fetchJob, fetchJobs, renameSpeakers, uploadAudio } from "./api";
import { formatClock, formatDuration, progressLabel } from "./lib/format";
import { demoJob } from "./mockData";
import type { Job, Speaker, TranscribeOptions } from "./types";

const modelOptions = [
  { label: "large-v3", value: "large-v3" },
  { label: "large-v3-turbo", value: "large-v3-turbo" },
  { label: "mlx-community/whisper-large-v3-turbo", value: "mlx-community/whisper-large-v3-turbo" },
  { label: "mlx-community/whisper-small-mlx", value: "mlx-community/whisper-small-mlx" },
];

function statusTone(status: Job["status"]): string {
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

function speakerName(job: Job, speakerId: string): string {
  return job.speakers.find((speaker) => speaker.id === speakerId)?.name ?? speakerId;
}

function App() {
  const [jobs, setJobs] = useState<Job[]>([demoJob]);
  const [activeJobId, setActiveJobId] = useState<string>("demo");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [options, setOptions] = useState<TranscribeOptions>({
    model: "large-v3",
    diarize: true,
    min_speakers: undefined,
    max_speakers: undefined,
    language: "",
  });
  const [uploading, setUploading] = useState(false);
  const [apiNotice, setApiNotice] = useState<string | null>(null);

  const activeJob = useMemo(
    () => jobs.find((job) => job.id === activeJobId) ?? jobs[0],
    [jobs, activeJobId],
  );

  const detectedSpeakerText = activeJob
    ? `${activeJob.speakers.length} ${activeJob.speakers.length === 1 ? "speaker" : "speakers"}`
    : "No speakers";

  async function refreshJobs() {
    try {
      const remoteJobs = await fetchJobs();
      if (remoteJobs.length > 0) {
        setJobs(remoteJobs);
        if (!remoteJobs.some((job) => job.id === activeJobId)) {
          setActiveJobId(remoteJobs[0].id);
        }
      }
      setApiNotice(null);
    } catch (error) {
      setApiNotice(
        error instanceof Error
          ? `Backend not connected: ${error.message}`
          : "Backend not connected",
      );
    }
  }

  useEffect(() => {
    void refreshJobs();
    const handle = window.setInterval(() => {
      void refreshJobs();
    }, 4000);
    return () => window.clearInterval(handle);
  }, []);

  useEffect(() => {
    if (!activeJob || !["queued", "running"].includes(activeJob.status) || activeJob.id === "demo") {
      return;
    }

    const handle = window.setInterval(async () => {
      try {
        const job = await fetchJob(activeJob.id);
        setJobs((current) => current.map((item) => (item.id === job.id ? job : item)));
      } catch (error) {
        setApiNotice(error instanceof Error ? error.message : "Unable to refresh job");
      }
    }, 1500);

    return () => window.clearInterval(handle);
  }, [activeJob?.id, activeJob?.status]);

  function updateOption<K extends keyof TranscribeOptions>(key: K, value: TranscribeOptions[K]) {
    setOptions((current) => ({ ...current, [key]: value }));
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) {
      setApiNotice("Choose an audio file first.");
      return;
    }

    setUploading(true);
    try {
      const job = await uploadAudio(selectedFile, options);
      setJobs((current) => [job, ...current.filter((item) => item.id !== "demo")]);
      setActiveJobId(job.id);
      setSelectedFile(null);
      setApiNotice(null);
    } catch (error) {
      setApiNotice(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function updateSpeakerName(speaker: Speaker, name: string) {
    if (!activeJob || activeJob.id === "demo") {
      setJobs((current) =>
        current.map((job) =>
          job.id === "demo"
            ? {
                ...job,
                speakers: job.speakers.map((item) =>
                  item.id === speaker.id ? { ...item, name } : item,
                ),
              }
            : job,
        ),
      );
      return;
    }

    try {
      const updated = await renameSpeakers(activeJob.id, {
        speakers: { [speaker.id]: name },
      });
      setJobs((current) => current.map((job) => (job.id === updated.id ? updated : job)));
      setApiNotice(null);
    } catch (error) {
      setApiNotice(error instanceof Error ? error.message : "Speaker rename failed");
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar left-panel" aria-label="Upload and jobs">
        <div className="brand-row">
          <span className="brand-mark" aria-hidden="true">
            <Mic2 size={22} />
          </span>
          <div>
            <h1>Speaker Scribe</h1>
            <p>Local MLX transcripts with speaker turns.</p>
          </div>
        </div>

        <form className="upload-panel" onSubmit={onSubmit}>
          <label className="dropzone">
            <UploadCloud size={28} />
            <span>Drop audio</span>
            <small>{selectedFile ? selectedFile.name : "WAV, MP3, M4A, FLAC, AAC"}</small>
            <input type="file" accept="audio/*,.m4a,.mp3,.wav,.flac,.aac" onChange={onFileChange} />
          </label>

          <label className="field">
            <span>MLX model</span>
            <select value={options.model} onChange={(event) => updateOption("model", event.target.value)}>
              {modelOptions.map((model) => (
                <option key={model.value} value={model.value}>
                  {model.label}
                </option>
              ))}
            </select>
          </label>

          <label className="switch-row">
            <input
              type="checkbox"
              checked={options.diarize}
              onChange={(event) => updateOption("diarize", event.target.checked)}
            />
            <span>Diarization</span>
          </label>

          <div className="stepper-grid">
            <label className="field">
              <span>Min speakers</span>
              <input
                type="number"
                min="1"
                max="12"
                inputMode="numeric"
                value={options.min_speakers ?? ""}
                onChange={(event) =>
                  updateOption(
                    "min_speakers",
                    event.target.value ? Number(event.target.value) : undefined,
                  )
                }
              />
            </label>
            <label className="field">
              <span>Max speakers</span>
              <input
                type="number"
                min="1"
                max="12"
                inputMode="numeric"
                value={options.max_speakers ?? ""}
                onChange={(event) =>
                  updateOption(
                    "max_speakers",
                    event.target.value ? Number(event.target.value) : undefined,
                  )
                }
              />
            </label>
          </div>

          <label className="field">
            <span>Language hint</span>
            <input
              type="text"
              placeholder="auto"
              value={options.language ?? ""}
              onChange={(event) => updateOption("language", event.target.value)}
            />
          </label>

          <button className="primary-button" type="submit" disabled={uploading}>
            {uploading ? <Loader2 className="spin" size={18} /> : <UploadCloud size={18} />}
            Start transcript
          </button>
        </form>

        {apiNotice ? (
          <div className="notice" role="status">
            <AlertTriangle size={16} />
            <span>{apiNotice}</span>
          </div>
        ) : null}

        <div className="panel-heading">
          <span>Jobs</span>
          <button className="icon-button" type="button" onClick={() => void refreshJobs()} aria-label="Refresh jobs">
            <RefreshCcw size={16} />
          </button>
        </div>

        <div className="job-list">
          {jobs.map((job) => (
            <button
              key={job.id}
              className={`job-item ${job.id === activeJob?.id ? "selected" : ""}`}
              type="button"
              onClick={() => setActiveJobId(job.id)}
            >
              <span className={`status-dot ${statusTone(job.status)}`} />
              <span>
                <strong>{job.original_name}</strong>
                <small>{job.stage}</small>
              </span>
            </button>
          ))}
        </div>
      </aside>

      <section className="workspace" aria-label="Transcript editor">
        {activeJob ? (
          <>
            <header className="workspace-header">
              <div>
                <div className="file-title">
                  <FileAudio size={22} />
                  <h2>{activeJob.original_name}</h2>
                </div>
                <p>
                  {activeJob.model} · {formatDuration(activeJob.duration)} · {detectedSpeakerText}
                </p>
              </div>
              <span className={`status-pill ${statusTone(activeJob.status)}`}>
                {activeJob.status === "completed" ? <CheckCircle2 size={16} /> : null}
                {activeJob.status === "running" ? <Loader2 className="spin" size={16} /> : null}
                {activeJob.status}
              </span>
            </header>

            <div className="progress-card">
              <div>
                <strong>{activeJob.stage}</strong>
                <span>{progressLabel(activeJob.progress)}</span>
              </div>
              <div className="progress-track" aria-label={`Progress ${progressLabel(activeJob.progress)}`}>
                <span style={{ width: progressLabel(activeJob.progress) }} />
              </div>
              {activeJob.error ? <p className="error-text">{activeJob.error}</p> : null}
            </div>

            {activeJob.audio_url ? (
              <div className="player-row">
                <PlayCircle size={18} />
                <audio controls src={activeJob.audio_url} />
              </div>
            ) : null}

            <div className="timeline">
              {activeJob.segments.length === 0 ? (
                <div className="empty-state">
                  <Captions size={28} />
                  <h3>No transcript segments yet</h3>
                  <p>Upload audio and the backend will stream job state here while MLX Whisper runs.</p>
                </div>
              ) : (
                activeJob.segments.map((segment) => {
                  const speaker = activeJob.speakers.find((item) => item.id === segment.speaker);
                  return (
                    <article className="segment-row" key={segment.id}>
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
                          <strong>{speakerName(activeJob, segment.speaker)}</strong>
                        </div>
                        <p>{segment.text}</p>
                      </div>
                    </article>
                  );
                })
              )}
            </div>
          </>
        ) : null}
      </section>

      <aside className="sidebar right-panel" aria-label="Speakers and export">
        <div className="panel-heading">
          <span>Detected speakers</span>
          <strong>{activeJob?.speakers.length ?? 0}</strong>
        </div>

        <div className="speaker-list">
          {activeJob?.speakers.map((speaker) => (
            <label className="speaker-editor" key={speaker.id}>
              <span className="speaker-meta">
                <span className="speaker-swatch" style={{ backgroundColor: speaker.color }} />
                <span>
                  <strong>{speaker.id}</strong>
                  <small>{formatClock(speaker.seconds)} spoken</small>
                </span>
              </span>
              <span className="rename-field">
                <span>Rename</span>
                <input
                  value={speaker.name}
                  onChange={(event) => void updateSpeakerName(speaker, event.target.value)}
                />
              </span>
            </label>
          ))}
        </div>

        <div className="export-panel">
          <h2>Export</h2>
          <p>Speaker names are applied to exports at download time.</p>
          <div className="export-actions">
            <a className="secondary-button" href={activeJob ? exportUrl(activeJob.id, "txt") : "#"}>
              <FileText size={17} />
              TXT
            </a>
            <a className="secondary-button" href={activeJob ? exportUrl(activeJob.id, "srt") : "#"}>
              <Captions size={17} />
              SRT
            </a>
            <a className="secondary-button" href={activeJob ? exportUrl(activeJob.id, "json") : "#"}>
              <Braces size={17} />
              JSON
            </a>
          </div>
        </div>

        <div className="local-note">
          <Download size={17} />
          <span>Real names require user labeling or enrolled voices; diarization detects speaker turns.</span>
        </div>
      </aside>
    </main>
  );
}

export default App;
