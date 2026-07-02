import { useEffect, useMemo, useRef, useState } from "react";
import { solveLive } from "../lib/api";
import type {
  SolveInputValue,
  SolveResponse,
  WsFrame,
} from "../lib/types";

interface Props {
  /** RSQ name to solve live. */
  name: string;
  /** Resolved inputs (same shape posted to /api/solve). */
  inputs: Record<string, SolveInputValue>;
  /** Optional explicit solver method. */
  method?: string;
  /** Fired when the live solve ends (so the parent can clear its busy state). */
  onDone?: () => void;
}

interface IterPoint {
  iter: number;
  residual: number;
}

/**
 * Live residual chart. Opens a WebSocket to /ws/solve, streams per-iteration
 * residuals, and plots them on a log-y axis as frames arrive, then shows the
 * final result. Self-contained inline SVG — no charting dependency.
 */
export function ResidualChart({ name, inputs, method, onDone }: Props) {
  const [points, setPoints] = useState<IterPoint[]>([]);
  const [result, setResult] = useState<SolveResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(true);
  const handleRef = useRef<{ close: () => void } | null>(null);

  useEffect(() => {
    setPoints([]);
    setResult(null);
    setError(null);
    setRunning(true);

    const handle = solveLive(
      { name, inputs, method },
      (frame: WsFrame) => {
        if (frame.type === "iter") {
          setPoints((ps) => [...ps, { iter: frame.iter, residual: frame.residual }]);
        } else if (frame.type === "result") {
          setResult(frame);
        } else if (frame.type === "error") {
          setError(frame.message);
        }
      },
      (err) => {
        setRunning(false);
        if (err) setError((e) => e ?? err);
        onDone?.();
      },
    );
    handleRef.current = handle;
    return () => handle.close();
    // Re-run only when the target solve changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name, JSON.stringify(inputs), method]);

  const directNote = !running && result && points.length <= 1;

  return (
    <div className="residual-chart">
      <div className="residual-head">
        <span className="residual-title">Live residuals</span>
        {running ? (
          <span className="residual-status running">streaming… iter {points.length}</span>
        ) : error ? (
          <span className="residual-status err">error</span>
        ) : (
          <span className="residual-status ok">
            {directNote
              ? "converged in 1 step / direct"
              : `converged in ${points.length} iterations`}
          </span>
        )}
      </div>

      <Chart points={points} />

      {error && <div className="panel error residual-err">{error}</div>}

      {result && (
        <div className="residual-result">
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
        </div>
      )}
    </div>
  );
}

function fmt(v: number | string | boolean | null): string {
  if (typeof v === "number") {
    const a = Math.abs(v);
    if (v === 0) return "0";
    if (a >= 1e6 || a < 1e-3) return v.toExponential(4);
    return v.toPrecision(6).replace(/\.?0+$/, "");
  }
  return v === null ? "—" : String(v);
}

/** Inline SVG log-y residual-vs-iteration plot. */
function Chart({ points }: { points: IterPoint[] }) {
  const W = 560;
  const H = 200;
  const padL = 52;
  const padR = 12;
  const padT = 12;
  const padB = 26;

  const { path, valid, yTicks, xTicks, sx, sy } = useMemo(() => {
    const valid = points.filter((p) => Number.isFinite(p.residual) && p.residual > 0);
    const logs = valid.map((p) => Math.log10(p.residual));
    let yMin = logs.length ? Math.min(...logs) : -1;
    let yMax = logs.length ? Math.max(...logs) : 0;
    if (yMax - yMin < 1e-9) {
      yMin -= 1;
      yMax += 1;
    }
    const xMax = Math.max(1, ...valid.map((p) => p.iter));

    const sx = (iter: number) => padL + (iter / xMax) * (W - padL - padR);
    const sy = (res: number) => {
      const t = (Math.log10(res) - yMin) / (yMax - yMin);
      return padT + (1 - t) * (H - padT - padB);
    };

    const path = valid
      .map((p, i) => `${i === 0 ? "M" : "L"}${sx(p.iter).toFixed(1)},${sy(p.residual).toFixed(1)}`)
      .join(" ");

    const yTicks: { y: number; label: string }[] = [];
    for (let e = Math.floor(yMin); e <= Math.ceil(yMax); e++) {
      yTicks.push({ y: sy(Math.pow(10, e)), label: `1e${e}` });
    }

    const xTickN = Math.min(6, xMax + 1);
    const xTicks = Array.from({ length: xTickN }, (_, i) => {
      const it = Math.round((i / (xTickN - 1 || 1)) * xMax);
      return { x: sx(it), label: String(it) };
    });

    return { path, valid, yTicks, xTicks, sx, sy };
  }, [points]);

  return (
    <svg
      className="residual-svg"
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="Residual versus iteration (log scale)"
    >
      {/* gridlines + y labels */}
      {yTicks.map((t, i) => (
        <g key={`y${i}`}>
          <line
            x1={padL}
            x2={W - padR}
            y1={t.y}
            y2={t.y}
            className="residual-grid"
          />
          <text x={padL - 6} y={t.y + 3} className="residual-axis-label" textAnchor="end">
            {t.label}
          </text>
        </g>
      ))}
      {/* x labels */}
      {xTicks.map((t, i) => (
        <text
          key={`x${i}`}
          x={t.x}
          y={H - 8}
          className="residual-axis-label"
          textAnchor="middle"
        >
          {t.label}
        </text>
      ))}
      {/* axes */}
      <line x1={padL} x2={padL} y1={padT} y2={H - padB} className="residual-axis" />
      <line x1={padL} x2={W - padR} y1={H - padB} y2={H - padB} className="residual-axis" />
      {/* residual trace */}
      {path && <path d={path} className="residual-line" fill="none" />}
      {valid.map((p, i) => (
        <circle key={i} cx={sx(p.iter)} cy={sy(p.residual)} r={2.2} className="residual-dot" />
      ))}
      {valid.length === 0 && (
        <text x={W / 2} y={H / 2} className="residual-axis-label" textAnchor="middle">
          waiting for iterations…
        </text>
      )}
    </svg>
  );
}
