import { Loader2, UploadCloud } from "lucide-react";
import type { ChangeEvent, FormEvent } from "react";
import { MODEL_OPTIONS, modelOption } from "../constants";
import type { TranscribeOptions } from "../types";

type UploadPanelProps = {
  selectedFile: File | null;
  options: TranscribeOptions;
  uploading: boolean;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onOptionChange: <K extends keyof TranscribeOptions>(
    key: K,
    value: TranscribeOptions[K],
  ) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function UploadPanel({
  selectedFile,
  options,
  uploading,
  onFileChange,
  onOptionChange,
  onSubmit,
}: UploadPanelProps) {
  return (
    <form className="upload-panel" onSubmit={onSubmit}>
      <label className="dropzone">
        <UploadCloud size={28} />
        <span>Drop audio</span>
        <small>{selectedFile ? selectedFile.name : "WAV, MP3, M4A, FLAC, AAC"}</small>
        <input type="file" accept="audio/*,.m4a,.mp3,.wav,.flac,.aac" onChange={onFileChange} />
      </label>

      <label className="field">
        <span>MLX model</span>
        <select
          value={options.model}
          onChange={(event) => onOptionChange("model", event.target.value)}
        >
          {MODEL_OPTIONS.map((model) => (
            <option key={model.value} value={model.value}>
              {model.label} · {model.size} · {model.speed}
            </option>
          ))}
        </select>
        <ModelHint value={options.model} />
      </label>

      <label className="switch-row">
        <input
          type="checkbox"
          checked={options.diarize}
          onChange={(event) => onOptionChange("diarize", event.target.checked)}
        />
        <span>Diarization</span>
      </label>

      <div className="stepper-grid">
        <SpeakerLimitField
          label="Min speakers"
          value={options.min_speakers}
          onChange={(value) => onOptionChange("min_speakers", value)}
        />
        <SpeakerLimitField
          label="Max speakers"
          value={options.max_speakers}
          onChange={(value) => onOptionChange("max_speakers", value)}
        />
      </div>

      <label className="field">
        <span>Language hint</span>
        <input
          type="text"
          placeholder="auto"
          value={options.language ?? ""}
          onChange={(event) => onOptionChange("language", event.target.value)}
        />
      </label>

      <button className="primary-button" type="submit" disabled={uploading}>
        {uploading ? <Loader2 className="spin" size={18} /> : <UploadCloud size={18} />}
        Start transcript
      </button>
    </form>
  );
}

function ModelHint({ value }: { value: string }) {
  const model = modelOption(value);
  if (!model) {
    return <small className="field-hint">Custom model — passed to MLX Whisper as given.</small>;
  }
  return (
    <small className="field-hint">
      {model.hint} Downloads once ({model.size}), then cached.
    </small>
  );
}

type SpeakerLimitFieldProps = {
  label: string;
  value: number | undefined;
  onChange: (value: number | undefined) => void;
};

function SpeakerLimitField({ label, value, onChange }: SpeakerLimitFieldProps) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type="number"
        min="1"
        max="12"
        inputMode="numeric"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value ? Number(event.target.value) : undefined)}
      />
    </label>
  );
}
