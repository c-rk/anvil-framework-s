import { useMemo } from "react";

export interface Series {
  label: string;
  /** [x, y] points; non-finite y values are skipped. */
  points: [number, number][];
}

interface Props {
  series: Series[];
  xLabel?: string;
  yLabel?: string;
  title?: string;
  /** Use a log-y axis (decade gridlines). Values <= 0 are skipped. */
  logY?: boolean;
  height?: number;
}

// Monochrome chart palette (greys), driven by theme variables.
const PALETTE = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
];

/**
 * Reusable, theme-aware inline-SVG line chart. Linear or log-y. Used for the
 * sweep plot and the variable-trace plot. Axis labels render in mono (via the
 * `.line-axis-label` rule), titles in serif. Responsive via viewBox.
 */
export function LineChart({
  series,
  xLabel,
  yLabel,
  title,
  logY = false,
  height = 220,
}: Props) {
  const W = 600;
  const H = height;
  const padL = 58;
  const padR = 14;
  const padT = title ? 26 : 12;
  const padB = 40;

  const model = useMemo(() => {
    const all: [number, number][] = [];
    for (const s of series) {
      for (const [x, y] of s.points) {
        if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
        if (logY && y <= 0) continue;
        all.push([x, y]);
      }
    }
    if (all.length === 0) {
      return null;
    }
    const xs = all.map((p) => p[0]);
    const ys = all.map((p) => p[1]);
    let xMin = Math.min(...xs);
    let xMax = Math.max(...xs);
    if (xMax - xMin < 1e-12) {
      xMin -= 1;
      xMax += 1;
    }

    const toYBasis = (v: number) => (logY ? Math.log10(v) : v);
    let yMin = Math.min(...ys.map(toYBasis));
    let yMax = Math.max(...ys.map(toYBasis));
    if (yMax - yMin < 1e-12) {
      yMin -= 1;
      yMax += 1;
    }

    const sx = (x: number) =>
      padL + ((x - xMin) / (xMax - xMin)) * (W - padL - padR);
    const sy = (y: number) => {
      const b = toYBasis(y);
      const t = (b - yMin) / (yMax - yMin);
      return padT + (1 - t) * (H - padT - padB);
    };

    const paths = series.map((s) => {
      const pts = s.points
        .filter(
          ([x, y]) =>
            Number.isFinite(x) && Number.isFinite(y) && (!logY || y > 0),
        )
        .sort((a, b) => a[0] - b[0]);
      const d = pts
        .map(
          (p, i) =>
            `${i === 0 ? "M" : "L"}${sx(p[0]).toFixed(1)},${sy(p[1]).toFixed(1)}`,
        )
        .join(" ");
      return { d, pts: pts.map((p) => [sx(p[0]), sy(p[1])] as [number, number]) };
    });

    // y ticks
    const yTicks: { y: number; label: string }[] = [];
    if (logY) {
      for (let e = Math.floor(yMin); e <= Math.ceil(yMax); e++) {
        yTicks.push({ y: sy(Math.pow(10, e)), label: `1e${e}` });
      }
    } else {
      const n = 5;
      for (let i = 0; i <= n; i++) {
        const v = yMin + (i / n) * (yMax - yMin);
        yTicks.push({ y: sy(v), label: fmtTick(v) });
      }
    }

    // x ticks
    const xN = 6;
    const xTicks = Array.from({ length: xN }, (_, i) => {
      const v = xMin + (i / (xN - 1)) * (xMax - xMin);
      return { x: sx(v), label: fmtTick(v) };
    });

    return { paths, yTicks, xTicks };
  }, [series, logY, H]);

  return (
    <div className="line-chart">
      {title && <div className="line-chart-title">{title}</div>}
      <svg
        className="line-svg"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={title ?? "line chart"}
      >
        {model ? (
          <>
            {model.yTicks.map((t, i) => (
              <g key={`y${i}`}>
                <line
                  x1={padL}
                  x2={W - padR}
                  y1={t.y}
                  y2={t.y}
                  className="line-grid"
                />
                <text
                  x={padL - 6}
                  y={t.y + 3}
                  className="line-axis-label"
                  textAnchor="end"
                >
                  {t.label}
                </text>
              </g>
            ))}
            {model.xTicks.map((t, i) => (
              <text
                key={`x${i}`}
                x={t.x}
                y={H - 22}
                className="line-axis-label"
                textAnchor="middle"
              >
                {t.label}
              </text>
            ))}
            <line
              x1={padL}
              x2={padL}
              y1={padT}
              y2={H - padB}
              className="line-axis"
            />
            <line
              x1={padL}
              x2={W - padR}
              y1={H - padB}
              y2={H - padB}
              className="line-axis"
            />
            {model.paths.map((p, i) => (
              <g key={i}>
                <path
                  d={p.d}
                  fill="none"
                  stroke={PALETTE[i % PALETTE.length]}
                  strokeWidth={1.8}
                />
                {p.pts.map(([cx, cy], j) => (
                  <circle
                    key={j}
                    cx={cx}
                    cy={cy}
                    r={2.2}
                    fill={PALETTE[i % PALETTE.length]}
                  />
                ))}
              </g>
            ))}
          </>
        ) : (
          <text
            x={W / 2}
            y={H / 2}
            className="line-axis-label"
            textAnchor="middle"
          >
            no data
          </text>
        )}
        {yLabel && (
          <text
            x={14}
            y={H / 2}
            className="line-axis-title"
            textAnchor="middle"
            transform={`rotate(-90 14 ${H / 2})`}
          >
            {yLabel}
          </text>
        )}
        {xLabel && (
          <text
            x={(W + padL) / 2}
            y={H - 4}
            className="line-axis-title"
            textAnchor="middle"
          >
            {xLabel}
          </text>
        )}
      </svg>
      {series.length > 1 && (
        <div className="line-legend">
          {series.map((s, i) => (
            <span key={s.label} className="line-legend-item">
              <span
                className="line-legend-swatch"
                style={{ background: PALETTE[i % PALETTE.length] }}
              />
              {s.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function fmtTick(v: number): string {
  const a = Math.abs(v);
  if (v === 0) return "0";
  if (a >= 1e5 || a < 1e-3) return v.toExponential(2);
  return v.toPrecision(4).replace(/\.?0+$/, "");
}
