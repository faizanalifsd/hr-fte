import { useState, useEffect } from "react";
import {
  Briefcase, FileText, Mail, CheckCircle2, X, Clock,
  AlertTriangle, XCircle, Inbox,
} from "lucide-react";
import { applicationApi, jobApi, missionApi, type ApplicationRecord, type Job, type AuditLogEntry } from "../lib/api";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Frontend display shape for an application row
interface AppRow {
  id: number;
  jobId: number;
  title: string;
  company: string;
  matchPercent: number;
  hrEmail: string;
  outcome: string;
  date: string;
  gmailId: string;
}

const statusBadge = (outcome: string) => {
  const styles: Record<string, string> = {
    Sent:     "bg-success/10 text-success border border-success/20",
    Failed:   "bg-destructive/10 text-destructive border border-destructive/20",
    Pending:  "bg-muted text-muted-foreground",
    Rejected: "bg-destructive/10 text-destructive border border-destructive/20",
  };
  return styles[outcome] || styles.Pending;
};

const statusIcon = (outcome: string) => {
  switch (outcome) {
    case "Sent":     return <CheckCircle2 className="w-3 h-3" />;
    case "Failed":   return <XCircle className="w-3 h-3" />;
    case "Rejected": return <AlertTriangle className="w-3 h-3" />;
    default:         return <Clock className="w-3 h-3" />;
  }
};

interface LogEntry {
  time: string;
  agent: string;
  action: string;
}

interface Props {
  missionId?: number;
}

const EvidenceTab = ({ missionId }: Props) => {
  const [selectedRow, setSelectedRow] = useState<AppRow | null>(null);
  const [rows, setRows] = useState<AppRow[]>([]);
  const [execLog, setExecLog] = useState<LogEntry[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!missionId) {
      setRows([]);
      setExecLog([]);
      setJobs([]);
      return;
    }

    const fetchData = async () => {
      setLoading(true);
      try {
        // Fetch in parallel: applications, mission jobs, audit log
        const [apps, missionJobs, auditLogs] = await Promise.allSettled([
          applicationApi.list(),
          jobApi.listByMission(missionId),
          missionApi.auditLog(missionId, 10),
        ]);

        const appsData: ApplicationRecord[] =
          apps.status === "fulfilled" ? apps.value : [];
        const jobsData: Job[] =
          missionJobs.status === "fulfilled" ? missionJobs.value : [];
        const logsData: AuditLogEntry[] =
          auditLogs.status === "fulfilled" ? auditLogs.value : [];

        setJobs(jobsData);

        // Build a quick lookup: job_id → Job
        const jobMap = new Map<number, Job>(jobsData.map((j) => [j.id, j]));

        // Map applications → display rows
        const mapped: AppRow[] = appsData.map((a) => {
          const job = jobMap.get(a.job_id);
          return {
            id:           a.id,
            jobId:        a.job_id,
            title:        job?.role ?? "—",
            company:      a.company,
            matchPercent: job?.match_score ?? 0,
            hrEmail:      a.hr_email,
            outcome:      a.outcome,
            date:         new Date(a.sent_at).toLocaleDateString(),
            gmailId:      a.gmail_message_id ?? "—",
          };
        });
        setRows(mapped);

        // Build execution log from audit entries
        const logMapped: LogEntry[] = logsData.map((l) => ({
          time:   new Date(l.timestamp).toLocaleTimeString("en", { hour: "2-digit", minute: "2-digit" }),
          agent:  l.agent_name,
          action: l.output_summary || l.action_type,
        }));
        setExecLog(logMapped);
      } catch { /* silent */ } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [missionId]);

  // Summary stats from real data only
  const jobsFetched  = jobs.length;
  const cvsGenerated = jobs.filter((j) => j.match_score !== null && j.match_score !== undefined).length;
  const appsSent     = rows.filter((r) => r.outcome === "Sent").length;
  const responses    = rows.filter((r) => r.outcome === "Rejected" || r.outcome === "Interview").length;

  // Empty state when no mission
  if (!missionId) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-3 text-center px-8">
        <Inbox className="w-10 h-10 text-muted-foreground/30" />
        <p className="text-sm font-medium text-muted-foreground">No evidence yet</p>
        <p className="text-[11px] text-muted-foreground/60 max-w-xs">
          Start a mission to track applications, CV versions, and audit records here.
        </p>
      </div>
    );
  }

  return (
    <div className="h-full flex gap-4">
      <div className="flex-1 flex flex-col gap-4 min-h-0">
        {/* Summary Cards */}
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: "Jobs Fetched",       value: jobsFetched,  icon: Briefcase    },
            { label: "CVs Generated",      value: cvsGenerated, icon: FileText     },
            { label: "Applications Sent",  value: appsSent,     icon: Mail         },
            { label: "Responses",          value: responses,    icon: CheckCircle2 },
          ].map((card) => (
            <div key={card.label} className="glass-panel p-4">
              <div className="flex items-center gap-2 mb-2">
                <card.icon className="w-4 h-4 text-primary" />
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                  {card.label}
                </span>
              </div>
              <p className="text-2xl font-bold text-foreground">{card.value}</p>
            </div>
          ))}
        </div>

        {/* Application Table */}
        <div className="glass-panel flex-1 flex flex-col min-h-0">
          <div className="px-4 py-3 border-b border-border/30">
            <h3 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-semibold">
              Application Tracker
            </h3>
          </div>

          {rows.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center p-8">
              <Mail className="w-8 h-8 text-muted-foreground/20" />
              <p className="text-[11px] text-muted-foreground/60">
                {loading ? "Loading applications…" : "No applications sent yet"}
              </p>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto scrollbar-thin">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border/20">
                    {["Job Title","Company","Match","HR Email","Status","Date"].map((h) => (
                      <th key={h} className="text-left px-4 py-2 text-[9px] uppercase tracking-wider text-muted-foreground font-semibold">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.id}
                      onClick={() => setSelectedRow(row)}
                      className="border-b border-border/10 hover:bg-secondary/30 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-2.5 font-medium text-foreground">{row.title}</td>
                      <td className="px-4 py-2.5 text-muted-foreground">{row.company}</td>
                      <td className="px-4 py-2.5">
                        <span className={`font-mono font-semibold ${
                          row.matchPercent >= 80 ? "text-success"
                          : row.matchPercent >= 60 ? "text-warning"
                          : "text-muted-foreground"
                        }`}>
                          {row.matchPercent ? `${Math.round(row.matchPercent)}%` : "—"}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground font-mono text-[10px] truncate max-w-[120px]">
                        {row.hrEmail}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-semibold ${statusBadge(row.outcome)}`}>
                          {statusIcon(row.outcome)} {row.outcome}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground font-mono">{row.date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Execution Log */}
        <div className="glass-panel p-4">
          <h3 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-semibold mb-3">
            Execution Log
          </h3>
          {execLog.length === 0 ? (
            <p className="text-[11px] text-muted-foreground/50 italic">No log entries yet</p>
          ) : (
            <div className="space-y-2">
              {execLog.map((log, i) => (
                <div key={i} className="flex items-start gap-3 text-[11px]">
                  <span className="font-mono text-muted-foreground/60 shrink-0">{log.time}</span>
                  <div className="w-1.5 h-1.5 rounded-full bg-primary/40 mt-1.5 shrink-0" />
                  <span className="text-foreground">
                    <span className="font-semibold text-primary">{log.agent}</span>
                    {" — "}{log.action}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Side Detail Panel */}
      {selectedRow && (
        <div className="w-72 glass-panel p-4 flex flex-col animate-fade-in">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-xs font-semibold text-foreground truncate">{selectedRow.title}</h4>
            <button onClick={() => setSelectedRow(null)} className="text-muted-foreground hover:text-foreground ml-2">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="space-y-4 text-[11px]">
            <div>
              <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold">Company</span>
              <p className="text-foreground mt-1">{selectedRow.company}</p>
            </div>
            <div>
              <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold">HR Email</span>
              <p className="text-foreground font-mono mt-1 break-all">{selectedRow.hrEmail}</p>
            </div>
            <div>
              <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold">Gmail Message ID</span>
              <p className="text-secondary-foreground font-mono mt-1 break-all">{selectedRow.gmailId}</p>
            </div>
            <div>
              <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold">Match Score</span>
              <p className="text-foreground mt-1">{selectedRow.matchPercent ? `${Math.round(selectedRow.matchPercent)}%` : "—"}</p>
            </div>
            <div>
              <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold">Status</span>
              <p className="text-foreground mt-1">{selectedRow.outcome}</p>
            </div>
            <div>
              <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold">Sent At</span>
              <p className="text-foreground font-mono mt-1">{selectedRow.date}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EvidenceTab;
