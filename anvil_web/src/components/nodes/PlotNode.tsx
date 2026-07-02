import { useMemo } from "react";
import { useNodes, type NodeProps } from "@xyflow/react";
import { LineChart, type Series } from "../LineChart";
import type { SweepSeriesData } from "./SweepNode";

export interface PlotNodeFields {
  /** Sweep block node id whose recorded series this plot renders. */
  source: string;
  onChange: (patch: { source?: string }) => void;
  onRemove: () => void;
}

/**
 * Plot block node: renders the recorded series of a sweep block (outputs vs
 * the swept param) as a small theme-aware LineChart, live-updating after each
 * sweep run.
 */
export function PlotNode({ data }: NodeProps) {
  const d = data as unknown as PlotNodeFields;
  const nodes = useNodes();

  const sweeps = useMemo(
    () =>
      nodes
        .filter((n) => n.type === "sweep")
        .map((n) => ({
          id: n.id,
          param: String(n.data.param ?? "").trim(),
          series: (n.data.series as SweepSeriesData | null) ?? null,
        })),
    [nodes],
  );

  const src = sweeps.find((s) => s.id === d.source) ?? null;

  // One chart per output: scales differ across quantities, so each gets its
  // own axes instead of sharing one y-axis.
  const charts: { label: string; series: Series[] }[] = useMemo(() => {
    if (!src?.series) return [];
    const { x, ys } = src.series;
    const out: { label: string; series: Series[] }[] = [];
    for (const [label, vals] of Object.entries(ys)) {
      const pts: [number, number][] = [];
      for (let i = 0; i < x.length; i++) {
        const y = vals[i];
        if (typeof y === "number" && Number.isFinite(y)) pts.push([x[i], y]);
      }
      if (pts.length) out.push({ label, series: [{ label, points: pts }] });
    }
    return out;
  }, [src?.series]);

  return (
    <div className="gnode gnode-plot">
      <div className="gnode-head">
        <span className="gnode-kind">plot</span>
        <span className="gnode-title">
          {src ? `vs ${src.param || "?"}` : "sweep plot"}
        </span>
        <button
          className="gnode-x"
          onClick={d.onRemove}
          title="Remove node"
          aria-label="Remove node"
        >
          ×
        </button>
      </div>

      <select
        className="gnode-op nodrag"
        value={d.source}
        onChange={(e) => d.onChange({ source: e.target.value })}
        aria-label="Sweep block to plot"
      >
        <option value="">— choose a sweep block —</option>
        {sweeps.map((s) => (
          <option key={s.id} value={s.id}>
            {s.param || "(unset param)"} · {s.id}
          </option>
        ))}
      </select>

      <div className="gnode-plot-body nodrag">
        {charts.length > 0 && src?.series ? (
          charts.map((c) => (
            <LineChart
              key={c.label}
              series={c.series}
              xLabel={src.series!.param}
              yLabel={c.label}
              height={150}
            />
          ))
        ) : (
          <div className="gnode-msg">
            {!src
              ? sweeps.length
                ? "select a sweep block to plot"
                : "add a sweep block first"
              : src.series
                ? "no numeric data recorded"
                : "run the sweep to plot its results"}
          </div>
        )}
      </div>
    </div>
  );
}
