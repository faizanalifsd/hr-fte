import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";
import type { PipelineStep } from "../hooks/useAutonomous";
import { FileText } from "lucide-react";

interface GraphTabProps {
  steps: PipelineStep[];
  autonomous: boolean;
}

const GraphTab = ({ steps, autonomous }: GraphTabProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [, setRendered] = useState(false);

  const cvUploaded = steps[0]?.status === "completed" || steps[0]?.status === "running" || autonomous;

  const getNodeClass = (stepIndex: number) => {
    const status = steps[stepIndex]?.status;
    if (status === "completed") return "completed";
    if (status === "running") return "running";
    return "pending";
  };

  useEffect(() => {
    if (!cvUploaded || !containerRef.current) {
      setRendered(false);
      return;
    }

    const isDark = document.documentElement.classList.contains("dark") || !document.documentElement.classList.contains("light");

    mermaid.initialize({
      startOnLoad: false,
      theme: "base",
      themeVariables: isDark
        ? {
            primaryColor: "#1a2332",
            primaryTextColor: "#e2e8f0",
            primaryBorderColor: "#2dd4bf",
            lineColor: "#334155",
            secondaryColor: "#1e293b",
            tertiaryColor: "#0f172a",
            background: "transparent",
            mainBkg: "#1a2332",
            nodeBorder: "#334155",
            clusterBkg: "#0f172a",
            titleColor: "#e2e8f0",
            edgeLabelBackground: "#1a2332",
          }
        : {
            primaryColor: "#f0fdf4",
            primaryTextColor: "#1a2e1a",
            primaryBorderColor: "#22c55e",
            lineColor: "#d1d5db",
            secondaryColor: "#f8fafc",
            tertiaryColor: "#ffffff",
            background: "transparent",
            mainBkg: "#f0fdf4",
            nodeBorder: "#d1d5db",
            clusterBkg: "#ffffff",
            titleColor: "#1a2e1a",
            edgeLabelBackground: "#ffffff",
          },
    });

    const diagram = `flowchart TD
    A[Start] --> B[CV Upload]
    B --> C[CV Parser Agent]
    C --> D[Job Scraper Agent]
    D --> E[Matcher Agent]
    E --> F[Top 10 Jobs]
    F --> G1[CV v1]
    F --> G2[CV v2]
    F --> G3[CV v3]
    F --> G4[CV v4]
    F --> G5[CV v5]
    F --> G6[CV v6]
    F --> G7[CV v7]
    F --> G8[CV v8]
    F --> G9[CV v9]
    F --> G10[CV v10]
    G1 --> H[CV Optimizer Agent]
    G2 --> H
    G3 --> H
    G4 --> H
    G5 --> H
    G6 --> H
    G7 --> H
    G8 --> H
    G9 --> H
    G10 --> H
    H --> I[Email Generator Agent]
    I --> J[Human Approval - HITL]
    J --> K[Application Agent]
    K --> L[Evidence Agent]
    L --> M[End]

    class A ${getNodeClass(0)}
    class B ${getNodeClass(0)}
    class C ${getNodeClass(1)}
    class D ${getNodeClass(2)}
    class E ${getNodeClass(3)}
    class F ${getNodeClass(3)}
    class G1,G2,G3,G4,G5,G6,G7,G8,G9,G10 ${getNodeClass(3)}
    class H ${getNodeClass(4)}
    class I ${getNodeClass(4)}
    class J ${getNodeClass(5)}
    class K ${getNodeClass(5)}
    class L ${getNodeClass(6)}
    class M ${getNodeClass(6)}

    classDef completed fill:${isDark ? "#064e3b" : "#dcfce7"},stroke:${isDark ? "#10b981" : "#22c55e"},stroke-width:2px,color:${isDark ? "#6ee7b7" : "#166534"}
    classDef running fill:${isDark ? "#1e3a5f" : "#dbeafe"},stroke:${isDark ? "#38bdf8" : "#3b82f6"},stroke-width:2px,stroke-dasharray:5,color:${isDark ? "#7dd3fc" : "#1e40af"}
    classDef pending fill:${isDark ? "#1e293b" : "#f1f5f9"},stroke:${isDark ? "#475569" : "#cbd5e1"},stroke-width:1px,color:${isDark ? "#94a3b8" : "#64748b"}`;

    const id = `graph-diagram-${Date.now()}`;
    const renderDiagram = async () => {
      try {
        containerRef.current!.innerHTML = "";
        const { svg } = await mermaid.render(id, diagram);
        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
          setRendered(true);
        }
      } catch (e) {
        console.error("Mermaid render error:", e);
      }
    };

    renderDiagram();
  }, [cvUploaded, steps, autonomous]);

  if (!cvUploaded) {
    return (
      <div className="h-full flex items-center justify-center glass-panel">
        <div className="text-center">
          <FileText className="w-10 h-10 text-muted-foreground/20 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">No execution flow available.</p>
          <p className="text-[10px] text-muted-foreground/60 mt-1">Upload a CV and start autonomous mode to generate the flow diagram.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full glass-panel flex items-center justify-center overflow-auto scrollbar-thin p-6">
      <div ref={containerRef} className="w-full flex items-center justify-center" />
    </div>
  );
};

export default GraphTab;
