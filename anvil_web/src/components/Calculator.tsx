import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { exportResultCSV, exportResultJSON } from "../lib/export";
import { exportReportHTML, exportReportMarkdown } from "../lib/report";
import { addCompare } from "../lib/compare";
import type { RsqDetail, SolveInputValue, SolveResponse } from "../lib/types";
import { MathView } from "./MathView";
import { ResidualChart } from "./ResidualChart";
import { rsqDocsUrl, NEW_TAB } from "../lib/docs";
import { fmtNum, parseNumberArray } from "../lib/numbers";
import {
  MEMORY_EVENT,
  memoryLabel,
  pushHistory,
  readMemory,
  setMemory,
  type MemoryMap,
  type MemorySlot,
} from "../lib/memory";

interface Props {
  /** RSQ name to load. The component fetches its own detail + runs solves. */
  name: string;
}

// Heuristic: an input is "array-like" if the RSQ flags array_input AND the name
// looks like a vector/series, or the input default is itself an array.
const ARRAY_NAME = /signal|samples|series|array|vector|data|wave|spectrum|x$/i;

function isArrayInput(d: RsqDetail, inpName: string, inpDefault: unknown): boolean {
  if (Array.isArray(inpDefault)) return true;
  if (d.array_input && ARRAY_NAME.test(inpName)) return true;
  return false;
}

/**
 * Self-contained RSQ calculator with unit inputs (B2), array/time-series widgets
 * (B3), and calculator-style memory (B4). Keeps the results table, KaTeX
 * formula, CSV/JSON export, and live-solve for coupled systems (B5).
 */
export function Calculator({ name }: Props) {
  const [detail, setDetail] = useState<RsqDetail | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  // Scalar text values, per-input unit strings, and raw array text (for arrays).
  const [values, setValues] = useState<Record<string, string>>({});
  const [units, setUnits] = useState<Record<string, string>>({});
  const [arrayText, setArrayText] = useState<Record<string, string>>({});
  const [result, setResult] = useState<SolveResponse | null>(null);
  const [solving, setSolving] = useState(false);
  const [solveErr, setSolveErr] = useState<string | null>(null);
  const [liveInputs, setLiveInputs] =
    useState<Record<string, SolveInputValue> | null>(null);

  // Memory (B4) — named slots persisted in localStorage, shared with the
  // CalcPad pane via MEMORY_EVENT.
  const [memory, setMem] = useState<MemoryMap>(() => readMemory());
  useEffect(() => {
    const refresh = () => setMem(readMemory());
    window.addEventListener(MEMORY_EVENT, refresh);
    return () => window.removeEventListener(MEMORY_EVENT, refresh);
  }, []);

  // CSV helper for array inputs (B3): parse once, expose columns.
  const [csvText, setCsvText] = useState("");
  const [csvCols, setCsvCols] = useState<Record<string, number[]>>({});
  const [csvErr, setCsvErr] = useState<string | null>(null);

  // Load RSQ detail whenever the name changes.
  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setResult(null);
    setSolveErr(null);
    setLoadErr(null);
    setLiveInputs(null);
    api
      .rsq(name)
      .then((d) => {
        if (cancelled) return;
        setDetail(d);
        const seed: Record<string, string> = {};
        const seedUnits: Record<string, string> = {};
        const seedArr: Record<string, string> = {};
        for (const inp of d.inputs) {
          const def = inp.default;
          if (Array.isArray(def)) {
            seedArr[inp.name] = (def as unknown[]).join(", ");
          } else {
            seed[inp.name] =
              def !== null && def !== undefined ? String(def) : "";
          }
          seedUnits[inp.name] = inp.unit ?? "";
        }
        setValues(seed);
        setUnits(seedUnits);
        setArrayText(seedArr);
      })
      .catch((e) => !cancelled && setLoadErr(String(e.message ?? e)));
    return () => {
      cancelled = true;
    };
  }, [name]);

  const arrayInputs = useMemo(() => {
    if (!detail) return new Set<string>();
    const s = new Set<string>();
    for (const inp of detail.inputs) {
      if (isArrayInput(detail, inp.name, inp.default)) s.add(inp.name);
    }
    return s;
  }, [detail]);

  const canRun = useMemo(() => {
    if (!detail) return false;
    return detail.inputs.every((inp) => {
      if (arrayInputs.has(inp.name)) {
        return parseNumberArray(arrayText[inp.name] ?? "").length > 0;
      }
      return (values[inp.name]?.trim() ?? "") !== "";
    });
  }, [detail, values, arrayText, arrayInputs]);

  // Resolve the form into the /api/solve input shape, attaching units (B2).
  function buildInputs(d: RsqDetail): Record<string, SolveInputValue> {
    const inputs: Record<string, SolveInputValue> = {};
    for (const inp of d.inputs) {
      const unit = (units[inp.name] ?? "").trim();
      if (arrayInputs.has(inp.name)) {
        const arr = parseNumberArray(arrayText[inp.name] ?? "");
        inputs[inp.name] = unit ? { value: arr, unit } : arr;
        continue;
      }
      const raw = values[inp.name]?.trim() ?? "";
      const num = Number(raw);
      const scalar: number | string = raw !== "" && !Number.isNaN(num) ? num : raw;
      if (unit && typeof scalar === "number") {
        inputs[inp.name] = { value: scalar, unit };
      } else {
        inputs[inp.name] = scalar;
      }
    }
    return inputs;
  }

  async function run() {
    if (!detail) return;
    setSolving(true);
    setSolveErr(null);
    setLiveInputs(null);
    try {
      const res = await api.solve(detail.name, buildInputs(detail));
      setResult(res);
      // Auto-log scalar outputs into the shared history pane.
      const items = Object.entries(res.results)
        .filter(([, rv]) => rv.role === "output" && typeof rv.value === "number")
        .map(([k, rv]) => ({
          name: k,
          value: rv.value as number,
          unit: rv.unit || "",
        }));
      if (items.length) {
        pushHistory({ kind: "solve", label: detail.name, items, t: Date.now() });
      }
    } catch (e: any) {
      setSolveErr(String(e.message ?? e));
    } finally {
      setSolving(false);
    }
  }

  const canLive = detail?.type === "S";

  function runLive() {
    if (!detail) return;
    setSolveErr(null);
    setResult(null);
    setLiveInputs(buildInputs(detail));
  }

  // ---- memory ops ----
  function memStoreScalar(slotName: string, value: number, unit: string) {
    setMem(setMemory(slotName, { kind: "scalar", value, unit }));
  }
  function memStoreArray(slotName: string, vals: number[]) {
    setMem(setMemory(slotName, { kind: "array", values: vals }));
  }
  function recallInto(inpName: string, slot: MemorySlot) {
    if (slot.kind === "scalar") {
      setValues((v) => ({ ...v, [inpName]: String(slot.value) }));
      if (slot.unit) setUnits((u) => ({ ...u, [inpName]: slot.unit }));
    } else {
      setArrayText((a) => ({ ...a, [inpName]: slot.values.join(", ") }));
    }
  }

  async function parseCsv() {
    setCsvErr(null);
    try {
      const res = await api.csv(csvText);
      const cols: Record<string, number[]> = {};
      for (const c of res.columns) {
        const arr = (res.data[c] ?? []).filter(
          (v): v is number => typeof v === "number" && Number.isFinite(v),
        );
        if (arr.length) cols[c] = arr;
      }
      setCsvCols(cols);
      if (Object.keys(cols).length === 0) setCsvErr("No numeric columns found.");
    } catch (e: any) {
      setCsvErr(String(e?.message ?? e));
    }
  }

  if (loadErr) {
    return <div className="panel error">Failed to load: {loadErr}</div>;
  }
  if (!detail) {
    return <div className="panel muted">Loading {name}…</div>;
  }

  const memNames = Object.keys(memory);
  const csvColNames = Object.keys(csvCols);

  return (
    <section className="calculator">
      <header className="calc-header">
        <div>
          <h2 className="calc-title">{detail.name}</h2>
          <div className="calc-sub">
            {detail.domain && <span className="chip">{detail.domain}</span>}
            <span className={`badge badge-${detail.type}`}>{detail.type}</span>
            {detail.array_input && <span className="chip">array</span>}
            {detail.version && <span className="muted">v{detail.version}</span>}
          </div>
        </div>
        <a
          className="ghost-btn calc-doc-link"
          href={rsqDocsUrl(detail.name)}
          {...NEW_TAB}
          title={`Open docs for ${detail.name} in a new tab`}
        >
          Docs ↗
        </a>
      </header>

      {detail.description && <p className="calc-desc">{detail.description}</p>}

      <div className="calc-formula">
        <MathView latex={detail.latex} fallback={detail.signature} />
        {!detail.latex && (
          <span className="formula-note">
            no LaTeX metadata — showing Python signature
          </span>
        )}
      </div>

      {arrayInputs.size > 0 && (
        <details className="calc-csv">
          <summary>CSV column source (for array inputs)</summary>
          <textarea
            className="calc-csv-text nodrag"
            placeholder="Paste CSV here (header row + numeric columns)…"
            value={csvText}
            onChange={(e) => setCsvText(e.target.value)}
            rows={4}
          />
          <div className="run-row">
            <button className="run-btn" onClick={parseCsv} disabled={!csvText.trim()}>
              Parse CSV
            </button>
            {csvColNames.length > 0 && (
              <span className="muted">
                columns: {csvColNames.join(", ")}
              </span>
            )}
          </div>
          {csvErr && <div className="panel error">{csvErr}</div>}
        </details>
      )}

      <div className="calc-grid">
        <div className="calc-inputs">
          <h3>Inputs</h3>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              run();
            }}
          >
            {detail.inputs.map((inp) => {
              const isArr = arrayInputs.has(inp.name);
              return (
                <label key={inp.name} className="field">
                  <span className="field-name">
                    <span className="field-name-id">{inp.name}</span>
                    {isArr && <span className="field-unit">array</span>}
                  </span>

                  {isArr ? (
                    <>
                      <textarea
                        className="field-array"
                        rows={2}
                        value={arrayText[inp.name] ?? ""}
                        placeholder="comma / space / newline separated numbers"
                        onChange={(e) =>
                          setArrayText((a) => ({ ...a, [inp.name]: e.target.value }))
                        }
                        aria-label={`${inp.name} array`}
                      />
                      <span className="field-array-count">
                        {parseNumberArray(arrayText[inp.name] ?? "").length} values
                      </span>
                      <div className="field-ref-row">
                        {csvColNames.length > 0 && (
                          <select
                            className="field-ref nodrag"
                            value=""
                            onChange={(e) => {
                              const col = e.target.value;
                              if (col && csvCols[col])
                                setArrayText((a) => ({
                                  ...a,
                                  [inp.name]: csvCols[col].join(", "),
                                }));
                            }}
                            aria-label="Use CSV column"
                          >
                            <option value="">CSV column…</option>
                            {csvColNames.map((c) => (
                              <option key={c} value={c}>
                                {c} ({csvCols[c].length})
                              </option>
                            ))}
                          </select>
                        )}
                        {memNames.length > 0 && (
                          <select
                            className="field-ref nodrag"
                            value=""
                            onChange={(e) => {
                              const slot = memory[e.target.value];
                              if (slot) recallInto(inp.name, slot);
                            }}
                            aria-label="Recall memory"
                          >
                            <option value="">memory…</option>
                            {memNames.map((m) => (
                              <option key={m} value={m}>
                                {m} {memoryLabel(memory[m])}
                              </option>
                            ))}
                          </select>
                        )}
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="field-valrow">
                        <input
                          type="text"
                          inputMode="decimal"
                          value={values[inp.name] ?? ""}
                          placeholder={
                            inp.default !== null ? String(inp.default) : "value"
                          }
                          onChange={(e) =>
                            setValues((v) => ({ ...v, [inp.name]: e.target.value }))
                          }
                        />
                        <input
                          className="field-unit-input nodrag"
                          type="text"
                          value={units[inp.name] ?? ""}
                          placeholder="unit"
                          onChange={(e) =>
                            setUnits((u) => ({ ...u, [inp.name]: e.target.value }))
                          }
                          aria-label={`${inp.name} unit`}
                          title="Unit sent as {value, unit}"
                        />
                      </div>
                      {memNames.length > 0 && (
                        <select
                          className="field-ref nodrag"
                          value=""
                          onChange={(e) => {
                            const slot = memory[e.target.value];
                            if (slot) recallInto(inp.name, slot);
                          }}
                          aria-label="Recall memory"
                        >
                          <option value="">recall memory…</option>
                          {memNames.map((m) => (
                            <option key={m} value={m}>
                              {m} {memoryLabel(memory[m])}
                            </option>
                          ))}
                        </select>
                      )}
                    </>
                  )}
                  {inp.desc && <span className="field-desc">{inp.desc}</span>}
                </label>
              );
            })}
            {detail.inputs.length === 0 && (
              <p className="muted">This RSQ takes no inputs.</p>
            )}
            <div className="run-row">
              <button
                type="submit"
                className="run-btn"
                disabled={!canRun || solving}
              >
                {solving ? "Running…" : "Run"}
              </button>
              {canLive && (
                <button
                  type="button"
                  className="run-btn live-btn"
                  disabled={!canRun}
                  onClick={runLive}
                  title="Stream solver residuals live over a WebSocket"
                >
                  Solve (live)
                </button>
              )}
            </div>
          </form>
        </div>

        <div className="calc-results">
          <h3>Results</h3>
          {solveErr && <div className="panel error">{solveErr}</div>}
          {liveInputs && (
            <ResidualChart
              name={detail.name}
              inputs={liveInputs}
              onDone={() => {}}
            />
          )}
          {!result && !solveErr && !liveInputs && (
            <p className="muted">Run the RSQ to see results.</p>
          )}
          {result && (
            <>
              <div className="method-line">
                solver method: <code>{result.method || "—"}</code>
              </div>
              <table className="result-table">
                <thead>
                  <tr>
                    <th>role</th>
                    <th>variable</th>
                    <th className="num">value</th>
                    <th>unit</th>
                    <th>M+</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(result.results).map(([k, rv]) => (
                    <tr key={k} className={rv.role}>
                      <td className="role">{rv.role}</td>
                      <td className="var">{k}</td>
                      <td className="num">{fmtValue(rv.value)}</td>
                      <td className="unit">{rv.unit || ""}</td>
                      <td>
                        <button
                          className="mem-store-btn"
                          title={`Store ${k} into a memory slot`}
                          onClick={() => {
                            const slotName = window.prompt(
                              `Store ${k} into memory slot named:`,
                              k,
                            );
                            if (!slotName) return;
                            if (Array.isArray(rv.value)) {
                              memStoreArray(
                                slotName,
                                (rv.value as unknown[]).filter(
                                  (n): n is number => typeof n === "number",
                                ),
                              );
                            } else if (typeof rv.value === "number") {
                              memStoreScalar(slotName, rv.value, rv.unit || "");
                            }
                          }}
                        >
                          M+
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="export-row">
                <button
                  className="compare-add"
                  onClick={() => addCompare(result)}
                  title="Add this result to the comparison tray below"
                >
                  + Compare
                </button>
                <button onClick={() => exportResultCSV(result)}>Export CSV</button>
                <button onClick={() => exportResultJSON(result)}>Export JSON</button>
                <button onClick={() => exportReportHTML(detail, result)} title="Download a self-contained HTML report">
                  Report HTML
                </button>
                <button onClick={() => exportReportMarkdown(detail, result)} title="Download a Markdown report">
                  Report MD
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}

/** Format a possibly-array result value for the table. */
function fmtValue(v: unknown): string {
  if (Array.isArray(v)) {
    const head = v.slice(0, 4).map((x) => fmtNum(x as number));
    return `[${head.join(", ")}${v.length > 4 ? `, … ${v.length}` : ""}]`;
  }
  return fmtNum(v as number | string | boolean | null);
}

