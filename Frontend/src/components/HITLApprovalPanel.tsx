import { useState, useEffect } from "react";
import { emailApi, type EmailDraft } from "../lib/api";
import {
  CheckCircle2,
  XCircle,
  PenLine,
  Mail,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Loader2,
} from "lucide-react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";

interface Props {
  onApprovalComplete?: (count: number) => void;
}

const HITLApprovalPanel = ({ onApprovalComplete }: Props) => {
  const [pendingEmails, setPendingEmails] = useState<EmailDraft[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");
  const [editToEmail, setEditToEmail] = useState("");
  const [actioning, setActioning] = useState<number | null>(null);
  const [approvedCount, setApprovedCount] = useState(0);

  const fetchPending = async () => {
    setLoading(true);
    try {
      const emails = await emailApi.listPending();
      setPendingEmails(emails);
    } catch {
      // silently ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPending();
    const interval = setInterval(fetchPending, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleApprove = async (id: number) => {
    setActioning(id);
    try {
      await emailApi.approve(id);
      setPendingEmails((prev) => prev.filter((e) => e.id !== id));
      const newCount = approvedCount + 1;
      setApprovedCount(newCount);
      onApprovalComplete?.(newCount);
    } catch (err) {
      console.error("Approve failed:", err);
    } finally {
      setActioning(null);
    }
  };

  const handleReject = async (id: number) => {
    setActioning(id);
    try {
      await emailApi.reject(id, "User rejected");
      setPendingEmails((prev) => prev.filter((e) => e.id !== id));
    } catch (err) {
      console.error("Reject failed:", err);
    } finally {
      setActioning(null);
    }
  };

  const startEdit = (email: EmailDraft) => {
    setEditingId(email.id);
    setEditSubject(email.subject);
    setEditBody(email.body);
    setEditToEmail(email.to_email);
  };

  const handleSaveEdit = async (id: number) => {
    setActioning(id);
    try {
      const updated = await emailApi.edit(id, editSubject, editBody, editToEmail);
      setPendingEmails((prev) => prev.map((e) => (e.id === id ? updated : e)));
      setEditingId(null);
    } catch (err) {
      console.error("Edit failed:", err);
    } finally {
      setActioning(null);
    }
  };

  if (pendingEmails.length === 0 && !loading) {
    return (
      <div className="glass-panel p-4 flex flex-col items-center gap-2 text-center">
        <Mail className="w-6 h-6 text-muted-foreground/40" />
        <p className="text-[11px] text-muted-foreground">No emails pending approval</p>
        <button
          onClick={fetchPending}
          className="text-[10px] text-primary hover:text-primary/80 flex items-center gap-1"
        >
          <RefreshCw className="w-3 h-3" /> Refresh
        </button>
      </div>
    );
  }

  return (
    <div className="glass-panel flex flex-col min-h-0">
      <div className="px-4 py-3 border-b border-border/30 flex items-center justify-between">
        <div>
          <h3 className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-semibold">
            HITL Email Approval
          </h3>
          <p className="text-[10px] text-muted-foreground/60 mt-0.5">
            Review and approve emails before sending
          </p>
        </div>
        <div className="flex items-center gap-2">
          {loading && <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />}
          <span className="text-[10px] font-mono text-warning font-semibold">
            {pendingEmails.length} pending
          </span>
          <button onClick={fetchPending} className="text-muted-foreground hover:text-foreground">
            <RefreshCw className="w-3 h-3" />
          </button>
        </div>
      </div>

      <div className="overflow-y-auto flex-1 divide-y divide-border/20">
        {pendingEmails.map((email) => {
          const isExpanded = expandedId === email.id;
          const isEditing = editingId === email.id;
          const isActioning = actioning === email.id;

          return (
            <div key={email.id} className="p-4">
              {/* Email header */}
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-foreground truncate">{email.subject}</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    To: <span className="font-mono">{email.to_email}</span>
                    {email.to_name && ` · ${email.to_name}`}
                    {email.hr_title && (
                      <span className="text-muted-foreground/60"> · {email.hr_title}</span>
                    )}
                  </p>
                  {email.hr_email_confidence && (
                    <span className={`inline-block mt-1 text-[9px] font-semibold px-1.5 py-0.5 rounded-full ${
                      email.hr_email_confidence === "verified"
                        ? "bg-success/20 text-success"
                        : email.hr_email_confidence === "likely"
                        ? "bg-warning/20 text-warning"
                        : "bg-destructive/20 text-destructive"
                    }`}>
                      {email.hr_email_confidence === "verified"
                        ? "✓ Verified Email"
                        : email.hr_email_confidence === "likely"
                        ? "~ Likely Email"
                        : "⚠ Fake recipient email — update To: address before sending"}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => setExpandedId(isExpanded ? null : email.id)}
                  className="text-muted-foreground hover:text-foreground shrink-0"
                >
                  {isExpanded ? (
                    <ChevronUp className="w-3.5 h-3.5" />
                  ) : (
                    <ChevronDown className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>

              {/* Email body preview / edit */}
              {isExpanded && (
                <div className="mb-3">
                  {isEditing ? (
                    <div className="space-y-2">
                      <input
                        type="email"
                        value={editToEmail}
                        onChange={(e) => setEditToEmail(e.target.value)}
                        className={`w-full text-xs bg-background/50 border rounded px-2 py-1.5 text-foreground font-mono ${
                          email.recipient_confirmed ? "border-border/40" : "border-destructive/50"
                        }`}
                        placeholder="To: recipient email"
                      />
                      {!email.recipient_confirmed && (
                        <p className="text-[10px] text-destructive">
                          This address is a guess, not a verified HR email — confirm the real one before you can approve.
                        </p>
                      )}
                      <input
                        type="text"
                        value={editSubject}
                        onChange={(e) => setEditSubject(e.target.value)}
                        className="w-full text-xs bg-background/50 border border-border/40 rounded px-2 py-1.5 text-foreground"
                        placeholder="Subject"
                      />
                      <Textarea
                        value={editBody}
                        onChange={(e) => setEditBody(e.target.value)}
                        rows={6}
                        className="text-xs font-mono bg-background/50 border-border/40 resize-none"
                      />
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-[10px] h-7 px-2"
                          onClick={() => setEditingId(null)}
                        >
                          Cancel
                        </Button>
                        <Button
                          size="sm"
                          className="text-[10px] h-7 px-2"
                          onClick={() => handleSaveEdit(email.id)}
                          disabled={isActioning}
                        >
                          {isActioning ? <Loader2 className="w-3 h-3 animate-spin" /> : "Save"}
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="bg-background/30 rounded p-3 text-[11px] text-muted-foreground leading-relaxed whitespace-pre-wrap font-mono border border-border/20">
                      {email.body}
                    </div>
                  )}
                </div>
              )}

              {/* Action buttons */}
              {!isEditing && (
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={() => (email.recipient_confirmed ? handleApprove(email.id) : startEdit(email))}
                    disabled={isActioning}
                    title={email.recipient_confirmed ? undefined : "Recipient is an unverified guess — fix the To: address first"}
                    className={`gap-1 h-7 text-[10px] border ${
                      email.recipient_confirmed
                        ? "bg-success/20 text-success border-success/30 hover:bg-success/30"
                        : "bg-destructive/10 text-destructive border-destructive/30 hover:bg-destructive/20"
                    }`}
                    variant="outline"
                  >
                    {isActioning ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <CheckCircle2 className="w-3 h-3" />
                    )}
                    {email.recipient_confirmed ? "Approve & Send" : "Fix recipient to approve"}
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => startEdit(email)}
                    disabled={isActioning}
                    className="gap-1 h-7 text-[10px]"
                    variant="outline"
                  >
                    <PenLine className="w-3 h-3" />
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => handleReject(email.id)}
                    disabled={isActioning}
                    className="gap-1 h-7 text-[10px] text-destructive border-destructive/30 hover:bg-destructive/10"
                    variant="outline"
                  >
                    <XCircle className="w-3 h-3" />
                    Reject
                  </Button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default HITLApprovalPanel;
