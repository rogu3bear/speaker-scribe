import { AlertTriangle, Mic2 } from "lucide-react";
import { useEffect, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { fetchJob, fetchJobs, renameSpeakers, uploadAudio } from "./api";
import { JobList } from "./components/JobList";
import { SpeakerPanel } from "./components/SpeakerPanel";
import { TranscriptWorkspace } from "./components/TranscriptWorkspace";
import { UploadPanel } from "./components/UploadPanel";
import { DEFAULT_TRANSCRIBE_OPTIONS } from "./constants";
import { canPollJob } from "./lib/presentation";
import type { Job, Speaker, TranscribeOptions } from "./types";

function App() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [options, setOptions] = useState<TranscribeOptions>(DEFAULT_TRANSCRIBE_OPTIONS);
  const [uploading, setUploading] = useState(false);
  const [apiNotice, setApiNotice] = useState<string | null>(null);

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

        <UploadPanel
          selectedFile={selectedFile}
          options={options}
          uploading={uploading}
          onFileChange={onFileChange}
          onOptionChange={updateOption}
          onSubmit={onSubmit}
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
          onSelectJob={setActiveJobId}
          onRefresh={() => void refreshJobs()}
        />
      </aside>

      <TranscriptWorkspace job={activeJob} />
      <SpeakerPanel job={activeJob} onRenameSpeaker={updateSpeakerName} />
    </main>
  );
}

export default App;
