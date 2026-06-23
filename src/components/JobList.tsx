import { RefreshCcw } from "lucide-react";
import { statusTone } from "../lib/presentation";
import type { Job } from "../types";

type JobListProps = {
  jobs: Job[];
  activeJobId: string | null;
  onSelectJob: (id: string) => void;
  onRefresh: () => void;
};

export function JobList({ jobs, activeJobId, onSelectJob, onRefresh }: JobListProps) {
  return (
    <>
      <div className="panel-heading">
        <span>Jobs</span>
        <button className="icon-button" type="button" onClick={onRefresh} aria-label="Refresh jobs">
          <RefreshCcw size={16} />
        </button>
      </div>

      <div className="job-list">
        {jobs.length === 0 ? (
          <p className="empty-list">No jobs yet.</p>
        ) : (
          jobs.map((job) => (
            <button
              key={job.id}
              className={`job-item ${job.id === activeJobId ? "selected" : ""}`}
              type="button"
              onClick={() => onSelectJob(job.id)}
            >
              <span className={`status-dot ${statusTone(job.status)}`} aria-hidden="true" />
              <span>
                <strong>{job.original_name}</strong>
                <small>{job.stage}</small>
              </span>
            </button>
          ))
        )}
      </div>
    </>
  );
}
