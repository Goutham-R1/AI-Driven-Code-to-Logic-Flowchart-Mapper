import React, { useMemo, useState } from "react";
import { analyzeCode } from "./api.js";
import CodePanel from "./components/CodePanel.jsx";
import MermaidViewer from "./components/MermaidViewer.jsx";
import ExplanationPanel from "./components/ExplanationPanel.jsx";

const DEFAULT_PY = `def classify(n):
    if n < 0:
        return "negative"
    elif n == 0:
        return "zero"
    else:
        return "positive"
`;

export default function App() {
  const [language, setLanguage] = useState("python");
  const [code, setCode] = useState(DEFAULT_PY);
  const [loading, setLoading] = useState(false);
  const [mermaid, setMermaid] = useState("graph TD\nS([Start]) --> E([End])");
  const [explanation, setExplanation] = useState("Paste code and click Generate.");
  const [nodeMap, setNodeMap] = useState({});
  const [highlight, setHighlight] = useState(null);
  const [error, setError] = useState("");

  const codeLines = useMemo(() => code.split("\n"), [code]);

  async function onGenerate() {
    setLoading(true);
    setError("");
    setHighlight(null);

    try {
      const result = await analyzeCode({ code, language });
      setMermaid(result.mermaid);
      setExplanation(result.explanation);
      setNodeMap(result.nodeMap || {});
    } catch (e) {
      setError(e.message || "Failed.");
    } finally {
      setLoading(false);
    }
  }

  function onNodeClick(nodeId) {
    const range = nodeMap?.[nodeId];
    if (!range) return;
    setHighlight({ nodeId, ...range });
  }

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <h1>AI-Driven Code-to-Logic Flowchart Mapper</h1>
          <p className="subtitle">Paste Python/JS → get explanation + Mermaid flowchart</p>
        </div>
        <div className="actions">
          <button className="btn" onClick={onGenerate} disabled={loading}>
            {loading ? "Generating..." : "Generate Flowchart"}
          </button>
        </div>
      </header>

      {error ? <div className="error">{error}</div> : null}

      <div className="grid">
        <section className="panel">
          <CodePanel
            language={language}
            setLanguage={setLanguage}
            code={code}
            setCode={setCode}
            codeLines={codeLines}
            highlight={highlight}
          />
        </section>

        <section className="panel">
          <MermaidViewer mermaid={mermaid} onNodeClick={onNodeClick} />
          <ExplanationPanel explanation={explanation} />
        </section>
      </div>

      <footer className="footer">
        <span>
          Tip: set backend <code>AI_PROVIDER=openai</code> and <code>OPENAI_API_KEY</code> for real AI.
        </span>
      </footer>
    </div>
  );
}
