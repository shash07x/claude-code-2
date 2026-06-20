"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import {
  ApiError,
  importsApi,
  type ImportCommitResponse,
  type ImportPreviewResponse,
  type ImportSource,
  type IssuePriority,
  type IssueStatus,
} from "@/lib/api";

const STATUS_LABEL: Record<IssueStatus, string> = {
  backlog: "Backlog",
  review: "Review",
  in_progress: "In Progress",
  done: "Done",
};

const PRIORITY_LABEL: Record<IssuePriority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  urgent: "Urgent",
};

const SOURCE_LABEL: Record<ImportSource, string> = {
  jira: "Jira",
  linear: "Linear",
  trello: "Trello",
};

type SourceChoice = "auto" | ImportSource;

export function CsvImporter() {
  const [csvText, setCsvText] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const [source, setSource] = useState<SourceChoice>("auto");

  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [result, setResult] = useState<ImportCommitResponse | null>(null);

  const [loading, setLoading] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  function resetOutputs() {
    setPreview(null);
    setResult(null);
    setError(null);
  }

  function onFile(file: File) {
    const reader = new FileReader();
    reader.onload = () => {
      setCsvText(String(reader.result ?? ""));
      setFileName(file.name);
      resetOutputs();
    };
    reader.onerror = () => setError("Couldn't read that file.");
    reader.readAsText(file);
  }

  async function onPreview() {
    if (!csvText.trim()) {
      setError("Add a CSV file or paste CSV text first.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await importsApi.preview(
        csvText,
        source === "auto" ? null : source
      );
      setPreview(res);
    } catch (err) {
      setPreview(null);
      setError(
        err instanceof ApiError ? err.message : "Preview failed. Try again."
      );
    } finally {
      setLoading(false);
    }
  }

  async function onImport() {
    if (!preview || preview.valid_rows === 0) return;
    setCommitting(true);
    setError(null);
    try {
      const res = await importsApi.commit(
        csvText,
        source === "auto" ? null : source
      );
      setResult(res);
      setPreview(null);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Import failed. Try again."
      );
    } finally {
      setCommitting(false);
    }
  }

  function onClear() {
    setCsvText("");
    setFileName(null);
    resetOutputs();
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  return (
    <div className="import-shell">
      {/* Step 1 — input ---------------------------------------------------- */}
      <div className="card import-card">
        <h2 className="import-step-title">1 · Choose a file</h2>
        <p className="import-hint">
          Export your board to CSV from Jira, Linear, or Trello, then upload it
          here. We map each row onto a TeamSync card&apos;s title, description,
          status, and priority — anything else is listed as dropped before you
          commit.
        </p>

        <div className="import-controls">
          <label className="import-file">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onFile(f);
              }}
            />
            <span>{fileName ?? "Choose CSV…"}</span>
          </label>

          <label className="import-source">
            Format
            <select
              value={source}
              onChange={(e) => {
                setSource(e.target.value as SourceChoice);
                resetOutputs();
              }}
            >
              <option value="auto">Auto-detect</option>
              <option value="jira">Jira</option>
              <option value="linear">Linear</option>
              <option value="trello">Trello</option>
            </select>
          </label>
        </div>

        <details className="import-paste">
          <summary>…or paste CSV directly</summary>
          <textarea
            value={csvText}
            placeholder="Paste CSV content (including the header row)…"
            onChange={(e) => {
              setCsvText(e.target.value);
              setFileName(null);
              resetOutputs();
            }}
            rows={6}
          />
        </details>

        <div className="import-actions">
          <button
            className="primary import-preview-btn"
            onClick={onPreview}
            disabled={loading || !csvText.trim()}
          >
            {loading ? "Reading…" : "Preview import"}
          </button>
          {(csvText || preview || result) && (
            <button className="ghost" onClick={onClear} disabled={committing}>
              Clear
            </button>
          )}
        </div>

        {error && <div className="alert error import-alert">{error}</div>}
      </div>

      {/* Step 3 — success -------------------------------------------------- */}
      {result && (
        <div className="card import-card">
          <div className="alert success import-alert">
            Imported <strong>{result.imported}</strong>{" "}
            {result.imported === 1 ? "card" : "cards"} from{" "}
            {SOURCE_LABEL[result.source]}
            {result.skipped > 0 && <> · skipped {result.skipped} invalid</>}.
          </div>
          <Link href="/board" className="board-cta">
            View them on the Sprint Board →
          </Link>
        </div>
      )}

      {/* Step 2 — preview -------------------------------------------------- */}
      {preview && (
        <div className="card import-card">
          <h2 className="import-step-title">2 · Review &amp; confirm</h2>

          <div className="import-summary">
            <span className="import-chip">
              {preview.detected ? "Detected" : "Format"}:{" "}
              <strong>{SOURCE_LABEL[preview.source]}</strong>
            </span>
            <span className="import-chip import-chip--ok">
              {preview.valid_rows} ready
            </span>
            {preview.invalid_rows > 0 && (
              <span className="import-chip import-chip--bad">
                {preview.invalid_rows} skipped
              </span>
            )}
          </div>

          {preview.unmapped_columns.length > 0 && (
            <div className="import-dropped">
              <strong>Columns dropped</strong> (no field in TeamSync):{" "}
              {preview.unmapped_columns.join(", ")}
            </div>
          )}

          <div className="import-table-wrap">
            <table className="import-table">
              <thead>
                <tr>
                  <th className="import-col-row">#</th>
                  <th>Title</th>
                  <th className="import-col-tag">Status</th>
                  <th className="import-col-tag">Priority</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row) => (
                  <tr
                    key={row.row_number}
                    className={row.valid ? "" : "import-row--invalid"}
                  >
                    <td className="import-col-row">{row.row_number}</td>
                    <td className="import-cell-title">
                      {row.title || (
                        <span className="import-missing">— missing —</span>
                      )}
                    </td>
                    <td>
                      <span className="import-tag">
                        {STATUS_LABEL[row.status]}
                      </span>
                    </td>
                    <td>
                      <span className={`prio prio--${row.priority}`}>
                        {PRIORITY_LABEL[row.priority]}
                      </span>
                    </td>
                    <td className="import-notes">
                      {row.errors.map((e, i) => (
                        <span key={`e${i}`} className="import-note import-note--err">
                          {e}
                        </span>
                      ))}
                      {row.warnings.map((w, i) => (
                        <span key={`w${i}`} className="import-note import-note--warn">
                          {w}
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="import-actions">
            <button
              className="primary"
              onClick={onImport}
              disabled={committing || preview.valid_rows === 0}
            >
              {committing
                ? "Importing…"
                : `Import ${preview.valid_rows} ${
                    preview.valid_rows === 1 ? "card" : "cards"
                  }`}
            </button>
            {preview.valid_rows === 0 && (
              <span className="import-hint">
                Nothing to import — every row is missing a title.
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
