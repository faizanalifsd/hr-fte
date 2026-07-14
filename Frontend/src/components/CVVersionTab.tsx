import { useEffect, useRef, useState } from "react";
import {
  FileText, Cpu, TrendingUp,
  Pencil, Send, Check, ChevronDown, ChevronUp,
  Loader2, Bot, RotateCcw, RefreshCw, Mail,
} from "lucide-react";
import { cvVersionApi, type CVVersionItem, type SyncToEmailResult } from "../lib/api";

// ── Smart CV text renderer ────────────────────────────────────────────────────
const CvRenderer = ({ text, dim = false }: { text: string; dim?: boolean }) => {
  if (!text?.trim())
    return <p className="text-[10px] text-muted-foreground/40 italic">No content</p>;

  if (text.trimStart().startsWith("%PDF") || text.includes("/Type /Catalog")) {
    return (
      <div className="flex flex-col items-center gap-3 py-10 text-center">
        <FileText className="w-10 h-10 text-muted-foreground/30" />
        <p className="text-sm text-muted-foreground/60">PDF binary stored — cannot render as text</p>
        <p className="text-[10px] text-muted-foreground/40">Re-upload your PDF in a new mission to view it here.</p>
      </div>
    );
  }

  const isHeading = (line: string) => {
    const t = line.trim();
    if (!t || t.length > 60) return false;
    const sectionWords =
      /^(summary|objective|skills|experience|education|projects|certifications|languages|references|contact|profile|work history|employment|achievements|awards|publications|interests|hobbies)/i;
    return (
      (t === t.toUpperCase() && /[A-Z]/.test(t)) ||
      t.endsWith(":") ||
      sectionWords.test(t) ||
      /^##?\s/.test(t)   // markdown headings
    );
  };
  const isBullet = (line: string) => /^[\s]*[-•*·▪►→✓✗]\s/.test(line);
  const isContact = (line: string) =>
    /[@|]\s*\S|(\+?\d[\d\s\-().]{7,})|(linkedin|github|portfolio)/i.test(line);
  const isEmpty = (line: string) => !line.trim();

  const lines = text.split("\n");
  const baseText = dim ? "text-muted-foreground/65" : "text-foreground/85";
  const elements: React.ReactNode[] = [];
  let i = 0;

  // First non-empty line = name (if not heading / short enough)
  while (i < lines.length && isEmpty(lines[i])) i++;
  if (i < lines.length) {
    const nameLine = lines[i].trim();
    if (nameLine && !isHeading(nameLine) && nameLine.length < 50) {
      elements.push(
        <p key={`name-${i}`} className="text-[13px] font-bold text-foreground mb-0.5 leading-tight">
          {nameLine}
        </p>
      );
      i++;
    }
  }

  for (; i < lines.length; i++) {
    const raw = lines[i];
    const line = raw.trim();
    if (isEmpty(raw)) {
      elements.push(<div key={`gap-${i}`} className="h-2" />);
    } else if (isHeading(line)) {
      const label = line.replace(/^##?\s*/, "").replace(/:$/, "");
      elements.push(
        <p key={`h-${i}`} className="text-[10px] font-bold uppercase tracking-[0.15em] text-primary mt-3 mb-1 border-b border-primary/20 pb-0.5">
          {label}
        </p>
      );
    } else if (isBullet(line)) {
      const content = line.replace(/^[\s]*[-•*·▪►→✓✗]\s*/, "");
      elements.push(
        <p key={`b-${i}`} className={`text-[10px] ${baseText} flex gap-1.5 leading-relaxed`}>
          <span className="text-primary/60 shrink-0 mt-px">•</span>
          <span>{content}</span>
        </p>
      );
    } else if (isContact(line)) {
      elements.push(
        <p key={`c-${i}`} className="text-[10px] text-muted-foreground/70 leading-relaxed font-mono">
          {line}
        </p>
      );
    } else {
      elements.push(
        <p key={`t-${i}`} className={`text-[10px] ${baseText} leading-relaxed`}>
          {line}
        </p>
      );
    }
  }

  return <div className="space-y-0.5">{elements}</div>;
};

// ── Chat message type ─────────────────────────────────────────────────────────
interface ChatMsg {
  role: "user" | "ai";
  text: string;
  draft?: string; // AI revision attached to this message
}

interface Props {
  missionId?: number;
}

const CVVersionTab = ({ missionId }: Props) => {
  // ── Core state ──────────────────────────────────────────────────────────────
  const [versions, setVersions]   = useState<CVVersionItem[]>([]);
  const [selected, setSelected]   = useState<CVVersionItem | null>(null);
  const [loading, setLoading]     = useState(false);

  // ── Edit panel state ────────────────────────────────────────────────────────
  const [editOpen, setEditOpen]   = useState(false);
  const [editMode, setEditMode]   = useState<"manual" | "chat">("manual");
  const [editText, setEditText]   = useState("");
  const [saving, setSaving]         = useState(false);
  const [saveOk, setSaveOk]         = useState(false);
  const [syncing, setSyncing]       = useState(false);
  const [syncResult, setSyncResult] = useState<SyncToEmailResult | null>(null);
  const [syncError, setSyncError]   = useState<string | null>(null);
  const [chatMsgs, setChatMsgs]     = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // ── Poll CV versions ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!missionId) { setVersions([]); setSelected(null); return; }
    setLoading(true);
    cvVersionApi.listByMission(missionId)
      .then((data) => {
        setVersions(data);
        const firstTailored = data.find((v) => v.is_master === 0);
        if (firstTailored && !selected) setSelected(firstTailored);
      })
      .catch(() => {})
      .finally(() => setLoading(false));

    const interval = setInterval(() => {
      cvVersionApi.listByMission(missionId)
        .then((data) => {
          setVersions(data);
          setSelected((prev) => {
            if (prev) return prev;
            return data.find((v) => v.is_master === 0) ?? null;
          });
        })
        .catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [missionId]);

  // ── Reset edit panel when CV version changes ─────────────────────────────────
  useEffect(() => {
    setEditOpen(false);
    setEditText(selected?.content_markdown ?? "");
    setChatMsgs([]);
    setChatInput("");
    setSaveOk(false);
    setSyncResult(null);
    setSyncError(null);
  }, [selected?.id]);

  // ── Scroll chat to bottom on new messages ────────────────────────────────────
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMsgs, chatLoading]);

  // ── Handlers ─────────────────────────────────────────────────────────────────
  const handleOpenEdit = () => {
    if (!editOpen) setEditText(selected?.content_markdown ?? "");
    setEditOpen((v) => !v);
  };

  const handleSaveManual = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const updated = await cvVersionApi.saveManual(selected.id, editText);
      // Update local versions list so CvRenderer shows the new content immediately
      setVersions((prev) =>
        prev.map((v) => (v.id === updated.id ? { ...v, content_markdown: updated.content_markdown } : v))
      );
      setSelected((prev) => prev ? { ...prev, content_markdown: updated.content_markdown } : prev);
      setSaveOk(true);
      setTimeout(() => setSaveOk(false), 2500);
    } catch {
      // silent — user can retry
    } finally {
      setSaving(false);
    }
  };

  const handleSyncToEmail = async () => {
    if (!selected || selected.is_master) return;
    setSyncing(true);
    setSyncResult(null);
    setSyncError(null);
    try {
      const result = await cvVersionApi.syncToEmail(selected.id);
      setSyncResult(result);
    } catch (err) {
      setSyncError(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const handleSendChat = async () => {
    if (!selected || !chatInput.trim() || chatLoading) return;
    const instruction = chatInput.trim();
    setChatInput("");
    setChatMsgs((prev) => [...prev, { role: "user", text: instruction }]);
    setChatLoading(true);
    try {
      const result = await cvVersionApi.aiEdit(selected.id, instruction);
      setChatMsgs((prev) => [
        ...prev,
        { role: "ai", text: result.explanation, draft: result.revised_content },
      ]);
    } catch (err) {
      setChatMsgs((prev) => [
        ...prev,
        { role: "ai", text: err instanceof Error ? err.message : "AI edit failed — please try again." },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleApplyDraft = (draft: string) => {
    setEditText(draft);
    setEditMode("manual");
  };

  // ── Early returns ─────────────────────────────────────────────────────────────
  if (!missionId) {
    return (
      <div className="glass-panel p-6 h-full flex flex-col items-center justify-center gap-3">
        <FileText className="w-8 h-8 text-muted-foreground/30" />
        <p className="text-sm text-muted-foreground/50">Launch a mission to see CV versions</p>
      </div>
    );
  }

  if (loading && versions.length === 0) {
    return (
      <div className="glass-panel p-6 h-full flex items-center justify-center">
        <p className="text-sm text-muted-foreground/50 animate-pulse">Loading CV versions…</p>
      </div>
    );
  }

  if (versions.length === 0) {
    return (
      <div className="glass-panel p-6 h-full flex flex-col items-center justify-center gap-3">
        <Cpu className="w-8 h-8 text-muted-foreground/30 animate-pulse" />
        <p className="text-sm text-muted-foreground/50">AI is optimizing CVs — check back shortly</p>
      </div>
    );
  }

  const tailored = versions.filter((v) => v.is_master === 0);

  return (
    <div className="glass-panel h-full flex flex-col overflow-hidden">

      {/* ── TOP TAB BAR ──────────────────────────────────────── */}
      <div className="flex items-end gap-0 px-4 pt-3 border-b border-border/40 overflow-x-auto scrollbar-none shrink-0">
        {tailored.map((v, i) => (
          <button
            key={v.id}
            onClick={() => setSelected(v)}
            className={`flex items-center gap-1.5 px-4 py-2 text-[11px] font-semibold border-b-2 transition-colors whitespace-nowrap mr-1 ${
              selected?.id === v.id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Cpu className="w-3 h-3" />
            CV {i + 1}
            {v.keyword_match_score !== undefined && (
              <span className="ml-1 text-[8px] px-1.5 py-0.5 rounded-full bg-primary/15 text-primary font-mono">
                {v.keyword_match_score}%
              </span>
            )}
          </button>
        ))}

        {tailored.length === 0 && (
          <span className="px-3 py-2 text-[10px] text-muted-foreground/40 italic">
            AI versions appear after workflow runs…
          </span>
        )}
      </div>

      {/* ── CONTENT AREA ─────────────────────────────────────── */}
      {!selected ? (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-sm text-muted-foreground/40">Select a CV version above</p>
        </div>

      ) : (
        /* ── AI-TAILORED ── */
        <div className="flex-1 flex flex-col overflow-hidden min-h-0">

          {/* Meta bar */}
          <div className="px-4 py-2 border-b border-border/30 flex items-center gap-3 shrink-0">
            <span className="text-[10px] text-muted-foreground/60">
              {selected.job_company} · {selected.job_role}
            </span>
            {selected.keyword_match_score !== undefined && (
              <span className="ml-auto flex items-center gap-1 text-[10px] text-primary font-mono">
                <TrendingUp className="w-3 h-3" />
                {selected.keyword_match_score}% keyword match
              </span>
            )}
          </div>

          {/* Scrollable content pane */}
          <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5 space-y-5">
            <CvRenderer text={selected.content_markdown || "—"} />

            {/* Suggested improvements */}
            {selected.optimization_notes && (() => {
              try {
                const notes: string[] = JSON.parse(selected.optimization_notes);
                if (!notes.length) return null;
                return (
                  <div className="border-t border-border/30 pt-4">
                    <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                      Suggested Improvements
                    </p>
                    <ul className="space-y-1.5">
                      {notes.map((n, idx) => (
                        <li key={idx} className="text-[10px] text-muted-foreground/80 flex gap-1.5">
                          <span className="text-primary shrink-0">•</span>
                          <span>{n}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              } catch { return null; }
            })()}
          </div>

          {/* ── EDIT PANEL ────────────────── */}
          <div className="shrink-0 border-t border-border/40 bg-background/40">

              {/* Header row — always visible */}
              <div
                className="flex items-center gap-2 px-4 py-2 cursor-pointer select-none hover:bg-muted/30 transition-colors"
                onClick={handleOpenEdit}
              >
                <Pencil className="w-3 h-3 text-muted-foreground" />
                <span className="text-[11px] font-semibold text-muted-foreground">Edit CV</span>

                {/* Mode tabs (only clickable when open) */}
                <div
                  className="flex rounded overflow-hidden border border-border/40 text-[9px] font-semibold ml-2"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={() => { setEditMode("manual"); setEditOpen(true); }}
                    className={`flex items-center gap-1 px-2 py-0.5 transition-colors ${
                      editMode === "manual" && editOpen
                        ? "bg-muted text-foreground"
                        : "text-muted-foreground hover:bg-muted/40"
                    }`}
                  >
                    <Pencil className="w-2.5 h-2.5" />
                    Manual
                  </button>
                  <button
                    onClick={() => { setEditMode("chat"); setEditOpen(true); }}
                    className={`flex items-center gap-1 px-2 py-0.5 transition-colors ${
                      editMode === "chat" && editOpen
                        ? "bg-primary/15 text-primary"
                        : "text-muted-foreground hover:bg-muted/40"
                    }`}
                  >
                    <Bot className="w-2.5 h-2.5" />
                    AI Chat
                  </button>
                </div>

                <span className="ml-auto text-muted-foreground/40">
                  {editOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}
                </span>
              </div>

              {/* Expanded body */}
              {editOpen && (
                <div className="px-4 pb-4">
                  {editMode === "manual" ? (
                    /* ── Manual editor ── */
                    <div className="flex flex-col gap-2">
                      <textarea
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        rows={10}
                        className="w-full text-[10px] font-mono bg-background/60 border border-border/40 rounded p-2 resize-y focus:outline-none focus:ring-1 focus:ring-primary/40 text-foreground/90 leading-relaxed"
                        placeholder="Edit your CV content here…"
                      />
                      <div className="flex items-center gap-2 flex-wrap">
                        <button
                          onClick={handleSaveManual}
                          disabled={saving}
                          className="flex items-center gap-1.5 px-3 py-1 text-[10px] font-semibold rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
                        >
                          {saving ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : saveOk ? (
                            <Check className="w-3 h-3" />
                          ) : null}
                          {saveOk ? "Saved!" : saving ? "Saving…" : "Save Changes"}
                        </button>
                        <button
                          onClick={() => { setEditText(selected.content_markdown ?? ""); setSaveOk(false); }}
                          className="flex items-center gap-1 px-3 py-1 text-[10px] font-semibold rounded text-muted-foreground hover:bg-muted/40 transition-colors"
                        >
                          <RotateCcw className="w-2.5 h-2.5" />
                          Reset
                        </button>
                        {/* Sync to Email — only visible for tailored CVs after a save */}
                        {saveOk && !selected.is_master && (
                          <button
                            onClick={handleSyncToEmail}
                            disabled={syncing}
                            className="flex items-center gap-1.5 px-3 py-1 text-[10px] font-semibold rounded border border-primary/40 text-primary hover:bg-primary/10 disabled:opacity-50 transition-colors ml-auto"
                          >
                            {syncing ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <RefreshCw className="w-3 h-3" />
                            )}
                            {syncing ? "Syncing…" : "Sync to Email"}
                          </button>
                        )}
                      </div>
                      {/* Sync feedback */}
                      {syncResult && (
                        <div className="flex items-start gap-1.5 px-2.5 py-1.5 rounded bg-success/10 border border-success/20 text-[10px] text-success">
                          <Mail className="w-3 h-3 shrink-0 mt-px" />
                          <span>Cover letter regenerated — email updated in HITL panel</span>
                        </div>
                      )}
                      {syncError && (
                        <p className="text-[10px] text-destructive">{syncError}</p>
                      )}
                    </div>

                  ) : (
                    /* ── AI Chat editor ── */
                    <div className="flex flex-col gap-2">

                      {/* Message history */}
                      <div className="max-h-40 overflow-y-auto flex flex-col gap-2 py-1 pr-1">
                        {chatMsgs.length === 0 && (
                          <p className="text-[10px] text-muted-foreground/40 italic text-center py-3">
                            Describe what to improve — e.g. "Strengthen the summary" or "Add more Python keywords"
                          </p>
                        )}
                        {chatMsgs.map((msg, idx) => (
                          <div
                            key={idx}
                            className={`flex flex-col gap-1 ${msg.role === "user" ? "items-end" : "items-start"}`}
                          >
                            <div
                              className={`px-2.5 py-1.5 rounded-lg text-[10px] leading-relaxed max-w-[85%] ${
                                msg.role === "user"
                                  ? "bg-primary/15 text-primary"
                                  : "bg-muted text-foreground/80"
                              }`}
                            >
                              {msg.role === "ai" && (
                                <Bot className="w-2.5 h-2.5 inline mr-1 text-primary/60" />
                              )}
                              {msg.text}
                            </div>
                            {/* Apply button for AI messages that carry a draft */}
                            {msg.role === "ai" && msg.draft && (
                              <button
                                onClick={() => handleApplyDraft(msg.draft!)}
                                className="flex items-center gap-1 px-2 py-0.5 text-[9px] font-semibold rounded border border-primary/30 text-primary hover:bg-primary/10 transition-colors"
                              >
                                <Check className="w-2.5 h-2.5" />
                                Apply to editor
                              </button>
                            )}
                          </div>
                        ))}
                        {chatLoading && (
                          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground/50">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            AI is rewriting…
                          </div>
                        )}
                        <div ref={chatEndRef} />
                      </div>

                      {/* Instruction input */}
                      <div className="flex gap-2">
                        <input
                          value={chatInput}
                          onChange={(e) => setChatInput(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSendChat()}
                          placeholder="e.g. Strengthen the summary, add Python keywords…"
                          disabled={chatLoading}
                          className="flex-1 text-[10px] bg-background/60 border border-border/40 rounded px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary/40 text-foreground/90 placeholder:text-muted-foreground/40 disabled:opacity-50"
                        />
                        <button
                          onClick={handleSendChat}
                          disabled={!chatInput.trim() || chatLoading}
                          className="flex items-center gap-1 px-3 py-1.5 text-[10px] font-semibold rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 transition-colors"
                        >
                          <Send className="w-3 h-3" />
                        </button>
                      </div>
                      <p className="text-[9px] text-muted-foreground/40">
                        Press "Apply to editor" on any AI reply to load it into the manual editor, then Save.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
        </div>
      )}
    </div>
  );
};

export default CVVersionTab;
