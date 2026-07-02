import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { exportResultCSV, exportResultJSON } from "../lib/export";
import type { RsqDetail, SolveInputValue, SolveResponse } from "../lib/types";
import { MathView } from "./MathView";
import { ResidualChart } from "./ResidualChart";

interface Props {
  /** RSQ name to load. The component fetches its own detail + runs solves. */
  name: string;
}

/**
 * Self-contained RSQ calculator.
 *
 * Designed to be reusable: it owns its own data fetching and state given just
 * an RSQ `name`, so it can later be dropped into a system-builder canvas as a
 * node without external wiring.
 */
export function Calculator({ name }: Props) {
  const [detail, setDetail] = useState<RsqDetail | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<SolveResponse | null>(null);
  const [solving, setSolving] = useState(false);
  const [solveErr, setSolveErr] = useState<string | null>(null);
  // Live (streaming) solve: holds the resolved inputs for the active live run.
  const [liveInputs, setLiveInputs] =
    useState<Record<string, SolveInputValue> | null>(null);

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
        // Seed the form from defaults.
        const seed: Record<string, string> = {};
        for (const inp of d.inputs) {
          seed[inp.name] =
            inp.default !== null && inp.default !== undefined
              ? String(inp.default)
              : "";
        }
        setValues(seed);
      })
      .catch((e) => !cancelled && setLoadErr(String(e.message ?? e)));
    return () => {
      cancelled = true;
    };
  }, [name]);

  const canRun = useMemo(() => {
    if (!detail) return false;
    return detail.inputs.every((inp) => values[inp.name]?.trim() !== "");
  }, [detail, values]);

  // Resolve the current form values into the /api/solve input shape.
  function buildInputs(d: RsqDetail): Record<string, SolveInputValue> {
    const inputs: Record<string, SolveInputValue> = {};
    for (const inp of d.inputs) {
      const raw = values[inp.name]?.trim() ?? "";
      const num = Number(raw);
      const scalar: number | string = raw !== "" && !Number.isNaN(num) ? num : raw;
      // Attach unit only when the metadata provides one and the value is numeric.
      if (inp.unit && typeof scalar === "number") {
        inputs[inp.name] = { value: scalar, unit: inp.unit };
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
    } catch (e: any) {
      setSolveErr(String(e.message ?? e));
    } finally {
      setSolving(false);
    }
  }

  // Coupled "S" systems iterate (gauss_seidel); offer a live streaming solve.
  const canLive = detail?.type === "S";

  function runLive() {
    if (!detail) return;
    setSolveErr(null);
    setResult(null);
    setLiveInputs(buildInputs(detail));
  }

  if (loadErr) {
    return <div className="panel error">Failed to load: {loadErr}</div>;
  }
  if (!detail) {
    return <div className="panel muted">Loading {name}…</div>;
  }

  const fmt = (v: number | string | boolean | null) => {
    if (typeof v === "number") {
      const a = Math.abs(v);
      if (v === 0) return "0";
      if (a >= 1e6 || a < 1e-3) return v.toExponential(4);
      return v.toPrecision(6).replace(/\.?0+$/, "");
    }
    return v === null ? "—" : String(v);
  };

  return (
    <section className="calculator">
      <header className="calc-header">
        <div>
          <h2>{detail.name}</h2>
          <div className="calc-sub">
            {detail.domain && <span className="chip">{detail.domain}</span>}
            <span className={`badge badge-${detail.type}`}>{detail.type}</span>
            {detail.version && <span className="muted">v{detail.version}</span>}
          </div>
        </div>
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

      <div className="calc-grid">
        <div className="calc-inputs">
          <h3>Inputs</h3>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              run();
            }}
          >
            {detail.inputs.map((inp) => (
              <label key={inp.name} className="field">
                <span className="field-name">
                  {inp.name}
                  {inp.unit && <span className="field-unit">{inp.unit}</span>}
                </span>
                <input
                  type="number"
                  step="any"
                  value={values[inp.name] ?? ""}
                  placeholder={
                    inp.default !== null ? String(inp.default) : "value"
                  }
                  onChange={(e) =>
                    setValues((v) => ({ ...v, [inp.name]: e.target.value }))
                  }
                />
                {inp.desc && <span className="field-desc">{inp.desc}</span>}
              </label>
            ))}
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
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(result.results).map(([k, rv]) => (
                    <tr key={k} className={rv.role}>
                      <td className="role">{rv.role}</td>
                      <td className="var">{k}</td>
                      <td className="num">{fmt(rv.value)}</td>
                      <td className="unit">{rv.unit || ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="export-row">
                <button onClick={() => exportResultCSV(result)}>
                  Export CSV
                </button>
                <button onClick={() => exportResultJSON(result)}>
                  Export JSON
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
