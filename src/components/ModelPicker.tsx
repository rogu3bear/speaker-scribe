import { Check, ChevronDown, Download, HardDrive, Loader2, Trash2, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ModelInfo } from "../types";

type ModelPickerProps = {
  models: ModelInfo[];
  value: string;
  busy: string | null;
  onSelect: (value: string) => void;
  onDownload: (value: string) => void;
  onRemove: (model: ModelInfo) => void;
};

export function formatBytes(bytes: number): string {
  if (bytes <= 0) {
    return "—";
  }
  if (bytes >= 1_000_000_000) {
    return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
  }
  return `${Math.round(bytes / 1_000_000)} MB`;
}

export function formatDownloadSize(megabytes: number): string {
  return megabytes >= 1000 ? `${(megabytes / 1000).toFixed(1)} GB` : `${megabytes} MB`;
}

/**
 * Model chooser with on-disk state.
 *
 * A native select cannot show which weights are already downloaded, how much
 * space each takes, or offer a way to fetch and remove them — and picking an
 * absent model silently costs gigabytes on the next run.
 */
export function ModelPicker({
  models,
  value,
  busy,
  onSelect,
  onDownload,
  onRemove,
}: ModelPickerProps) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const selected = models.find((model) => model.value === value);

  useEffect(() => {
    if (!open) {
      return;
    }
    function onPointerDown(event: MouseEvent) {
      if (root.current && !root.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="model-picker" ref={root}>
      <button
        className="model-trigger"
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="model-trigger-text">
          <strong>{selected?.label ?? value}</strong>
          <small>
            {selected ? (
              <>
                <StateLabel model={selected} /> · {selected.speed}
              </>
            ) : (
              "Custom model"
            )}
          </small>
        </span>
        <ChevronDown size={16} aria-hidden="true" />
      </button>

      {open ? (
        <div className="model-menu" role="listbox" aria-label="Whisper models">
          {models.map((model) => (
            <div
              className={`model-option ${model.value === value ? "selected" : ""}`}
              key={model.value}
            >
              <button
                className="model-choose"
                type="button"
                role="option"
                aria-selected={model.value === value}
                onClick={() => {
                  onSelect(model.value);
                  setOpen(false);
                }}
              >
                <span className="model-option-head">
                  <strong>{model.label}</strong>
                  {model.value === value ? <Check size={14} aria-hidden="true" /> : null}
                </span>
                <span className="model-option-meta">
                  <StateLabel model={model} /> · {model.speed}
                </span>
                <span className="model-option-hint">{model.hint}</span>
              </button>
              <ModelAction
                model={model}
                busy={busy === model.value}
                onDownload={onDownload}
                onRemove={onRemove}
              />
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function StateLabel({ model }: { model: ModelInfo }) {
  if (model.state === "downloading") {
    return <span className="model-state downloading">Downloading…</span>;
  }
  if (model.state === "error") {
    return (
      <span className="model-state error" title={model.detail ?? undefined}>
        Download failed
      </span>
    );
  }
  if (model.state === "available") {
    return <span className="model-state available">On disk · {formatBytes(model.size_on_disk)}</span>;
  }
  return (
    <span className="model-state missing">
      Not downloaded · {formatDownloadSize(model.download_mb)}
    </span>
  );
}

function ModelAction({
  model,
  busy,
  onDownload,
  onRemove,
}: {
  model: ModelInfo;
  busy: boolean;
  onDownload: (value: string) => void;
  onRemove: (model: ModelInfo) => void;
}) {
  if (model.state === "downloading" || busy) {
    return (
      <span className="icon-button" aria-label="Working">
        <Loader2 className="spin" size={15} />
      </span>
    );
  }
  if (model.state === "available") {
    return (
      <button
        className="icon-button"
        type="button"
        title={`Remove ${model.label} (${formatBytes(model.size_on_disk)})`}
        aria-label={`Remove ${model.label}`}
        onClick={() => onRemove(model)}
      >
        <Trash2 size={15} />
      </button>
    );
  }
  return (
    <button
      className="icon-button"
      type="button"
      title={`Download ${model.label} (${formatDownloadSize(model.download_mb)})`}
      aria-label={`Download ${model.label}`}
      onClick={() => onDownload(model.value)}
    >
      {model.state === "error" ? <TriangleAlert size={15} /> : <Download size={15} />}
    </button>
  );
}

export function CacheSummary({ models }: { models: ModelInfo[] }) {
  const onDisk = models.filter((model) => model.state === "available");
  if (onDisk.length === 0) {
    return null;
  }
  const total = onDisk.reduce((sum, model) => sum + model.size_on_disk, 0);
  return (
    <small className="field-hint">
      <HardDrive size={12} aria-hidden="true" /> {onDisk.length} of {models.length} models on disk,{" "}
      {formatBytes(total)} total.
    </small>
  );
}
