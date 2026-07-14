import { Bot, Circle, Sun, Moon, Link2, Zap } from "lucide-react";
import { Switch } from "./ui/switch";

type Status = "idle" | "running" | "reviewing";

const statusConfig: Record<Status, { label: string; color: string }> = {
  idle: { label: "Idle", color: "text-muted-foreground" },
  running: { label: "Running", color: "text-success" },
  reviewing: { label: "Reviewing", color: "text-warning" },
};

interface HeaderProps {
  status: Status;
  autonomous: boolean;
  onToggleAutonomous: () => void;
  apiMode: "connected" | "simulated";
  theme: "dark" | "light";
  onToggleTheme: () => void;
}

const Header = ({ status, autonomous, onToggleAutonomous, apiMode, theme, onToggleTheme }: HeaderProps) => {
  const { label, color } = statusConfig[status];

  return (
    <header className="flex items-center justify-between px-8 py-4 border-b border-border/40">
      <div className="flex items-center gap-5">
        <div className="relative">
          <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center">
            <Bot className="w-5 h-5 text-primary" />
          </div>
          <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-background ${color === "text-success" ? "bg-success" : color === "text-warning" ? "bg-warning" : "bg-muted-foreground"}`} />
        </div>
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-foreground">Digital FTE</h1>
          <p className="text-xs text-muted-foreground tracking-wide">Your Autonomous Career Employee</p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* API Mode Badge */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border/30 text-[10px]">
          <Link2 className="w-3 h-3 text-muted-foreground" />
          <span className="text-muted-foreground font-medium">API:</span>
          <span className={`font-semibold ${apiMode === "connected" ? "text-success" : "text-warning"}`}>
            {apiMode === "connected" ? "Connected" : "Simulated"}
          </span>
        </div>

        {/* Autonomous Mode Toggle */}
        <div className="flex items-center gap-2 glass-panel px-3 py-1.5">
          <Zap className={`w-3 h-3 ${autonomous ? "text-success" : "text-muted-foreground"}`} />
          <span className="text-[10px] font-medium text-foreground">Autonomous</span>
          <Switch checked={autonomous} onCheckedChange={onToggleAutonomous} className="scale-75" />
        </div>

        {/* Theme Toggle */}
        <button
          onClick={onToggleTheme}
          className="p-2 rounded-lg border border-border/30 hover:bg-secondary/50 transition-colors"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? (
            <Sun className="w-4 h-4 text-muted-foreground hover:text-foreground transition-colors" />
          ) : (
            <Moon className="w-4 h-4 text-muted-foreground hover:text-foreground transition-colors" />
          )}
        </button>

        {/* Status */}
        <div className="flex items-center gap-2.5 glass-panel px-4 py-2">
          <Circle className={`w-2 h-2 fill-current ${color} status-glow`} />
          <span className={`text-xs font-medium tracking-wider uppercase ${color}`}>{label}</span>
        </div>
      </div>
    </header>
  );
};

export default Header;
