import { useEffect, useMemo, useRef, useState } from "react";
import { api, solveSystemLive } from "../lib/api";
import type {
  SystemSolveRequest,
  SystemSolveResponse,
  SystemWsFrame,
} from "../lib/types";
import { LineChart, type Series } from "./LineChart";

interface Props {
  request: SystemSolveRequest;
  /** When false, use the non-streaming POST /api/system/solve fallback. */
  live: boolean;
  onDone?: () => void;
  /** Fired with the final solved results (for the canvas post-pass). */
  onResult?: (results: SystemSolveResponse["results"]) => void;
}

interface IterPoint {
  iter: number;
  residual: number;
  variables?: Record<string, number>;
}

const fmt = (v: number | string | boolean | null): string => {
  if (typeof v === "number") {
    const a = Math.abs(v);
    if (v === 0) return "0";
    if (a >= 1e6 || a < 1e-3) return v.toExponential(4);
    return v.toPrecision(6).replace(/\.?0+$/, "");
  }
  return v === null ? "—" : String(v);
};

/**
 * Runs a System solve (live over WS, or one-shot via POST) and renders:
 *   - a live log-y residual convergence chart,
 *   - a results table (values + units + input/output role),
 *   - a variable-trace plot when the stream includes per-iteration `variables`.
 */
export function SystemSolvePanel({ request, live, onDone, onResult }: Props) {
  const [points, setPoints] = useState<IterPoint[]>([]);
  const [result, setResult] = useState<SystemSolveResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(true);
  const [traceVar, setTraceVar] = useState<string | null>(null);
  const handleRef = useRef<{ close: () => void } | null>(null);

  const reqKey = JSON.stringify(request);

  useEffect(() => {
    setPoints([]);
    setResult(null);
    setError(null);
    setRunning(true);
    let cancelled = false;
    let gotResult = false;

    const runPost = (note?: string) => {
      api
        .solveSystem(request)
        .then((res) => {
          if (cancelled) return;
          gotResult = true;
          setError(null);
          setResult(res);
          onResult?.(res.results);
          setPoints(
            (res.history ?? []).map((h) => ({
              iter: h.iter,
              residual: h.residual,
            })),
          );
          if (note) console.info(note);
        })
        .catch((e) => {
          if (!cancelled) setError(String(e?.message ?? e));
        })
        .finally(() => {
          if (!cancelled) {
            setRunning(false);
            onDone?.();
          }
        });
    };

    if (live) {
      const handle = solveSystemLive(
        request,
        (frame: SystemWsFrame) => {
          if (cancelled) return;
          if (frame.type === "iter") {
            setPoints((ps) => [
              ...ps,
              {
                iter: frame.iter,
                residual: frame.residual,
                variables: frame.variables,
              },
            ]);
          } else if (frame.type === "result") {
            gotResult = true;
            setResult(frame);
            onResult?.(frame.results);
            if (frame.history?.length) {
              // Backfill residual history if the stream was sparse.
              setPoints((ps) =>
                ps.length >= frame.history.length
                  ? ps
                  : frame.history.map((h) => ({
                      iter: h.iter,
                      residual: h.residual,
                    })),
              );
            }
          } else if (frame.type === "error") {
            setError(frame.message);
          }
        },
        (err) => {
          if (cancelled) return;
          // Connection-level failure with no result and no solver error
          // -> transparently retry over plain HTTP rather than dying.
          const isConnErr = err === "WebSocket connection error";
          if (!gotResult && (isConnErr || (!err && !gotResult))) {
            runPost("live stream unavailable; solved via HTTP fallback");
            return;
          }
          setRunning(false);
          if (err && !gotResult) setError((e) => e ?? err);
          onDone?.();
        },
      );
      handleRef.current = handle;
      return () => {
        cancelled = true;
        handle.close();
      };
    }

    runPost();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reqKey, live]);

  const residualSeries: Series[] = useMemo(
    () => [
      {
        label: "residual",
        points: points.map((p) => [p.iter, p.residual] as [number, number]),
      },
    ],
    [points],
  );

  // Variables available for the trace plot (from streamed snapshots).
  const traceVars = useMemo(() => {
    const set = new Set<string>();
    for (const p of points) {
      if (p.variables) for (const k of Object.keys(p.variables)) set.add(k);
    }
    return [...set].sort();
  }, [points]);

  useEffect(() => {
    if (!traceVar && traceVars.length) setTraceVar(traceVars[0]);
  }, [traceVars, traceVar]);

  const traceSeries: Series[] = useMemo(() => {
    if (!traceVar) return [];
    const pts: [number, number][] = [];
    for (const p of points) {
      const v = p.variables?.[traceVar];
      if (typeof v === "number") pts.push([p.iter, v]);
    }
    return pts.length ? [{ label: traceVar, points: pts }] : [];
  }, [points, traceVar]);

  return (
    <div className="sys-solve">
      <div className="residual-head">
        <span className="residual-title">
          {live ? "Live residuals" : "Residuals"}
        </span>
        {running ? (
          <span className="residual-status running">
            solving… iter {points.length}
          </span>
        ) : error ? (
          <span className="residual-status err">error</span>
        ) : (
          <span className="residual-status ok">
            converged in {points.length} iteration
            {points.length === 1 ? "" : "s"}
          </span>
        )}
      </div>

      <LineChart series={residualSeries} logY xLabel="iteration" yLabel="‖r‖" />

      {error && <div className="panel error residual-err">{error}</div>}

      {traceVars.length > 0 && (
        <div className="trace-block">
          <div className="trace-head">
            <span className="residual-title">Variable trace</span>
            <select
              className="trace-select nodrag"
              value={traceVar ?? ""}
              onChange={(e) => setTraceVar(e.target.value)}
            >
              {traceVars.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </div>
          <LineChart
            series={traceSeries}
            xLabel="iteration"
            yLabel={traceVar ?? "value"}
          />
        </div>
      )}

      {result && (
        <div className="residual-result">
          <div className="method-line">
            method: <code>{result.method || "—"}</code>
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
        </div>
      )}
    </div>
  );
}
