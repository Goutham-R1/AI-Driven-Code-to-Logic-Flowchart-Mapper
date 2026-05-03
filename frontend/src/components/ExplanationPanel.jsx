import React from "react";

export default function ExplanationPanel({ explanation }) {
  return (
    <div className="explain">
      <div className="panelHeader">
        <h2>What this code does</h2>
      </div>
      <p className="explainText">{explanation}</p>
    </div>
  );
}
