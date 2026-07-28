import { Braces, Captions, Download, FileText } from "lucide-react";
import { useMemo, useState } from "react";
import { exportUrl } from "../api";
import { formatClock } from "../lib/format";
import { voiceMetrics } from "../lib/metrics";
import type { VoiceMetrics } from "../lib/metrics";
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

const percent = (value: number) => `${Math.round(value * 100)}%`;

export function SpeakerPanel({ job, onRenameSpeaker }: SpeakerPanelProps) {
  const [openVoice, setOpenVoice] = useState<string | null>(null);
  const metrics = useMemo(() => (job ? voiceMetrics(job) : new Map()), [job]);
  const nameFor = (speakerId: string) =>
    job?.speakers.find((item) => item.id === speakerId)?.name ?? speakerId;

  return (
    <aside className="sidebar right-panel" aria-label="Speakers and export">
      <div className="panel-heading">
        <span>Detected speakers</span>
        <strong>{job?.speakers.length ?? 0}</strong>
      </div>

      <div className="speaker-list">
        {job && job.speakers.length > 0 ? (
          job.speakers.map((speaker) => {
            const open = openVoice === speaker.id;
            const stats = metrics.get(speaker.id);
            return (
              <div className={`speaker-card ${open ? "open" : ""}`} key={speaker.id}>
                <button
                  className="speaker-summary"
                  type="button"
                  aria-expanded={open}
                  onClick={() => setOpenVoice(open ? null : speaker.id)}
                >
                  <span className="speaker-swatch" style={{ backgroundColor: speaker.color }} />
                  <span className="speaker-identity">
                    <strong>{speaker.name}</strong>
                    <small>
                      {formatClock(speaker.seconds)} spoken
                      {stats ? ` · ${percent(stats.shareOfTalk)} of talk` : ""}
                    </small>
                  </span>
                </button>

                {stats ? (
                  <div className="share-bar" aria-hidden="true">
                    <span
                      style={{
                        width: percent(stats.shareOfTalk),
                        backgroundColor: speaker.color,
                      }}
                    />
                  </div>
                ) : null}

                {open ? (
                  <div className="voice-detail">
                    {stats ? <VoiceStats stats={stats} nameFor={nameFor} /> : null}
                    <label className="rename-field">
                      <span>Rename</span>
                      <input
                        value={speaker.name}
                        onChange={(event) => onRenameSpeaker(speaker, event.target.value)}
                      />
                    </label>
                    {speaker.voice_id ? (
                      <p className="voice-id" title={speaker.voice_id}>
                        Voice ID <code>{speaker.voice_id.slice(0, 12)}</code>
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })
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
        <span>
          Real names require user labeling or enrolled voices; diarization detects speaker turns.
        </span>
      </div>
    </aside>
  );
}

function VoiceStats({
  stats,
  nameFor,
}: {
  stats: VoiceMetrics;
  nameFor: (speakerId: string) => string;
}) {
  const rows: [string, string][] = [
    ["Words", stats.words.toLocaleString()],
    ["Pace", `${Math.round(stats.wordsPerMinute)} wpm`],
    ["Turns", String(stats.turns)],
    ["Avg turn", `${formatClock(stats.averageTurnSeconds)} · ${Math.round(stats.averageTurnWords)}w`],
    ["Longest turn", formatClock(stats.longestTurnSeconds)],
    ["Questions", String(stats.questions)],
    ["Fillers", `${stats.fillerWords} (${percent(stats.fillerRate)})`],
  ];

  if (stats.firstHeardAt !== null && stats.lastHeardAt !== null) {
    rows.push(["Heard", `${formatClock(stats.firstHeardAt)}–${formatClock(stats.lastHeardAt)}`]);
  }

  return (
    <>
      <dl className="voice-stats">
        {rows.map(([label, value]) => (
          <div className="voice-stat" key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <ul className="voice-relations">
        {stats.respondsTo ? (
          <li>
            Most often answers <strong>{nameFor(stats.respondsTo.speaker)}</strong>
            <span> ({stats.respondsTo.count}×)</span>
          </li>
        ) : null}
        {stats.answeredBy ? (
          <li>
            Most often answered by <strong>{nameFor(stats.answeredBy.speaker)}</strong>
            <span> ({stats.answeredBy.count}×)</span>
          </li>
        ) : null}
      </ul>
    </>
  );
}
