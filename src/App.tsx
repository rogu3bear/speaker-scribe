import { AlertTriangle, Mic2 } from "lucide-react";
import { useEffect, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import {
  downloadModel,
  fetchHealth,
  fetchJob,
  fetchJobs,
  fetchModels,
  fileJob,
  removeModel,
  renameSpeakers,
  uploadAudio,
} from "./api";
import { JobList } from "./components/JobList";
import { LegalPanel } from "./components/LegalPanel";
import type { LegalDocument } from "./components/LegalPanel";
import { SpeakerPanel } from "./components/SpeakerPanel";
import { TranscriptWorkspace } from "./components/TranscriptWorkspace";
import { UploadPanel } from "./components/UploadPanel";
import { DEFAULT_TRANSCRIBE_OPTIONS } from "./constants";
import { canPollJob, preferredModel } from "./lib/presentation";
import type { Health, Job, JobCollection, ModelInfo, Speaker, TranscribeOptions } from "./types";

function App() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [options, setOptions] = useState<TranscribeOptions>(DEFAULT_TRANSCRIBE_OPTIONS);
  const [uploading, setUploading] = useState(false);
  const [apiNotice, setApiNotice] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [collection, setCollection] = useState<JobCollection>("inbox");
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [busyModel, setBusyModel] = useState<string | null>(null);
  const [modelSettled, setModelSettled] = useState(false);
  const [legal, setLegal] = useState<LegalDocument | null>(null);

  const activeJob = jobs.find((job) => job.id === activeJobId) ?? null;

  async function refreshJobs() {
    try {
      const remoteJobs = await fetchJobs();
      setJobs(remoteJobs);
      setActiveJobId((currentId) =>
        remoteJobs.some((job) => job.id === currentId) ? currentId : remoteJobs[0]?.id ?? null,
      );
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
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    void refreshModels();
  }, []);

  // Settle on a model that is actually on disk, once, when the catalog first
  // arrives. Only then is it known what this machine has: a fresh install of the
  // packaged app has just the shipped model, and a long-running one may have
  // every model. After this the choice belongs to the user, so it never runs
  // again — including when a download finishes, which would otherwise move the
  // picker underneath them.
  useEffect(() => {
    if (modelSettled || models.length === 0) {
      return;
    }
    const preferred = preferredModel(models);
    if (preferred) {
      setOptions((current) => ({ ...current, model: preferred }));
    }
    setModelSettled(true);
  }, [models, modelSettled]);

  // A download runs on a worker thread, so poll while one is in flight.
  useEffect(() => {
    if (!models.some((model) => model.state === "downloading")) {
      return;
    }
    const handle = window.setInterval(() => void refreshModels(), 3000);
    return () => window.clearInterval(handle);
  }, [models]);

  async function refreshModels() {
    try {
      setModels(await fetchModels());
    } catch {
      // The picker falls back to whatever it already has.
    }
  }

  async function startModelDownload(value: string) {
    setBusyModel(value);
    try {
      setModels(await downloadModel(value));
      setApiNotice(null);
    } catch (error) {
      setApiNotice(error instanceof Error ? error.message : "Could not start the download");
    } finally {
      setBusyModel(null);
    }
  }

  async function deleteModel(model: ModelInfo) {
    const confirmed = window.confirm(
      `Remove ${model.label}? This frees disk space and the weights are re-downloaded ` +
        "the next time the model is used.",
    );
    if (!confirmed) {
      return;
    }
    setBusyModel(model.value);
    try {
      setModels(await removeModel(model.value));
      setApiNotice(null);
    } catch (error) {
      setApiNotice(error instanceof Error ? error.message : "Could not remove that model");
    } finally {
      setBusyModel(null);
    }
  }

  useEffect(() => {
    if (!canPollJob(activeJob)) {
      return;
    }

    const handle = window.setInterval(async () => {
      try {
        const job = await fetchJob(activeJob.id);
        replaceJob(job);
      } catch (error) {
        setApiNotice(error instanceof Error ? error.message : "Unable to refresh job");
      }
    }, 1500);

    return () => window.clearInterval(handle);
  }, [activeJob?.id, activeJob?.status]);

  function updateOption<K extends keyof TranscribeOptions>(key: K, value: TranscribeOptions[K]) {
    setOptions((current) => ({ ...current, [key]: value }));
  }

  function replaceJob(updated: Job) {
    setJobs((current) => current.map((job) => (job.id === updated.id ? updated : job)));
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
      setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)]);
      setActiveJobId(job.id);
      setSelectedFile(null);
      setApiNotice(null);
    } catch (error) {
      setApiNotice(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function moveJob(job: Job, next: JobCollection) {
    try {
      replaceJob(await fileJob(job.id, next));
      setApiNotice(null);
    } catch (error) {
      setApiNotice(error instanceof Error ? error.message : "Could not move that transcript");
    }
  }

  async function updateSpeakerName(speaker: Speaker, name: string) {
    if (!activeJob) {
      return;
    }

    try {
      const updated = await renameSpeakers(activeJob.id, {
        speakers: { [speaker.id]: name },
      });
      replaceJob(updated);
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

        {health && !health.ml_ready ? (
          <div className="notice" role="alert">
            <AlertTriangle size={16} />
            <span>
              <strong>Real transcription is unavailable.</strong>{" "}
              {health.detail ?? "The local speech engine is not ready."} Uploads will fail
              until this is resolved.
            </span>
          </div>
        ) : null}

        <UploadPanel
          selectedFile={selectedFile}
          options={options}
          uploading={uploading}
          models={models}
          busyModel={busyModel}
          onFileChange={onFileChange}
          onOptionChange={updateOption}
          onSubmit={onSubmit}
          onDownloadModel={(value) => void startModelDownload(value)}
          onRemoveModel={(model) => void deleteModel(model)}
        />

        {apiNotice ? (
          <div className="notice" role="status">
            <AlertTriangle size={16} />
            <span>{apiNotice}</span>
          </div>
        ) : null}

        <JobList
          jobs={jobs}
          activeJobId={activeJobId}
          collection={collection}
          onSelectJob={setActiveJobId}
          onSelectCollection={setCollection}
          onFileJob={(job, next) => void moveJob(job, next)}
          onRefresh={() => void refreshJobs()}
        />

        <footer className="sidebar-footer">
          <span>Audio stays on this Mac.</span>
          <button type="button" className="link-button" onClick={() => setLegal("privacy")}>
            Privacy
          </button>
          <button type="button" className="link-button" onClick={() => setLegal("terms")}>
            Terms
          </button>
        </footer>
      </aside>

      <TranscriptWorkspace job={activeJob} />
      <SpeakerPanel job={activeJob} onRenameSpeaker={updateSpeakerName} />

      {legal ? <LegalPanel document={legal} onClose={() => setLegal(null)} /> : null}
    </main>
  );
}

export default App;
