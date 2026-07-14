import { MapPin, DollarSign, Clock, ExternalLink, Star } from "lucide-react";

export interface Job {
  id: string;
  title: string;
  company: string;
  location: string;
  salary: string;
  source: string;
  scrapedAt: string;
  confidence: number;
  description: string;
  hrEmail: string;
  hiringManager: string;
  directLink: string;
  rawData: Record<string, unknown>;
  sourceType: "API" | "Scrape";
  fetchTime: string;
}

interface JobCardProps {
  job: Job;
  isSelected: boolean;
  onSelect: () => void;
}

const JobCard = ({ job, isSelected, onSelect }: JobCardProps) => {
  const confidenceColor =
    job.confidence >= 80
      ? "text-success"
      : job.confidence >= 60
      ? "text-warning"
      : "text-destructive";

  return (
    <button
      onClick={onSelect}
      className={`
        w-full text-left p-4 rounded-xl border transition-all duration-300
        ${
          isSelected
            ? "glass-panel-active border-primary/30"
            : "glass-panel border-border/30 hover:border-border/60"
        }
      `}
    >
      <div className="flex items-start justify-between mb-2">
        <h3 className="text-sm font-semibold text-foreground leading-tight pr-2">{job.title}</h3>
        <div className={`flex items-center gap-1 shrink-0 ${confidenceColor}`}>
          <Star className="w-3 h-3 fill-current" />
          <span className="text-xs font-mono font-medium">{job.confidence}%</span>
        </div>
      </div>

      <p className="text-xs font-medium text-secondary-foreground mb-3">{job.company}</p>

      <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <MapPin className="w-3 h-3" /> {job.location}
        </span>
        <span className="flex items-center gap-1">
          <DollarSign className="w-3 h-3" /> {job.salary}
        </span>
        <span className="flex items-center gap-1">
          <ExternalLink className="w-3 h-3" /> {job.source}
        </span>
      </div>

      <div className="flex items-center gap-1.5 mt-3 pt-2.5 border-t border-border/30">
        <Clock className="w-3 h-3 text-muted-foreground/60" />
        <span className="text-[10px] text-muted-foreground/60 font-mono">{job.scrapedAt}</span>
      </div>
    </button>
  );
};

export default JobCard;
