import React, { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

export default function MermaidViewer({ mermaid: mermaidText, onNodeClick }) {
  const ref = useRef(null);
  const [renderErr, setRenderErr] = useState("");

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "loose",
      theme: "default",
      flowchart: { curve: "basis" }
    });
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function render() {
      setRenderErr("");
      if (!ref.current) return;

      try {
        const id = "mmd-" + Math.random().toString(16).slice(2);
        const { svg } = await mermaid.render(id, mermaidText);

        if (cancelled) return;
        ref.current.innerHTML = svg;

        const nodeGroups = ref.current.querySelectorAll("g.node");
        nodeGroups.forEach((g) => {
          g.style.cursor = "pointer";
          g.addEventListener("click", () => {
            const title = g.querySelector("title")?.textContent?.trim();
            if (title) onNodeClick?.(title);
          });
        });
      } catch (e) {
        setRenderErr(String(e?.message || e));
      }
    }

    render();
    return () => {
      cancelled = true;
    };
  }, [mermaidText, onNodeClick]);

  return (
    <div>
      <div className="panelHeader">
        <h2>Flowchart</h2>
      </div>

      {renderErr ? (
        <div className="error">
          Mermaid render error: {renderErr}
          <div className="small">
            Make sure your Mermaid text starts with <code>graph TD</code>.
          </div>
        </div>
      ) : null}

      <div className="mermaidBox" ref={ref} />
      <details className="rawBox">
        <summary>Raw Mermaid</summary>
        <pre>{mermaidText}</pre>
      </details>
    </div>
  );
}
