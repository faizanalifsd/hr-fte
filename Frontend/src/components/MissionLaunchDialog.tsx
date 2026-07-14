import { useState, useRef } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Rocket, Upload, AlertCircle, Loader2 } from "lucide-react";

interface Props {
  open: boolean;
  onClose: () => void;
  onLaunch: (missionInput: string, cvText: string) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
}

const SAMPLE_MISSION = "Find me 5 Python developer jobs in Karachi within 30 days";

const MissionLaunchDialog = ({ open, onClose, onLaunch, isLoading, error }: Props) => {
  const [missionInput, setMissionInput] = useState(SAMPLE_MISSION);
  const [cvText, setCvText] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    if (file.name.toLowerCase().endsWith(".pdf")) return; // PDF accepted silently — user pastes text
    const reader = new FileReader();
    reader.onload = (ev) => {
      if (typeof ev.target?.result === "string") setCvText(ev.target.result);
    };
    reader.readAsText(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!missionInput.trim() || !cvText.trim()) return;
    await onLaunch(missionInput.trim(), cvText.trim());
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && !isLoading && onClose()}>
      <DialogContent className="sm:max-w-[600px] bg-card border-border/40">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-foreground">
            <Rocket className="w-4 h-4 text-primary" />
            Launch Autonomous Mission
          </DialogTitle>
          <DialogDescription className="text-muted-foreground text-xs">
            Describe the jobs you want to find and paste your CV. The agent will
            scrape, match, and prepare applications for your review.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 mt-2">
          {/* Mission Input */}
          <div className="space-y-1.5">
            <Label className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
              Mission Requirements
            </Label>
            <Input
              value={missionInput}
              onChange={(e) => setMissionInput(e.target.value)}
              placeholder="e.g. Find me 10 Python developer jobs in Karachi within 30 days"
              disabled={isLoading}
              className="bg-background/50 border-border/40 text-sm"
            />
            <p className="text-[10px] text-muted-foreground/60">
              Include role, count, location, and timeframe.
            </p>
          </div>

          {/* CV Input */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
                Your CV / Resume
              </Label>
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                disabled={isLoading}
                className="flex items-center gap-1 text-[10px] text-primary hover:text-primary/80 transition-colors"
              >
                <Upload className="w-3 h-3" />
                {fileName ?? "Upload .txt / .pdf"}
              </button>
              <input ref={fileRef} type="file" accept=".txt,.md,.pdf" className="hidden" onChange={handleFile} />
            </div>
            <Textarea
              value={cvText}
              onChange={(e) => setCvText(e.target.value)}
              placeholder="Paste your CV content here..."
              disabled={isLoading}
              rows={8}
              className="bg-background/50 border-border/40 text-xs font-mono resize-none"
            />
            <p className="text-[10px] text-muted-foreground/60">
              Paste your CV as plain text, or upload a .txt file.
            </p>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-xs text-destructive">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" size="sm" onClick={onClose} disabled={isLoading} className="text-muted-foreground">
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={isLoading || !missionInput.trim() || !cvText.trim()} className="gap-1.5">
              {isLoading ? (
                <><Loader2 className="w-3.5 h-3.5 animate-spin" />Launching…</>
              ) : (
                <><Rocket className="w-3.5 h-3.5" />Launch Mission</>
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default MissionLaunchDialog;
