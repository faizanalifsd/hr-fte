import { useState } from "react";
import { MapPin, DollarSign, ExternalLink, Star, Clock, ChevronDown, ChevronUp, Mail, User, Database, Loader2, BriefcaseBusiness } from "lucide-react";
import type { Job } from "./JobCard";

interface JobFeedProps {
  jobs: Job[];
  isLoading?: boolean;
  missionActive?: boolean;
}

const JOBS_PER_PAGE = 10;

const JobFeed = ({ jobs, isLoading = false, missionActive = false }: JobFeedProps) => {
  const [visibleCount, setVisibleCount] = useState(JOBS_PER_PAGE);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [rawExpanded, setRawExpanded] = useState<string | null>(null);

  const visibleJobs = jobs.slice(0, visibleCount);

  // No mission running — prompt user to start one
  if (!missionActive && jobs.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-3 text-center px-8">
        <BriefcaseBusiness className="w-10 h-10 text-muted-foreground/30" />
        <p className="text-sm font-medium text-muted-foreground">No jobs yet</p>
        <p className="text-[11px] text-muted-foreground/60 max-w-xs">
          Toggle Autonomous mode and launch a mission to start scraping real job listings.
        </p>
      </div>
    );
  }

  // Mission active but jobs still loading / scraping in progress
  if (missionActive && jobs.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-3 text-center">
        <Loader2 className="w-6 h-6 text-primary animate-spin" />
        <p className="text-sm font-medium text-muted-foreground">
          {isLoading ? "Scraping jobs…" : "Waiting for job results…"}
        </p>
        <p className="text-[11px] text-muted-foreground/50">
          Jobs will appear here as the scraper runs
        </p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto scrollbar-thin pr-1 space-y-3">
      {visibleJobs.map((job) => {
        const isExpanded = expandedJobId === job.id;
        const confidenceColor =
          job.confidence >= 80 ? "text-success" : job.confidence >= 60 ? "text-warning" : "text-destructive";

        return (
          <div key={job.id} className="glass-panel overflow-hidden transition-all duration-300">
            {/* Card Summary */}
            <button
              onClick={() => setExpandedJobId(isExpanded ? null : job.id)}
              className="w-full text-left p-4 hover:bg-secondary/20 transition-colors"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1 pr-3">
                  <h3 className="text-sm font-semibold text-foreground leading-tight">{job.title}</h3>
                  <p className="text-xs font-medium text-primary mt-0.5">{job.company}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <div className={`flex items-center gap-1 ${confidenceColor}`}>
                    <Star className="w-3 h-3 fill-current" />
                    <span className="text-xs font-mono font-medium">{job.confidence}%</span>
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-muted-foreground" />
                  )}
                </div>
              </div>

              <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                <span className="flex items-center gap-1">
                  <MapPin className="w-3 h-3" /> {job.location}
                </span>
                <span className="flex items-center gap-1">
                  <DollarSign className="w-3 h-3" /> {job.salary}
                </span>
                <span className="flex items-center gap-1">
                  <ExternalLink className="w-3 h-3" /> {job.source}
                </span>
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" /> {job.scrapedAt}
                </span>
              </div>
            </button>

            {/* Expanded Detail */}
            {isExpanded && (
              <div className="border-t border-border/30 p-4 space-y-4 animate-fade-in">
                {/* Contact */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="glass-panel p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <Mail className="w-3 h-3 text-muted-foreground" />
                      <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-medium">HR Email</span>
                    </div>
                    <p className="text-xs font-mono text-foreground">{job.hrEmail}</p>
                  </div>
                  <div className="glass-panel p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <User className="w-3 h-3 text-muted-foreground" />
                      <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-medium">Hiring Manager</span>
                    </div>
                    <p className="text-xs text-foreground">{job.hiringManager}</p>
                  </div>
                </div>

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
                  <h4 className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                    Full Description
                  </h4>
                  <div className="glass-panel p-3 text-xs text-secondary-foreground leading-relaxed whitespace-pre-wrap">
                    {job.description}
                  </div>
                </div>

                {/* Source metadata */}
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

                {/* Raw Data */}
                <div className="glass-panel overflow-hidden">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setRawExpanded(rawExpanded === job.id ? null : job.id);
                    }}
                    className="flex items-center justify-between w-full p-3 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <span className="uppercase tracking-wider font-semibold text-[10px]">Raw Data (JSON)</span>
                    {rawExpanded === job.id ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  </button>
                  {rawExpanded === job.id && (
                    <div className="px-3 pb-3">
                      <pre className="text-[10px] font-mono text-muted-foreground bg-background/50 rounded-lg p-3 overflow-x-auto scrollbar-thin">
                        {JSON.stringify(job.rawData, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}

      {visibleCount < jobs.length && (
        <button
          onClick={() => setVisibleCount((c) => c + JOBS_PER_PAGE)}
          className="w-full py-3 text-xs font-medium text-primary hover:text-primary/80 glass-panel transition-colors"
        >
          View More Jobs ({jobs.length - visibleCount} remaining)
        </button>
      )}
    </div>
  );
};

export default JobFeed;
