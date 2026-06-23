import { Braces, Captions, Download, FileText } from "lucide-react";
import { exportUrl } from "../api";
import { formatClock } from "../lib/format";
import type { Job, Speaker } from "../types";

type SpeakerPanelProps = {
  job: Job | null;
  onRenameSpeaker: (speaker: Speaker, name: string) => void;
};

const EXPORT_ACTIONS = [
  { format: "txt", label: "TXT", icon: FileText },
  { format: "srt", label: "SRT", icon: Captions },
  { format: "json", label: "JSON", icon: Braces },
] as const;

export function SpeakerPanel({ job, onRenameSpeaker }: SpeakerPanelProps) {
  return (
    <aside className="sidebar right-panel" aria-label="Speakers and export">
      <div className="panel-heading">
        <span>Detected speakers</span>
        <strong>{job?.speakers.length ?? 0}</strong>
      </div>

      <div className="speaker-list">
        {job && job.speakers.length > 0 ? (
          job.speakers.map((speaker) => (
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
                  onChange={(event) => onRenameSpeaker(speaker, event.target.value)}
                />
              </span>
            </label>
          ))
        ) : (
          <p className="empty-list">Speaker labels appear after diarization.</p>
        )}
      </div>

      <div className="export-panel">
        <h2>Export</h2>
        <p>Speaker names are applied to exports at download time.</p>
        <div className="export-actions">
          {EXPORT_ACTIONS.map(({ format, label, icon: Icon }) =>
            job ? (
              <a key={format} className="secondary-button" href={exportUrl(job.id, format)}>
                <Icon size={17} />
                {label}
              </a>
            ) : (
              <span key={format} className="secondary-button disabled-action" aria-disabled="true">
                <Icon size={17} />
                {label}
              </span>
            ),
          )}
        </div>
      </div>

      <div className="local-note">
        <Download size={17} />
        <span>Real names require user labeling or enrolled voices; diarization detects speaker turns.</span>
      </div>
    </aside>
  );
}
