import { useState, useEffect } from "react";
import {
  Brain,
  FileText,
  GitCompare,
  UserSearch,
  ShieldCheck,
  PenTool,
  Search,
  Send,
  Clock,
  ChevronDown,
  ChevronUp,
  Activity,
} from "lucide-react";
import { missionApi, type AuditLogEntry } from "../lib/api";

const agentDefinitions = [
  { id: "cv-agent",          name: "CV Agent",           icon: FileText   },
  { id: "scraper-agent",     name: "Scraper Agent",      icon: Search     },
  { id: "matcher-agent",     name: "Matcher Agent",      icon: GitCompare },
  { id: "email-agent",       name: "Email Agent",        icon: PenTool    },
  { id: "optimization-agent",name: "Optimization Agent", icon: Brain      },
  { id: "evidence-agent",    name: "Evidence Agent",     icon: ShieldCheck},
  { id: "application-agent", name: "Application Agent",  icon: Send       },
];

// Map backend agent_name → frontend agent id
const agentNameMap: Record<string, string> = {
  cv_parser:         "cv-agent",
  job_scraper:       "scraper-agent",
  job_matcher:       "matcher-agent",
  email_generator:   "email-agent",
  cv_optimizer:      "optimization-agent",
  evidence_agent:    "evidence-agent",
  application_agent: "application-agent",
  email_sender:      "application-agent",
};

const statusStyles: Record<string, { dot: string; label: string }> = {
  idle:      { dot: "bg-muted-foreground",              label: "Idle"   },
  running:   { dot: "bg-success animate-pulse",         label: "Running"},
  completed: { dot: "bg-primary",                       label: "Done"   },
  failed:    { dot: "bg-destructive",                   label: "Failed" },
};

interface AuditEntry {
  time: string;
  agent: string;
  action: string;
  status: string;
  summary: string;
}

interface Props {
  missionId?: number;
}

const AIControlPanel = ({ missionId }: Props) => {
  const [expandedHistory, setExpandedHistory] = useState<number | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditEntry[]>([]);
  const [agentStatuses, setAgentStatuses] = useState<
    Record<string, { status: string; task: string; lastExec: string }>
  >({});

  useEffect(() => {
    if (!missionId) {
      setAuditLogs([]);
      setAgentStatuses({});
      return;
    }

    const fetchLogs = async () => {
      try {
        const logs: AuditLogEntry[] = await missionApi.auditLog(missionId);

        const entries: AuditEntry[] = logs.map((l) => {
          const rawStatus = (l.status || "").toLowerCase();
          const mappedStatus =
            rawStatus === "success" ? "completed" :
            rawStatus === "running" ? "running"   :
            "failed";
          return {
            time:    new Date(l.timestamp).toLocaleTimeString(),
            agent:   l.agent_name,
            action:  l.output_summary || l.action_type,
            status:  mappedStatus,
            summary: l.output_summary || "",
          };
        });

        setAuditLogs([...entries].reverse());

        // Derive per-agent status from latest log per agent.
        // logs[] is newest-first (DESC from API) — only store the FIRST hit per
        // agent so the newest log entry wins and older entries don't overwrite it.
        const statuses: Record<string, { status: string; task: string; lastExec: string }> = {};
        logs.forEach((l) => {
          const agentId = agentNameMap[l.agent_name] || l.agent_name;
          if (statuses[agentId]) return; // already captured the newest entry
          const rawStatus = (l.status || "").toLowerCase();
          const mappedStatus =
            rawStatus === "success"  ? "completed" :
            rawStatus === "running"  ? "running"   :
            rawStatus === "failed"   ? "failed"    :
            "idle";
          statuses[agentId] = {
            status:   mappedStatus,
            task:     l.output_summary || l.action_type || "—",
            lastExec: new Date(l.timestamp).toLocaleTimeString(),
          };
        });
        setAgentStatuses(statuses);
      } catch {
        // silently ignore — backend may not be ready yet
      }
    };

    fetchLogs();
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, [missionId]);

  return (
    <div className="h-full flex flex-col gap-4 overflow-hidden">
      {/* Agent Departments */}
      <div className="glass-panel p-4">
        <h3 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-semibold mb-3">
          AI Departments
        </h3>
        <div className="space-y-0.5">
          {agentDefinitions.map((agent) => {
            const info = agentStatuses[agent.id] || { status: "idle", task: "Standby", lastExec: "—" };
            const st = statusStyles[info.status] || statusStyles.idle;
            return (
              <button
                key={agent.id}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-secondary/50 transition-colors text-left group"
              >
                <agent.icon className="w-3.5 h-3.5 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="text-[11px] text-foreground block truncate">{agent.name}</span>
                  <span className="text-[9px] text-muted-foreground/50 font-mono block truncate">{info.task}</span>
                </div>
                <div className="flex flex-col items-end gap-0.5 shrink-0">
                  <div className="flex items-center gap-1">
                    <span className="text-[8px] text-muted-foreground/50 font-mono">{st.label}</span>
                    <div className={`w-1.5 h-1.5 rounded-full ${st.dot}`} />
                  </div>
                  <span className="text-[8px] text-muted-foreground/30 font-mono">{info.lastExec}</span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Divider */}
      <div className="h-px bg-border/40" />

      {/* Execution History */}
      <div className="glass-panel p-4 flex-1 min-h-0 flex flex-col">
        <h3 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-semibold mb-3">
          Execution History
        </h3>

        {auditLogs.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center">
            <Activity className="w-6 h-6 text-muted-foreground/20" />
            <p className="text-[11px] text-muted-foreground/50">
              {missionId ? "Waiting for activity…" : "No active mission"}
            </p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto scrollbar-thin space-y-1 pr-1">
            {auditLogs.map((entry, i) => (
              <div key={i} className="group">
                <button
                  onClick={() => setExpandedHistory(expandedHistory === i ? null : i)}
                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-secondary/30 transition-colors"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Clock className="w-2.5 h-2.5 text-muted-foreground/50 shrink-0" />
                    <span className="text-[9px] font-mono text-muted-foreground/60">{entry.time}</span>
                    <span className="text-[9px] font-medium text-primary/80 truncate">{entry.agent}</span>
                    <div className="ml-auto shrink-0">
                      {expandedHistory === i
                        ? <ChevronUp className="w-3 h-3 text-muted-foreground/40" />
                        : <ChevronDown className="w-3 h-3 text-muted-foreground/40" />
                      }
                    </div>
                  </div>
                  <p className="text-[11px] text-foreground/80 pl-[18px]">{entry.action}</p>
                  <div className="pl-[18px] mt-1">
                    <span
                      className={`text-[8px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded-full border ${
                        entry.status === "completed"
                          ? "bg-success/10 text-success border-success/20"
                          : entry.status === "running"
                          ? "bg-primary/10 text-primary border-primary/20"
                          : "bg-destructive/10 text-destructive border-destructive/20"
                      }`}
                    >
                      {entry.status}
                    </span>
                  </div>
                </button>
                {expandedHistory === i && (
                  <div className="px-3 pb-2 pl-[30px] animate-fade-in">
                    <p className="text-[10px] text-muted-foreground leading-relaxed">{entry.summary}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default AIControlPanel;
