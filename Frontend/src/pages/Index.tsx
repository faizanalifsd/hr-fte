import { useState, useEffect, useRef } from "react";
import Header from "../components/Header";
import TabNavigation from "../components/TabNavigation";
import AIControlPanel from "../components/AIControlPanel";
import JobFeed from "../components/JobFeed";
import PlanTab from "../components/PlanTab";
import GraphTab from "../components/GraphTab";
import EvidenceTab from "../components/EvidenceTab";
import AgentMonitor from "../components/AgentMonitor";
import ProgressTracker from "../components/ProgressTracker";
import MissionLaunchDialog from "../components/MissionLaunchDialog";
import HITLApprovalPanel from "../components/HITLApprovalPanel";
import CVVersionTab from "../components/CVVersionTab";
import { useTheme } from "../hooks/useTheme";
import { useAutonomous } from "../hooks/useAutonomous";
import { jobApi, type Job } from "../lib/api";

// JobFeed expects this shape
interface FeedJob {
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

const mapJobToFeed = (j: Job): FeedJob => ({
  id:            String(j.id),
  title:         j.role,
  company:       j.company,
  location:      j.location || "Remote",
  salary:        "—",
  source:        j.source_portal || "Apify",
  scrapedAt:     new Date(j.created_at).toLocaleString(),
  confidence:    Math.round(j.match_score ?? 0),
  description:   j.description,
  hrEmail:       j.hr_email || "—",
  hiringManager: j.hr_name || "—",
  directLink:    j.apply_link || "#",
  rawData:       { job_id: j.id, status: j.status, mission_id: j.mission_id },
  sourceType:    "API",
  fetchTime:     j.created_at,
});

const Index = () => {
  const [activeTab, setActiveTab]       = useState("plan");
  const { theme, toggleTheme }          = useTheme();
  const {
    autonomous,
    toggleAutonomous,
    startMission,
    markApplicationsSent,
    steps,
    apiMode,
    currentMission,
    isLoading,
    error,
  } = useAutonomous();

  const [feedJobs, setFeedJobs]         = useState<FeedJob[]>([]);
  const [jobsLoading, setJobsLoading]   = useState(false);
  const [showLaunchDialog, setShowLaunchDialog] = useState(false);
  const [showHITL, setShowHITL]         = useState(false);
  const pollRef                          = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll jobs every 5 s while mission is active
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);

    if (!currentMission) {
      setFeedJobs([]);
      return;
    }

    const fetchJobs = async () => {
      setJobsLoading(true);
      try {
        const jobs = await jobApi.listByMission(currentMission.id);
        setFeedJobs(jobs.map(mapJobToFeed));
      } catch { /* silent */ } finally {
        setJobsLoading(false);
      }
    };

    fetchJobs();
    pollRef.current = setInterval(fetchJobs, 5000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [currentMission]);

  const handleToggleAutonomous = () => {
    if (!autonomous) {
      setShowLaunchDialog(true);
    } else {
      toggleAutonomous();
      setFeedJobs([]);
      setShowHITL(false);
    }
  };

  const handleLaunch = async (missionInput: string, cvText: string) => {
    setActiveTab("job");
    setShowLaunchDialog(false);
    await startMission(missionInput, cvText);
    setShowHITL(true);
  };

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Header
        status={autonomous ? "running" : "idle"}
        autonomous={autonomous}
        onToggleAutonomous={handleToggleAutonomous}
        apiMode={apiMode}
        theme={theme}
        onToggleTheme={toggleTheme}
      />
      <ProgressTracker steps={steps} visible={autonomous} />
      <TabNavigation activeTab={activeTab} onTabChange={setActiveTab} />

      <div
        className="flex-1 px-6 pb-6 grid grid-cols-12 gap-4 min-h-0"
        style={{ height: autonomous ? "calc(100vh - 175px)" : "calc(100vh - 130px)" }}
      >
        {/* Left Panel – AI Control */}
        <div className="col-span-3 overflow-hidden">
          <AIControlPanel missionId={currentMission?.id} />
        </div>

        {/* Center Panel – Dynamic Content */}
        <div className="col-span-6 overflow-hidden">
          {activeTab === "job" && (
            <JobFeed
              jobs={feedJobs}
              isLoading={jobsLoading}
              missionActive={autonomous}
            />
          )}
          {activeTab === "cv"        && (
            <CVVersionTab missionId={currentMission?.id} />
          )}
          {activeTab === "plan"     && (
            <PlanTab
              jobs={feedJobs}
              onLaunch={handleLaunch}
              isLoading={isLoading}
            />
          )}
          {activeTab === "graph"    && <GraphTab steps={steps} autonomous={autonomous} />}
          {activeTab === "evidence" && <EvidenceTab missionId={currentMission?.id} />}
        </div>

        {/* Right Panel – HITL + Agent Monitor */}
        <div className="col-span-3 flex flex-col gap-4">
          {/* Always show HITL when a mission is active — panel handles its own empty state */}
          {autonomous && (
            <HITLApprovalPanel onApprovalComplete={markApplicationsSent} />
          )}
          <AgentMonitor missionId={currentMission?.id} />
        </div>
      </div>

      {/* Mission Launch Dialog */}
      <MissionLaunchDialog
        open={showLaunchDialog}
        onClose={() => setShowLaunchDialog(false)}
        onLaunch={handleLaunch}
        isLoading={isLoading}
        error={error}
      />
    </div>
  );
};

export default Index;
