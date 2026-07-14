import { useState } from "react";
import { ExternalLink, Mail, User, ChevronDown, ChevronUp, Database, Clock } from "lucide-react";
import type { Job } from "./JobCard";

interface JobDetailProps {
  job: Job | null;
}

const JobDetail = ({ job }: JobDetailProps) => {
  const [rawExpanded, setRawExpanded] = useState(false);

  if (!job) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-12 h-12 rounded-xl bg-muted/50 flex items-center justify-center mx-auto mb-3">
            <Database className="w-5 h-5 text-muted-foreground/40" />
          </div>
          <p className="text-sm text-muted-foreground">Select a job to view details</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 overflow-y-auto h-full scrollbar-thin pr-1">
      <div>
        <h2 className="text-xl font-semibold text-foreground mb-1">{job.title}</h2>
        <p className="text-sm text-primary font-medium">{job.company}</p>
      </div>

      {/* Contact Info */}
      <div className="grid grid-cols-2 gap-3">
        <div className="glass-panel p-3">
          <div className="flex items-center gap-2 mb-1.5">
            <Mail className="w-3.5 h-3.5 text-muted-foreground" />
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">HR Email</span>
          </div>
          <p className="text-xs text-foreground font-mono">{job.hrEmail}</p>
        </div>
        <div className="glass-panel p-3">
          <div className="flex items-center gap-2 mb-1.5">
            <User className="w-3.5 h-3.5 text-muted-foreground" />
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Hiring Manager</span>
          </div>
          <p className="text-xs text-foreground">{job.hiringManager}</p>
        </div>
      </div>

      {/* Direct Link */}
      <a
        href={job.directLink}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-2 text-xs text-primary hover:text-primary/80 transition-colors"
      >
        <ExternalLink className="w-3.5 h-3.5" />
        <span className="font-mono underline underline-offset-2">View Original Listing</span>
      </a>

      {/* Description */}
      <div>
        <h3 className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
          Full Description
        </h3>
        <div className="glass-panel p-4 text-sm text-secondary-foreground leading-relaxed whitespace-pre-wrap">
          {job.description}
        </div>
      </div>

      {/* Source Metadata */}
      <div className="flex items-center gap-4 text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <Database className="w-3 h-3" />
          Source: <span className="font-mono text-foreground/70">{job.sourceType}</span>
        </span>
        <span className="flex items-center gap-1.5">
          <Clock className="w-3 h-3" />
          Fetched: <span className="font-mono text-foreground/70">{job.fetchTime}</span>
        </span>
      </div>

      {/* Raw Data Collapsible */}
      <div className="glass-panel overflow-hidden">
        <button
          onClick={() => setRawExpanded(!rawExpanded)}
          className="flex items-center justify-between w-full p-3 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <span className="uppercase tracking-wider font-semibold">Raw Data (JSON)</span>
          {rawExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {rawExpanded && (
          <div className="px-3 pb-3">
            <pre className="text-[11px] font-mono text-muted-foreground bg-background/50 rounded-lg p-3 overflow-x-auto scrollbar-thin">
              {JSON.stringify(job.rawData, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};

export default JobDetail;
