import { AlertTriangle, Box, Download, Ruler } from "lucide-react";

import type { DesignResponse, PartRequest, ValidationIssue } from "../api/types";

interface ResultPanelProps {
  result: DesignResponse | null;
  error: string | null;
}

const PARAMETER_LABELS: Record<keyof PartRequest, string> = {
  part_type: "Part type",
  source_prompt: "Source prompt",
  rows: "Rows",
  cols: "Columns",
  well_count: "Well count",
  diameter_mm: "Diameter",
  spacing_mm: "Spacing",
  depth_mm: "Depth",
  well_width_mm: "Well width",
  well_height_mm: "Well height",
  tube_volume_ml: "Tube volume",
  notes: "Notes"
};

const PARAMETER_UNITS: Partial<Record<keyof PartRequest, string>> = {
  diameter_mm: "mm",
  spacing_mm: "mm",
  depth_mm: "mm",
  well_width_mm: "mm",
  well_height_mm: "mm",
  tube_volume_ml: "mL"
};

export function ResultPanel({ result, error }: ResultPanelProps) {
  if (error) {
    return (
      <section className="workspace-pane result-pane" aria-live="polite">
        <div className="empty-state error-state">
          <AlertTriangle size={28} />
          <p>{error}</p>
        </div>
      </section>
    );
  }

  if (!result) {
    return (
      <section className="workspace-pane result-pane" aria-live="polite">
        <div className="empty-state">
          <Box size={30} />
          <p>Generated parameters, manufacturability checks, and export targets will appear here.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="workspace-pane result-pane" aria-live="polite">
      <div className="result-header">
        <div>
          <p className="eyebrow">Selected template</p>
          <h2>{result.template.name}</h2>
        </div>
        <span className="status-pill">{result.part_request.part_type.replace(/_/g, " ")}</span>
      </div>

      <p className="template-description">{result.template.description}</p>

      <div className="result-grid">
        <section className="result-section" aria-labelledby="parameters-title">
          <h3 id="parameters-title">Parameters</h3>
          <dl className="parameter-list">{renderParameters(result.part_request)}</dl>
        </section>

        <section className="result-section" aria-labelledby="validation-title">
          <h3 id="validation-title">Validation</h3>
          <ValidationList issues={result.validation} />
        </section>
      </div>

      {result.estimated_dimensions ? (
        <section className="result-section" aria-labelledby="dimensions-title">
          <h3 id="dimensions-title">
            <Ruler size={18} />
            Estimated dimensions
          </h3>
          <div className="dimension-strip">
            <span>{result.estimated_dimensions.width_mm.toFixed(1)} mm wide</span>
            <span>{result.estimated_dimensions.depth_mm.toFixed(1)} mm deep</span>
            <span>{result.estimated_dimensions.height_mm.toFixed(1)} mm high</span>
          </div>
        </section>
      ) : null}

      <section className="result-section" aria-labelledby="exports-title">
        <h3 id="exports-title">
          <Download size={18} />
          Exports
        </h3>
        <div className="export-list">
          {result.exports.map((file) => (
            <div className="export-row" key={file.filename}>
              <div>
                <strong>{file.filename}</strong>
                <p>{file.message}</p>
              </div>
              <span data-status={file.status}>{file.status}</span>
            </div>
          ))}
        </div>
      </section>
    </section>
  );
}

function renderParameters(partRequest: PartRequest) {
  return (Object.entries(partRequest) as [keyof PartRequest, PartRequest[keyof PartRequest]][])
    .filter(([key, value]) => {
      if (key === "source_prompt" || value === null || value === undefined) {
        return false;
      }
      return !Array.isArray(value) || value.length > 0;
    })
    .map(([key, value]) => {
      const renderedValue = Array.isArray(value) ? value.join("; ") || "None" : String(value);
      const unit = PARAMETER_UNITS[key] ? ` ${PARAMETER_UNITS[key]}` : "";
      return (
        <div className="parameter-row" key={key}>
          <dt>{PARAMETER_LABELS[key]}</dt>
          <dd>
            {renderedValue}
            {unit}
          </dd>
        </div>
      );
    });
}

function ValidationList({ issues }: { issues: ValidationIssue[] }) {
  if (issues.length === 0) {
    return <p className="quiet-copy">No validation issues found.</p>;
  }

  return (
    <ul className="validation-list">
      {issues.map((issue) => (
        <li data-severity={issue.severity} key={`${issue.code}-${issue.field ?? "global"}`}>
          <strong>{issue.severity}</strong>
          <span>{issue.message}</span>
        </li>
      ))}
    </ul>
  );
}
