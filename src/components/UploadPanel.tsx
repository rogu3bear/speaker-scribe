import { Loader2, UploadCloud } from "lucide-react";
import type { ChangeEvent, FormEvent } from "react";
import type { ModelInfo, TranscribeOptions } from "../types";
import { CacheSummary, ModelPicker } from "./ModelPicker";

type UploadPanelProps = {
  selectedFile: File | null;
  options: TranscribeOptions;
  uploading: boolean;
  models: ModelInfo[];
  busyModel: string | null;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onOptionChange: <K extends keyof TranscribeOptions>(
    key: K,
    value: TranscribeOptions[K],
  ) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onDownloadModel: (value: string) => void;
  onRemoveModel: (model: ModelInfo) => void;
};

export function UploadPanel({
  selectedFile,
  options,
  uploading,
  models,
  busyModel,
  onFileChange,
  onOptionChange,
  onSubmit,
  onDownloadModel,
  onRemoveModel,
}: UploadPanelProps) {
  return (
    <form className="upload-panel" onSubmit={onSubmit}>
      <label className="dropzone">
        <UploadCloud size={28} />
        <span>Drop audio</span>
        <small>{selectedFile ? selectedFile.name : "WAV, MP3, M4A, FLAC, AAC"}</small>
        <input type="file" accept="audio/*,.m4a,.mp3,.wav,.flac,.aac" onChange={onFileChange} />
      </label>

      <div className="field">
        <span>MLX model</span>
        <ModelPicker
          models={models}
          value={options.model}
          busy={busyModel}
          onSelect={(value) => onOptionChange("model", value)}
          onDownload={onDownloadModel}
          onRemove={onRemoveModel}
        />
        <CacheSummary models={models} />
      </div>

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
