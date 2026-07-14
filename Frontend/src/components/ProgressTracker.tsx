import { Check, Loader2, Circle } from "lucide-react";
import type { PipelineStep } from "../hooks/useAutonomous";

interface ProgressTrackerProps {
  steps: PipelineStep[];
  visible: boolean;
}

const ProgressTracker = ({ steps, visible }: ProgressTrackerProps) => {
  if (!visible) return null;

  return (
    <div className="px-6 py-3 border-b border-border/40 overflow-x-auto scrollbar-thin">
      <div className="flex items-center gap-1 min-w-max">
        {steps.map((step, i) => (
          <div key={step.id} className="flex items-center">
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg transition-all duration-500" 
              style={{ 
                background: step.status === "completed" ? "hsl(var(--success) / 0.1)" : 
                            step.status === "running" ? "hsl(var(--primary) / 0.1)" : "transparent" 
              }}
            >
              {step.status === "completed" ? (
                <Check className="w-3 h-3 text-success" />
              ) : step.status === "running" ? (
                <Loader2 className="w-3 h-3 text-primary animate-spin" />
              ) : (
                <Circle className="w-2.5 h-2.5 text-muted-foreground/40" />
              )}
              <span className={`text-[10px] font-medium whitespace-nowrap ${
                step.status === "completed" ? "text-success" : 
                step.status === "running" ? "text-primary" : "text-muted-foreground/50"
              }`}>
                {step.label}
                {step.detail && step.status === "completed" ? ` (${step.detail})` : ""}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div className={`w-4 h-px mx-0.5 transition-colors duration-500 ${
                step.status === "completed" ? "bg-success/40" : "bg-border/30"
              }`} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProgressTracker;
