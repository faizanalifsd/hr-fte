interface TabNavigationProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const tabs = [
  { id: "job", label: "JOB", enabled: true },
  { id: "cv", label: "CV VERSIONS", enabled: true },
  { id: "plan", label: "PLAN", enabled: true },
  { id: "graph", label: "GRAPH", enabled: true },
  { id: "evidence", label: "EVIDENCE", enabled: true },
];

const TabNavigation = ({ activeTab, onTabChange }: TabNavigationProps) => {
  return (
    <nav className="flex items-center justify-center gap-1 py-3">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => tab.enabled && onTabChange(tab.id)}
          disabled={!tab.enabled}
          className={`
            relative px-8 py-2.5 text-xs font-semibold tracking-[0.2em] uppercase rounded-lg transition-all duration-300
            ${tab.enabled ? "cursor-pointer" : "cursor-not-allowed"}
            ${
              activeTab === tab.id
                ? "bg-primary/10 text-primary border border-primary/20"
                : tab.enabled
                ? "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                : "text-muted-foreground/40"
            }
          `}
        >
          {tab.label}
          {!tab.enabled && (
            <span className="ml-2 text-[9px] tracking-normal font-normal opacity-60">soon</span>
          )}
        </button>
      ))}
    </nav>
  );
};

export default TabNavigation;
