import { Activity, Cpu, Zap, Clock, Hash, RefreshCw, AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";
import { missionApi, type AuditLogEntry } from "../lib/api";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface Props {
  missionId?: number;
}

interface MissionData {
  target_role: string;
  target_count: number;
  progress_count: number;
  status: string;
}

const AgentMonitor = ({ missionId }: Props) => {
  const [logLines, setLogLines] = useState<string[]>([]);
  const [progress, setProgress] = useState(0);
  const [runtime, setRuntime] = useState(0);
  const [mission, setMission] = useState<MissionData | null>(null);
  const [currentPhase, setCurrentPhase] = useState("Idle");
  const [isStuck, setIsStuck] = useState(false);
  const [rerunLoading, setRerunLoading] = useState(false);
  const [lastLogTime, setLastLogTime] = useState<Date | null>(null);

  // Tick runtime counter
  useEffect(() => {
    const timer = setInterval(() => setRuntime((r) => r + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  // Poll mission + audit log when active
  useEffect(() => {
    if (!missionId) {
      setMission(null);
      setProgress(0);
      setCurrentPhase("Idle");
      setLogLines([]);
      return;
    }

    const fetchAll = async () => {
      // Fetch mission progress
      try {
        const res = await fetch(`${API_BASE}/api/missions/${missionId}`);
        if (res.ok) {
          const data: MissionData = await res.json();
          setMission(data);
          const pct =
            data.target_count > 0
              ? Math.round((data.progress_count / data.target_count) * 100)
              : 0;
          setProgress(pct);
          setCurrentPhase(data.status);
        }
      } catch { /* silent */ }

      // Fetch audit log for live log display + current phase
      try {
        const logs: AuditLogEntry[] = await missionApi.auditLog(missionId, 20);

        // Derive current active phase from the latest log entry
        if (logs.length > 0) {
          const latest = logs[0]; // newest first
          const summary = latest.output_summary || latest.action_type;
          // Extract phase label: "Phase 5: Job Matching..." → "Phase 5: Job Matching"
          const phaseMatch = summary.match(/Phase\s+[\d\-]+:?\s+[^—]*/i);
          if (phaseMatch) {
            setCurrentPhase(phaseMatch[0].trim().slice(0, 30));
          } else {
            setCurrentPhase(`${latest.agent_name} (${latest.status})`);
          }
        }

        const lines = logs
          .slice(0, 8)
          .reverse()
          .map(
            (l) =>
              `[${new Date(l.timestamp).toLocaleTimeString()}] ${l.agent_name}: ${
                l.output_summary || l.action_type
              }`
          );
        setLogLines(lines);

        // Detect stuck: last log older than 3 minutes AND no sign of progress past CV parsing.
        // Not stuck if: cv_parser succeeded OR any later-phase agent has logged (meaning CV
        // was already parsed and the workflow is running/waiting at a later stage).
        if (logs.length > 0) {
          const newest = new Date(logs[0].timestamp);
          setLastLogTime(newest);
          const ageMs = Date.now() - newest.getTime();
          const laterPhaseAgents = ["job_scraper", "job_matcher", "cv_optimizer", "email_generator", "email_sender"];
          const hasProgress =
            logs.some((l) => l.agent_name === "cv_parser" && l.status === "Success") ||
            logs.some((l) => laterPhaseAgents.includes(l.agent_name));
          setIsStuck(ageMs > 3 * 60 * 1000 && !hasProgress);
        }
      } catch { /* silent */ }
    };

    fetchAll();
    const interval = setInterval(fetchAll, 5000);
    return () => clearInterval(interval);
  }, [missionId]);

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
  };

  const handleRerun = async () => {
    if (!missionId) return;
    setRerunLoading(true);
    try {
      // Fetch the stored master CV from the backend — no need to re-paste
      const cvRes = await fetch(`${API_BASE}/api/cvversions/mission/${missionId}`);
      if (!cvRes.ok) throw new Error("Failed to fetch stored CV");
      const cvVersions: { is_master: number; content_markdown: string }[] = await cvRes.json();
      const master = cvVersions.find((v) => v.is_master) || cvVersions[0];
      if (!master?.content_markdown?.trim()) {
        alert("No stored CV found. Please re-launch the workflow from the Mission panel.");
        setRerunLoading(false);
        return;
      }
      await missionApi.execute(missionId, master.content_markdown.trim());
      setIsStuck(false);
    } catch (e) {
      alert("Re-run failed: " + (e instanceof Error ? e.message : String(e)));
    } finally {
      setRerunLoading(false);
    }
  };

  return (
    <div className="glass-panel p-4 space-y-4 h-full flex flex-col">
      <div className="flex items-center gap-2">
        <Activity className="w-3.5 h-3.5 text-primary" />
        <h3 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-semibold">
          Agent Monitor
        </h3>
        <div
          className={`ml-auto w-1.5 h-1.5 rounded-full ${
            missionId ? "bg-success animate-pulse" : "bg-muted-foreground/40"
          }`}
        />
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-background/50 rounded-lg p-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <Cpu className="w-2.5 h-2.5 text-muted-foreground/60" />
            <span className="text-[8px] uppercase tracking-wider text-muted-foreground/60 font-medium">Phase</span>
          </div>
          <p className="text-[11px] text-foreground font-medium truncate">{currentPhase}</p>
        </div>
        <div className="bg-background/50 rounded-lg p-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <Zap className="w-2.5 h-2.5 text-muted-foreground/60" />
            <span className="text-[8px] uppercase tracking-wider text-muted-foreground/60 font-medium">Mission</span>
          </div>
          <p className="text-[11px] text-primary font-medium truncate">
            {mission ? mission.target_role : "—"}
          </p>
        </div>
        <div className="bg-background/50 rounded-lg p-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <Hash className="w-2.5 h-2.5 text-muted-foreground/60" />
            <span className="text-[8px] uppercase tracking-wider text-muted-foreground/60 font-medium">Progress</span>
          </div>
          <p className="text-[11px] text-foreground font-mono font-medium">
            {mission ? `${mission.progress_count}/${mission.target_count}` : "—/—"}
          </p>
        </div>
        <div className="bg-background/50 rounded-lg p-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <Clock className="w-2.5 h-2.5 text-muted-foreground/60" />
            <span className="text-[8px] uppercase tracking-wider text-muted-foreground/60 font-medium">Runtime</span>
          </div>
          <p className="text-[11px] text-foreground font-mono font-medium">{formatTime(runtime)}</p>
        </div>
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <p className="text-[10px] text-muted-foreground/70">Progress</p>
          <span className="text-[10px] font-mono text-primary">{progress}%</span>
        </div>
        <div className="h-1 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all duration-700 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Stuck-mission banner */}
      {isStuck && missionId && (
        <div className="rounded-lg border border-warning/30 bg-warning/5 px-3 py-2 flex items-start gap-2">
          <AlertTriangle className="w-3.5 h-3.5 text-warning shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-[10px] text-warning font-semibold">Workflow stuck</p>
            <p className="text-[9px] text-muted-foreground mt-0.5">
              CV parsing stalled — backend may have restarted. Re-run to continue.
            </p>
          </div>
          <button
            onClick={handleRerun}
            disabled={rerunLoading}
            className="shrink-0 flex items-center gap-1 px-2 py-1 rounded bg-warning/10 border border-warning/30 text-warning text-[9px] font-semibold hover:bg-warning/20 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-2.5 h-2.5 ${rerunLoading ? "animate-spin" : ""}`} />
            {rerunLoading ? "Starting…" : "Re-run"}
          </button>
        </div>
      )}

      {/* Live Log */}
      <div className="flex-1 min-h-0">
        <p className="text-[10px] text-muted-foreground/70 mb-2">Live Log</p>
        <div className="bg-background/50 rounded-lg p-3 h-[calc(100%-20px)] overflow-y-auto scrollbar-thin space-y-1">
          {logLines.length === 0 ? (
            <p className="text-[10px] text-muted-foreground/40 italic">
              {missionId ? "Waiting for agent activity…" : "No active mission"}
            </p>
          ) : (
            logLines.map((line, i) => (
              <p key={i} className="log-line animate-fade-in" style={{ animationDelay: `${i * 30}ms` }}>
                {line}
              </p>
            ))
          )}
          {missionId && (
            <span className="inline-block w-1.5 h-3.5 bg-primary/60 animate-pulse ml-2" />
          )}
        </div>
      </div>
    </div>
  );
};

export default AgentMonitor;
