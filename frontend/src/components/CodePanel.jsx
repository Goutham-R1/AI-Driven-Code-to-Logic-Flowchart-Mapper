import React from "react";

export default function CodePanel({
  language,
  setLanguage,
  code,
  setCode,
  codeLines,
  highlight
}) {
  const start = highlight?.startLine ?? null;
  const end = highlight?.endLine ?? null;

  return (
    <>
      <div className="panelHeader">
        <h2>Code Input</h2>
        <select
          className="select"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
        >
          <option value="python">Python</option>
          <option value="javascript">JavaScript</option>
        </select>
      </div>

      <textarea
        className="textarea"
        value={code}
        onChange={(e) => setCode(e.target.value)}
        spellCheck={false}
      />

      <div className="hint">
        {start && end ? (
          <span>
            Highlighting lines <b>{start}</b>–<b>{end}</b> (from clicked node <b>{highlight.nodeId}</b>)
          </span>
        ) : (
          <span>Click a flowchart node to highlight related code (if mapping is available).</span>
        )}
      </div>

      <pre className="codePreview">
        {codeLines.map((line, idx) => {
          const lineNo = idx + 1;
          const active = start && end && lineNo >= start && lineNo <= end;
          return (
            <div key={idx} className={`codeLine ${active ? "active" : ""}`}>
              <span className="lineNo">{String(lineNo).padStart(3, " ")}</span>
              <span className="lineText">{line || " "}</span>
            </div>
          );
        })}
      </pre>
    </>
  );
}
