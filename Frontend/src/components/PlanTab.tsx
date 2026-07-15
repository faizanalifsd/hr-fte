import { useState, useCallback, useRef } from "react";
import {
  Upload, FileText, MapPin, Briefcase, ToggleLeft, ToggleRight,
  ChevronDown, Bold, Heading1, Heading2, List, Highlighter,
  RotateCcw, Download, CheckCheck, Send, RefreshCw, Mail as MailIcon,
  Lock, Copy, Star, X, AlertTriangle, Loader2,
} from "lucide-react";
import { cvVersionApi } from "../lib/api";
type PlanPhase = "init" | "editor";
type CVVersion = "auto" | "edited" | "locked";

interface JobCVState {
  editedCV: string;
  chatHistory: { role: "user" | "ai"; text: string }[];
  emailSubject: string;
  emailBody: string;
  coverLetter: string;
  hrEmail: string;
  version: CVVersion;
}

const experienceLevels = ["Entry Level", "Mid Level", "Senior", "Staff", "Principal", "Director+"];

interface PlanJob {
  id: string;
  title: string;
  company: string;
  confidence: number;
  hrEmail: string;
}

interface PlanTabProps {
  jobs?: PlanJob[];
  onLaunch?: (missionInput: string, cvText: string) => Promise<void>;
  isLoading?: boolean;
}

const PlanTab = ({ jobs = [], onLaunch, isLoading = false }: PlanTabProps) => {
  const [phase, setPhase] = useState<PlanPhase>("init");
  const [desiredRole, setDesiredRole] = useState("");
  const [location, setLocation] = useState("");
  const [remote, setRemote] = useState(false);
  const [experience, setExperience] = useState("Senior");
  const [fileName, setFileName] = useState<string | null>(null);
  const [cvContent, setCvContent] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [launchError, setLaunchError] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [selectedJobCV, setSelectedJobCV] = useState<string | null>(null);
  const [showBaseCV, setShowBaseCV] = useState(false);

  // Per-job state
  const [jobStates, setJobStates] = useState<Record<string, JobCVState>>({});

  // Base CV chat/email state
  const [baseChatHistory, setBaseChatHistory] = useState<{ role: "user" | "ai"; text: string }[]>([
    { role: "ai", text: "I've analyzed your master resume. Ask me anything about optimizing it for specific roles." },
  ]);
  const [baseChatInput, setBaseChatInput] = useState("");
  const [baseEmailSubject, setBaseEmailSubject] = useState("Application: [Role] — [Your Name]");
  const [baseEmailBody, setBaseEmailBody] = useState("Dear Hiring Team,\n\nI am writing to express my interest…\n\nBest regards,\n[Your Name]");
  const [baseCoverLetter, setBaseCoverLetter] = useState("I am excited about the opportunity to contribute my skills…");

  const top10Jobs = jobs.slice(0, 10);

  const getJobState = useCallback((jobId: string): JobCVState => {
    if (jobStates[jobId]) return jobStates[jobId];
    const job = top10Jobs.find((j) => j.id === jobId);
    return {
      editedCV: sampleAIResume.replace("Anthropic", job?.company || ""),
      chatHistory: [
        { role: "ai", text: `I've tailored your resume for the ${job?.title} role at ${job?.company}. Key changes are marked with [MODIFIED].` },
      ],
      emailSubject: `Application: ${job?.title} — [Your Name]`,
      emailBody: `Dear Hiring Team,\n\nI am writing to express my interest in the ${job?.title} position at ${job?.company}.\n\nI have attached my tailored resume for your review.\n\nBest regards,\n[Your Name]`,
      coverLetter: `I am excited about ${job?.company}'s mission. My background aligns closely with the responsibilities outlined in this role…`,
      hrEmail: job?.hrEmail || "",
      version: "auto",
    };
  }, [jobStates, top10Jobs]);

  const updateJobState = (jobId: string, updates: Partial<JobCVState>) => {
    setJobStates((prev) => ({
      ...prev,
      [jobId]: { ...getJobState(jobId), ...updates },
    }));
  };

  const processFile = async (file: File) => {
    setFileName(file.name);
    setExtractError(null);

    if (file.name.toLowerCase().endsWith(".pdf")) {
      setExtracting(true);
      try {
        const { text } = await cvVersionApi.extractPdf(file);
        setCvContent(text);
      } catch (err) {
        setCvContent(null);
        setExtractError(err instanceof Error ? err.message : "Failed to extract PDF text");
      } finally {
        setExtracting(false);
      }
      return;
    }

    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result;
      if (typeof text === "string") setCvContent(text);
    };
    reader.readAsText(file);
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) processFile(file);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  };

  const handleActivatePlanning = async () => {
    if (!cvContent?.trim() || !desiredRole.trim() || !onLaunch) return;
    setLaunchError(null);
    const loc = remote ? "Remote" : (location.trim() || "Pakistan");
    const missionInput = `Find me ${experience} ${desiredRole.trim()} jobs in ${loc}`;
    try {
      await onLaunch(missionInput, cvContent);
      setPhase("editor");
    } catch (err) {
      setLaunchError(err instanceof Error ? err.message : "Launch failed");
    }
  };

  const handleSendChat = (jobId: string | null) => {
    if (jobId === null) {
      if (!baseChatInput.trim()) return;
      setBaseChatHistory((prev) => [...prev, { role: "user", text: baseChatInput }]);
      setBaseChatInput("");
      setTimeout(() => {
        setBaseChatHistory((prev) => [...prev, { role: "ai", text: "I've analyzed your request. Consider emphasizing your distributed systems experience. Click 'Apply Suggestion' to update." }]);
      }, 800);
    } else {
      const state = getJobState(jobId);
      const input = (document.getElementById(`chat-input-${jobId}`) as HTMLInputElement)?.value || "";
      if (!input.trim()) return;
      updateJobState(jobId, {
        chatHistory: [...state.chatHistory, { role: "user", text: input }, { role: "ai", text: "I've analyzed your request and updated the CV accordingly. Click 'Apply Suggestion' to see changes." }],
      });
      const el = document.getElementById(`chat-input-${jobId}`) as HTMLInputElement;
      if (el) el.value = "";
    }
  };

  if (phase === "init") {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="glass-panel p-8 max-w-lg w-full space-y-6 animate-fade-in">
          <div className="text-center mb-2">
            <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto mb-3">
              <FileText className="w-5 h-5 text-primary" />
            </div>
            <h2 className="text-lg font-semibold text-foreground">Profile Initialization</h2>
            <p className="text-xs text-muted-foreground mt-1">Upload your resume and set preferences to activate planning</p>
          </div>

          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleFileDrop}
            className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors cursor-pointer ${
              dragOver ? "border-primary bg-primary/5" : "border-border/50 hover:border-border"
            }`}
          >
            <input type="file" accept=".txt,.md,.text,.pdf" className="hidden" id="cv-upload" onChange={handleFileSelect} />
            <label htmlFor="cv-upload" className="cursor-pointer">
              {extracting ? (
                <Loader2 className="w-6 h-6 text-muted-foreground mx-auto mb-2 animate-spin" />
              ) : (
                <Upload className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
              )}
              {extracting ? (
                <p className="text-sm text-muted-foreground">Extracting text from {fileName}…</p>
              ) : fileName ? (
                <p className={`text-sm font-medium ${cvContent ? "text-primary" : "text-destructive"}`}>
                  {fileName} {cvContent ? "✓" : "✗"}
                </p>
              ) : (
                <>
                  <p className="text-sm text-foreground">Drop CV here or click to upload</p>
                  <p className="text-[10px] text-muted-foreground mt-1">PDF, TXT or MD</p>
                </>
              )}
            </label>
          </div>
          {extractError && (
            <p className="text-xs text-destructive text-center">
              Couldn't extract text from that PDF: {extractError} — try a text-based export instead.
            </p>
          )}

          <div className="space-y-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-1 block">
                <Briefcase className="w-3 h-3 inline mr-1" /> Desired Role
              </label>
              <input type="text" value={desiredRole} onChange={(e) => setDesiredRole(e.target.value)} placeholder="e.g. Senior ML Engineer"
                className="w-full bg-background/50 border border-border/50 rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/40" />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-1 block">
                <MapPin className="w-3 h-3 inline mr-1" /> Preferred Location
              </label>
              <input type="text" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. San Francisco, CA"
                className="w-full bg-background/50 border border-border/50 rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/40" />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-foreground">Remote Preferred</span>
              <button onClick={() => setRemote(!remote)} className="text-primary">
                {remote ? <ToggleRight className="w-6 h-6" /> : <ToggleLeft className="w-6 h-6 text-muted-foreground" />}
              </button>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-1 block">Experience Level</label>
              <div className="relative">
                <select value={experience} onChange={(e) => setExperience(e.target.value)}
                  className="w-full appearance-none bg-background/50 border border-border/50 rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary/40">
                  {experienceLevels.map((lvl) => (<option key={lvl} value={lvl}>{lvl}</option>))}
                </select>
                <ChevronDown className="w-4 h-4 text-muted-foreground absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>
            </div>
          </div>

          {launchError && (
            <p className="text-xs text-destructive text-center">
              {launchError}
            </p>
          )}

          <button
            onClick={handleActivatePlanning}
            disabled={!cvContent?.trim() || !desiredRole.trim() || isLoading || extracting}
            className="w-full py-3 rounded-lg bg-primary text-primary-foreground font-semibold text-sm hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                Launching Mission…
              </>
            ) : (
              "Activate Planning"
            )}
          </button>

        </div>
      </div>
    );
  }

  // No jobs available — show placeholder
  if (phase === "editor" && top10Jobs.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-3 text-center px-8">
        <Briefcase className="w-10 h-10 text-muted-foreground/30" />
        <p className="text-sm font-medium text-muted-foreground">No jobs to plan yet</p>
        <p className="text-[11px] text-muted-foreground/60 max-w-xs">
          Start a mission to scrape and match real jobs, then come back here to review and tailor CVs.
        </p>
      </div>
    );
  }

  const selectedJob = selectedJobCV ? top10Jobs.find((j) => j.id === selectedJobCV) : null;
  const currentState = selectedJobCV ? getJobState(selectedJobCV) : null;

  return (
    <div className="h-full flex flex-col gap-3 overflow-hidden">
      {/* Base CV Banner */}
      <div className="glass-panel px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileText className="w-4 h-4 text-primary" />
          <div>
            <h3 className="text-xs font-semibold text-foreground">Master Resume</h3>
            <p className="text-[10px] text-muted-foreground">{fileName || "resume.pdf"} • Base CV for all optimizations</p>
          </div>
        </div>
        <button onClick={() => { setShowBaseCV(!showBaseCV); setSelectedJobCV(null); }}
          className="text-[10px] font-medium px-3 py-1.5 rounded-lg border border-border/30 text-muted-foreground hover:text-foreground hover:border-border transition-colors">
          {showBaseCV ? "Hide Base CV" : "View Base CV"}
        </button>
      </div>

      {/* Job-based CV Cards */}
      <div className="glass-panel p-3">
        <h3 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-semibold mb-2">
          Top 10 Job-Optimized CVs
        </h3>
        <div className="flex gap-2 overflow-x-auto scrollbar-thin pb-1">
          {top10Jobs.map((job, i) => {
            const isSelected = selectedJobCV === job.id;
            const version = getJobState(job.id).version;
            return (
              <button key={job.id} onClick={() => { setSelectedJobCV(isSelected ? null : job.id); setShowBaseCV(false); }}
                className={`shrink-0 text-left px-3 py-2 rounded-lg border transition-all text-[10px] min-w-[140px] ${
                  isSelected ? "border-primary/30 bg-primary/5" : "border-border/30 hover:border-border/50"
                }`}>
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="font-semibold text-foreground truncate">CV v{i + 1}</span>
                  {version === "locked" && <Lock className="w-2.5 h-2.5 text-warning" />}
                  <Star className={`w-2.5 h-2.5 ml-auto ${job.confidence >= 80 ? "text-success" : "text-muted-foreground/40"}`} />
                </div>
                <p className="text-muted-foreground truncate">{job.title}</p>
                <p className="text-muted-foreground/50 truncate">{job.company}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* CV Editor Panel for selected job */}
      {selectedJobCV && currentState && selectedJob ? (
        <div className="flex-1 flex flex-col gap-3 min-h-0 animate-fade-in">
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-semibold text-foreground">CV for {selectedJob.title}</h3>
              <span className="text-[9px] text-muted-foreground/60">Derived from: Base CV</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="relative">
                <select value={currentState.version}
                  onChange={(e) => updateJobState(selectedJobCV, { version: e.target.value as CVVersion })}
                  className="appearance-none text-[10px] bg-background/50 border border-border/30 rounded px-2 py-1 text-foreground pr-6 focus:outline-none">
                  <option value="auto">Auto Generated</option>
                  <option value="edited">User Edited</option>
                  <option value="locked">Final Locked</option>
                </select>
                <ChevronDown className="w-3 h-3 text-muted-foreground absolute right-1.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>
              <button onClick={() => setSelectedJobCV(null)} className="text-muted-foreground hover:text-foreground">
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Split: CV Editor top, Chat + Email bottom */}
          <div className="flex-1 flex flex-col gap-3 min-h-0 overflow-y-auto scrollbar-thin">
            {/* CV Editor Row */}
            <div className="grid grid-cols-2 gap-3 min-h-[240px]">
              <div className="glass-panel p-3 flex flex-col min-h-0">
                <h3 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-semibold mb-2">Original Resume</h3>
                <div className="flex-1 overflow-y-auto scrollbar-thin bg-background/50 rounded-lg p-3 text-[11px] text-secondary-foreground leading-relaxed whitespace-pre-wrap max-h-[200px]">
                  {sampleOriginalResume}
                </div>
              </div>
              <div className="glass-panel p-3 flex flex-col min-h-0">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-semibold">AI Tailored</h3>
                  <div className="flex items-center gap-0.5">
                    {[Bold, Heading1, Heading2, List, Highlighter].map((Icon, i) => (
                      <button key={i} className="p-1 rounded hover:bg-secondary/50 text-muted-foreground hover:text-foreground transition-colors">
                        <Icon className="w-3 h-3" />
                      </button>
                    ))}
                  </div>
                </div>
                <textarea value={currentState.editedCV}
                  onChange={(e) => updateJobState(selectedJobCV, { editedCV: e.target.value })}
                  className="flex-1 w-full bg-background/50 rounded-lg p-3 text-[11px] text-foreground leading-relaxed resize-none focus:outline-none focus:ring-1 focus:ring-primary/30 scrollbar-thin font-mono max-h-[200px]" />
                <div className="flex items-center gap-2 mt-2">
                  <button className="flex items-center gap-1 px-2 py-1 rounded bg-success/10 text-success border border-success/20 text-[9px] font-semibold">
                    <CheckCheck className="w-2.5 h-2.5" /> Accept
                  </button>
                  <button onClick={() => updateJobState(selectedJobCV, { editedCV: sampleOriginalResume })}
                    className="flex items-center gap-1 px-2 py-1 rounded bg-secondary text-secondary-foreground text-[9px] font-semibold">
                    <RotateCcw className="w-2.5 h-2.5" /> Revert
                  </button>
                  <button className="flex items-center gap-1 px-2 py-1 rounded bg-secondary text-secondary-foreground text-[9px] font-semibold">
                    <Copy className="w-2.5 h-2.5" /> Duplicate
                  </button>
                  <button className="flex items-center gap-1 px-2 py-1 rounded bg-primary/10 text-primary border border-primary/20 text-[9px] font-semibold ml-auto">
                    <Download className="w-2.5 h-2.5" /> PDF
                  </button>
                </div>
              </div>
            </div>

            {/* Chat + Email Row - inside the CV editor panel */}
            <div className="grid grid-cols-2 gap-3 min-h-[220px]">
              <div className="glass-panel p-3 flex flex-col min-h-0">
                <h3 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-semibold mb-2">
                  CV Chat Assistant — {selectedJob.title}
                </h3>
                <div className="flex-1 overflow-y-auto scrollbar-thin space-y-2 mb-2 max-h-[140px]">
                  {currentState.chatHistory.map((msg, i) => (
                    <div key={i} className={`text-[11px] px-3 py-2 rounded-lg ${
                      msg.role === "user" ? "bg-primary/10 text-foreground ml-8" : "bg-secondary/50 text-secondary-foreground mr-8"
                    }`}>
                      {msg.text}
                      {msg.role === "ai" && (
                        <button className="block mt-1 text-[9px] text-primary font-semibold hover:underline">Apply Suggestion →</button>
                      )}
                    </div>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input id={`chat-input-${selectedJobCV}`} type="text" placeholder={`Ask about CV for ${selectedJob.company}…`}
                    onKeyDown={(e) => e.key === "Enter" && handleSendChat(selectedJobCV)}
                    className="flex-1 bg-background/50 border border-border/50 rounded-lg px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/40" />
                  <button onClick={() => handleSendChat(selectedJobCV)} className="p-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
                    <Send className="w-3 h-3" />
                  </button>
                </div>
              </div>

              <div className="glass-panel p-3 flex flex-col min-h-0 overflow-y-auto scrollbar-thin">
                <h3 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-semibold mb-2">
                  Email Draft — {selectedJob.company}
                </h3>
                <div className="space-y-2 flex-1">
                  <div>
                    <label className="text-[9px] text-muted-foreground uppercase tracking-wider font-medium">To (HR Email)</label>
                    <div className="flex items-center gap-2 mt-0.5">
                      <input type="text" value={currentState.hrEmail}
                        onChange={(e) => updateJobState(selectedJobCV, { hrEmail: e.target.value })}
                        className="flex-1 bg-background/50 border border-border/50 rounded px-2 py-1.5 text-xs text-foreground focus:outline-none focus:border-primary/40" />
                      {!currentState.hrEmail && (
                        <span className="flex items-center gap-1 text-[9px] text-warning">
                          <AlertTriangle className="w-3 h-3" /> Missing
                        </span>
                      )}
                    </div>
                  </div>
                  <div>
                    <label className="text-[9px] text-muted-foreground uppercase tracking-wider font-medium">Subject</label>
                    <input type="text" value={currentState.emailSubject}
                      onChange={(e) => updateJobState(selectedJobCV, { emailSubject: e.target.value })}
                      className="w-full bg-background/50 border border-border/50 rounded px-2 py-1.5 text-xs text-foreground focus:outline-none focus:border-primary/40 mt-0.5" />
                  </div>
                  <div>
                    <label className="text-[9px] text-muted-foreground uppercase tracking-wider font-medium">Email Body</label>
                    <textarea value={currentState.emailBody}
                      onChange={(e) => updateJobState(selectedJobCV, { emailBody: e.target.value })} rows={2}
                      className="w-full bg-background/50 border border-border/50 rounded px-2 py-1.5 text-xs text-foreground resize-none focus:outline-none focus:border-primary/40 mt-0.5" />
                  </div>
                  <div>
                    <label className="text-[9px] text-muted-foreground uppercase tracking-wider font-medium">Cover Letter</label>
                    <textarea value={currentState.coverLetter}
                      onChange={(e) => updateJobState(selectedJobCV, { coverLetter: e.target.value })} rows={2}
                      className="w-full bg-background/50 border border-border/50 rounded px-2 py-1.5 text-xs text-foreground resize-none focus:outline-none focus:border-primary/40 mt-0.5" />
                  </div>
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-secondary text-secondary-foreground text-[10px] font-semibold hover:bg-secondary/80 transition-colors">
                    <RefreshCw className="w-3 h-3" /> Regenerate
                  </button>
                  <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 text-primary border border-primary/20 text-[10px] font-semibold hover:bg-primary/20 transition-colors ml-auto">
                    <MailIcon className="w-3 h-3" /> Save to Gmail Draft
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : showBaseCV ? (
        /* Base CV view with chat + email */
        <div className="flex-1 flex flex-col gap-3 min-h-0 animate-fade-in">
          <div className="glass-panel p-4 max-h-48 overflow-y-auto scrollbar-thin">
            <pre className="text-[11px] text-secondary-foreground leading-relaxed whitespace-pre-wrap font-mono">{sampleOriginalResume}</pre>
          </div>
          <div className="flex-1 grid grid-cols-2 gap-3 min-h-0">
            <div className="glass-panel p-3 flex flex-col min-h-0">
              <h3 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-semibold mb-2">CV Chat Assistant — Base CV</h3>
              <div className="flex-1 overflow-y-auto scrollbar-thin space-y-2 mb-2">
                {baseChatHistory.map((msg, i) => (
                  <div key={i} className={`text-[11px] px-3 py-2 rounded-lg ${
                    msg.role === "user" ? "bg-primary/10 text-foreground ml-8" : "bg-secondary/50 text-secondary-foreground mr-8"
                  }`}>
                    {msg.text}
                    {msg.role === "ai" && (
                      <button className="block mt-1 text-[9px] text-primary font-semibold hover:underline">Apply Suggestion →</button>
                    )}
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <input type="text" value={baseChatInput} onChange={(e) => setBaseChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSendChat(null)} placeholder="Ask about your base CV…"
                  className="flex-1 bg-background/50 border border-border/50 rounded-lg px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/40" />
                <button onClick={() => handleSendChat(null)} className="p-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
                  <Send className="w-3 h-3" />
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Default: prompt to select */
        <div className="flex-1 flex items-center justify-center glass-panel">
          <div className="text-center">
            <FileText className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">Select a CV version above or view Base CV</p>
          </div>
        </div>
      )}
    </div>
  );
};

// Sample data
const sampleOriginalResume = `JOHN DOE
Senior Software Engineer

SUMMARY
Experienced software engineer with 7+ years in backend systems, distributed computing, and machine learning infrastructure. Proficient in Python, Go, and cloud platforms.

EXPERIENCE
Lead ML Engineer — TechCorp (2022–Present)
• Led team of 6 engineers building ML training pipelines
• Reduced model training time by 40% through GPU optimization
• Implemented RLHF feedback loops for production LLMs

Senior Backend Engineer — DataFlow Inc (2019–2022)
• Designed microservices architecture serving 2M+ requests/day
• Built real-time data processing pipeline using Apache Kafka
• Mentored 4 junior engineers

Software Engineer — StartupXYZ (2017–2019)
• Full-stack development with React and Node.js
• Implemented CI/CD pipelines and automated testing

EDUCATION
M.S. Computer Science — Stanford University (2017)
B.S. Computer Science — UC Berkeley (2015)

SKILLS
Python, PyTorch, TensorFlow, Go, Rust, Kubernetes, AWS, GCP`;

const sampleAIResume = `JOHN DOE
Senior AI/ML Engineer — Alignment & Infrastructure

SUMMARY
[MODIFIED] AI/ML engineer with 7+ years specializing in alignment research, distributed training systems, and RLHF implementation. Deep expertise in PyTorch, large language models, and GPU-optimized training infrastructure.

EXPERIENCE
Lead ML Engineer — TechCorp (2022–Present)
• [MODIFIED] Architected novel ML training pipelines with focus on alignment-safe model development
• [MODIFIED] Optimized distributed GPU training clusters, achieving 40% efficiency gains at scale
• [ENHANCED] Pioneered RLHF feedback systems for production LLMs
• [ADDED] Published 2 papers on safe AI training methodologies

Senior Backend Engineer — DataFlow Inc (2019–2022)
• [MODIFIED] Engineered distributed systems architecture handling 2M+ daily inference requests
• Built real-time ML data pipeline using Apache Kafka for model monitoring
• Mentored 4 junior engineers on ML best practices

Software Engineer — StartupXYZ (2017–2019)
• Full-stack development with React and Node.js
• Implemented CI/CD pipelines for ML model deployment

EDUCATION
M.S. Computer Science — Stanford University (2017)
  Focus: Machine Learning & AI Safety
B.S. Computer Science — UC Berkeley (2015)

SKILLS
[OPTIMIZED] Python, PyTorch, RLHF, Distributed Training, GPU Computing, HPC, Go, Kubernetes, AWS, GCP, Alignment Research`;

export default PlanTab;
