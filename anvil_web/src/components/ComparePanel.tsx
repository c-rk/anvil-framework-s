import { useEffect, useMemo, useState } from "react";
import {
  COMPARE_EVENT,
  clearCompare,
  readCompare,
  removeCompare,
  type CompareSnapshot,
} from "../lib/compare";
import { triggerDownload } from "../lib/export";
import { fmtNum } from "../lib/numbers";

function cell(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (Array.isArray(v)) return `[${v.length}]`;
  return fmtNum(v as number | string | boolean | null);
}

/**
 * Result comparison tray. Shows every pinned solve snapshot as a column, with
 * one row per variable (union across snapshots). Persists via lib/compare.ts,
 * so it survives switching between RSQs on the Calculator page.
 */
export function ComparePanel() {
  const [snaps, setSnaps] = useState<CompareSnapshot[]>(readCompare);

  useEffect(() => {
    const refresh = () => setSnaps(readCompare());
    window.addEventListener(COMPARE_EVENT, refresh);
    return () => window.removeEventListener(COMPARE_EVENT, refresh);
  }, []);

  // Ordered union of variable names: preserve first-seen order, inputs first.
  const variables = useMemo(() => {
    const seen: string[] = [];
    const roleOf: Record<string, string> = {};
    for (const s of snaps) {
      for (const [k, rv] of Object.entries(s.results)) {
        if (!(k in roleOf)) {
          roleOf[k] = rv.role;
          seen.push(k);
        }
      }
    }
    return seen.sort((a, b) => {
      const ra = roleOf[a] === "input" ? 0 : 1;
      const rb = roleOf[b] === "input" ? 0 : 1;
      return ra - rb;
    });
  }, [snaps]);

  const unitOf = useMemo(() => {
    const u: Record<string, string> = {};
    for (const s of snaps) {
      for (const [k, rv] of Object.entries(s.results)) {
        if (rv.unit && !u[k]) u[k] = rv.unit;
      }
    }
    return u;
  }, [snaps]);

  if (snaps.length === 0) return null;

  const exportCsv = () => {
    const header = ["variable", "unit", ...snaps.map((s) => s.label)];
    const lines = [header.join(",")];
    for (const v of variables) {
      const row = [
        v,
        unitOf[v] || "",
        ...snaps.map((s) => cell(s.results[v]?.value)),
      ];
      lines.push(row.join(","));
    }
    triggerDownload("anvil_comparison.csv", lines.join("\n"), "text/csv");
  };

  return (
    <section className="compare-panel">
      <div className="compare-head">
        <h3>Comparison</h3>
        <div className="compare-actions">
          <button onClick={exportCsv} title="Export the comparison as CSV">
            Export CSV
          </button>
          <button
            className="compare-clear"
            onClick={() => setSnaps(clearCompare())}
            title="Remove all snapshots"
          >
            Clear
          </button>
        </div>
      </div>
      <div className="compare-scroll">
        <table className="compare-table">
          <thead>
            <tr>
              <th className="compare-varcol">variable</th>
              {snaps.map((s) => (
                <th key={s.id} className="compare-col">
                  <span className="compare-col-label" title={`${s.rsq} · ${s.method}`}>
                    {s.label}
                  </span>
                  <button
                    className="compare-col-x"
                    onClick={() => setSnaps(removeCompare(s.id))}
                    title={`Remove ${s.label}`}
                    aria-label={`Remove ${s.label}`}
                  >
                    ×
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {variables.map((v) => (
              <tr key={v}>
                <td className="compare-var">
                  {v}
                  {unitOf[v] && <span className="compare-unit"> {unitOf[v]}</span>}
                </td>
                {snaps.map((s) => (
                  <td key={s.id} className="compare-num">
                    {cell(s.results[v]?.value)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
