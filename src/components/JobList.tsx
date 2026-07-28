import { Archive, BookmarkPlus, Inbox, RefreshCcw, Undo2 } from "lucide-react";
import { COLLECTIONS, jobTitle, jobsInCollection, statusTone } from "../lib/presentation";
import type { Job, JobCollection } from "../types";

type JobListProps = {
  jobs: Job[];
  activeJobId: string | null;
  collection: JobCollection;
  onSelectJob: (id: string) => void;
  onSelectCollection: (collection: JobCollection) => void;
  onFileJob: (job: Job, collection: JobCollection) => void;
  onRefresh: () => void;
};

export function JobList({
  jobs,
  activeJobId,
  collection,
  onSelectJob,
  onSelectCollection,
  onFileJob,
  onRefresh,
}: JobListProps) {
  const active = COLLECTIONS.find((item) => item.key === collection) ?? COLLECTIONS[0];
  const visible = jobsInCollection(jobs, collection);

  return (
    <>
      <div className="panel-heading">
        <span>Transcripts</span>
        <button className="icon-button" type="button" onClick={onRefresh} aria-label="Refresh jobs">
          <RefreshCcw size={16} />
        </button>
      </div>

      <div className="collection-tabs" role="tablist" aria-label="Transcript collections">
        {COLLECTIONS.map((item) => {
          const count = jobsInCollection(jobs, item.key).length;
          return (
            <button
              key={item.key}
              role="tab"
              type="button"
              aria-selected={item.key === collection}
              className={`collection-tab ${item.key === collection ? "selected" : ""}`}
              onClick={() => onSelectCollection(item.key)}
            >
              {item.label}
              {count > 0 ? <span className="collection-count">{count}</span> : null}
            </button>
          );
        })}
      </div>

      <div className="job-list">
        {visible.length === 0 ? (
          <p className="empty-list">{active.empty}</p>
        ) : (
          visible.map((job) => (
            <div className={`job-item ${job.id === activeJobId ? "selected" : ""}`} key={job.id}>
              <button className="job-open" type="button" onClick={() => onSelectJob(job.id)}>
                <span className={`status-dot ${statusTone(job.status)}`} aria-hidden="true" />
                <span>
                  <strong>{jobTitle(job)}</strong>
                  <small>{job.stage}</small>
                </span>
              </button>
              <JobActions job={job} collection={collection} onFileJob={onFileJob} />
            </div>
          ))
        )}
      </div>
    </>
  );
}

function JobActions({
  job,
  collection,
  onFileJob,
}: {
  job: Job;
  collection: JobCollection;
  onFileJob: (job: Job, collection: JobCollection) => void;
}) {
  if (collection === "archived") {
    return (
      <button
        className="icon-button"
        type="button"
        title="Restore to inbox"
        aria-label={`Restore ${jobTitle(job)} to inbox`}
        onClick={() => onFileJob(job, "inbox")}
      >
        <Undo2 size={15} />
      </button>
    );
  }

  return (
    <div className="job-actions">
      {collection === "inbox" ? (
        <button
          className="icon-button"
          type="button"
          title="Save to conversations"
          aria-label={`Save ${jobTitle(job)} to conversations`}
          onClick={() => onFileJob(job, "saved")}
        >
          <BookmarkPlus size={15} />
        </button>
      ) : (
        <button
          className="icon-button"
          type="button"
          title="Move back to inbox"
          aria-label={`Move ${jobTitle(job)} back to inbox`}
          onClick={() => onFileJob(job, "inbox")}
        >
          <Inbox size={15} />
        </button>
      )}
      <button
        className="icon-button"
        type="button"
        title="Archive"
        aria-label={`Archive ${jobTitle(job)}`}
        onClick={() => onFileJob(job, "archived")}
      >
        <Archive size={15} />
      </button>
    </div>
  );
}
