import { useState, useCallback, useEffect } from "react";
import { missionApi, systemApi, type Mission } from "../lib/api";

export interface PipelineStep {
  id: string;
  label: string;
  status: "pending" | "running" | "completed" | "failed";
  time?: string;
  detail?: string;
}

const initialSteps: PipelineStep[] = [
  { id: "cv-upload", label: "CV Uploaded", status: "pending" },
  { id: "parsing", label: "Parsing", status: "pending" },
  { id: "scraping", label: "Jobs Scraped", status: "pending", detail: "0" },
  { id: "matching", label: "Matching Done", status: "pending" },
  { id: "emails", label: "Emails Generated", status: "pending" },
  { id: "applications", label: "Applications Sent", status: "pending" },
  { id: "evidence", label: "Evidence Stored", status: "pending" },
];

export const useAutonomous = () => {
  const [autonomous, setAutonomous] = useState(false);
  const [steps, setSteps] = useState<PipelineStep[]>(initialSteps);
  const [apiMode, setApiMode] = useState<"connected" | "simulated">("simulated");
  const [currentMission, setCurrentMission] = useState<Mission | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // On startup: restore the latest mission from the backend so page refreshes
  // don't lose all state. Pick the most recent mission regardless of status.
  useEffect(() => {
    const restore = async () => {
      try {
        const missions = await missionApi.list();
        if (missions.length === 0) return;
        // Sort by ID desc — highest ID = most recently created
        const latest = missions.sort((a, b) => b.id - a.id)[0];
        setCurrentMission(latest);
        setAutonomous(true);
        setApiMode("connected");
      } catch {
        // backend not reachable — stay in simulated mode
      }
    };
    restore();
  }, []);

  const updateStep = (id: string, update: Partial<PipelineStep>) => {
    setSteps((prev) =>
      prev.map((s) => (s.id === id ? { ...s, ...update } : s))
    );
  };

  const markStepRunning = (id: string) =>
    updateStep(id, { status: "running" });

  const markStepCompleted = (id: string, detail?: string) =>
    updateStep(id, {
      status: "completed",
      time: new Date().toLocaleTimeString(),
      ...(detail !== undefined ? { detail } : {}),
    });

  const markStepFailed = (id: string) =>
    updateStep(id, { status: "failed", time: new Date().toLocaleTimeString() });

  const startMission = useCallback(
    async (missionInput: string, cvText: string) => {
      setIsLoading(true);
      setError(null);
      setSteps(initialSteps);

      try {
        // Check backend connectivity
        await systemApi.health();
        setApiMode("connected");
        setAutonomous(true);

        // Phase 1: Create mission
        markStepRunning("cv-upload");
        const mission = await missionApi.create(missionInput);
        setCurrentMission(mission);
        markStepCompleted("cv-upload");

        // Phase 2-12: Kick off background workflow (returns 202 immediately)
        // The backend runs all phases in a background thread.
        // Progress is tracked via polling GET /api/missions/{id} and /audit.
        markStepRunning("parsing");
        await missionApi.execute(mission.id, cvText);

        // Mark all pipeline steps as running — real status comes from audit log polling
        markStepCompleted("cv-upload");
        markStepRunning("parsing");
        updateStep("scraping",      { status: "running" });
        updateStep("matching",      { status: "running" });
        updateStep("emails",        { status: "running" });
        updateStep("applications",  { status: "pending" });
        updateStep("evidence",      { status: "pending" });

        setIsLoading(false);
        return mission;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Unknown error";
        setError(msg);
        setApiMode("simulated");

        // Mark current running step as failed
        setSteps((prev) =>
          prev.map((s) =>
            s.status === "running" ? { ...s, status: "failed" } : s
          )
        );

        setIsLoading(false);
        throw err;
      }
    },
    []
  );

  const toggleAutonomous = useCallback(() => {
    setAutonomous((prev) => {
      if (prev) {
        // Stop: reset
        setSteps(initialSteps);
        setApiMode("simulated");
        setCurrentMission(null);
        setError(null);
      }
      return !prev;
    });
  }, []);

  const markApplicationsSent = useCallback((count: number) => {
    markStepCompleted("applications", String(count));
    markStepCompleted("evidence");
  }, []);

  return {
    autonomous,
    toggleAutonomous,
    startMission,
    markApplicationsSent,
    steps,
    apiMode,
    currentMission,
    isLoading,
    error,
  };
};
