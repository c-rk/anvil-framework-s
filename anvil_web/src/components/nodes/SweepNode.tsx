import { useMemo } from "react";
import { Handle, Position, useNodes, type NodeProps } from "@xyflow/react";
import type { RsqDetail } from "../../lib/types";

/** Results recorded by a client-side system sweep run. */
export interface SweepSeriesData {
  /** Swept quantity name. */
  param: string;
  /** Swept values (x axis). */
  x: number[];
  /** output name -> per-step values (null when a step failed / non-numeric). */
  ys: Record<string, (number | null)[]>;
}

export interface SweepNodeFields {
  /** Name of the quantity to sweep (auto-wires by name matching). */
  param: string;
  min: string;
  max: string;
  steps: string;
  /** Selected output names to record at each step. */
  outputs: string[];
  /** Run progress (i of n) while the sweep executes; null when idle. */
  progress: { i: number; n: number } | null;
  series: SweepSeriesData | null;
  error: string | null;
  onChange: (
    patch: Partial<Pick<SweepNodeFields, "param" | "min" | "max" | "steps" | "outputs">>,
  ) => void;
  onRun: () => void;
  onRemove: () => void;
}

/**
 * Sweep block node: sweeps one canvas quantity across [min, max] in N steps by
 * issuing one system solve per step CLIENT-SIDE, recording the chosen relation
 * outputs. The single target handle auto-wires to the quantity named `param`.
 */
export function SweepNode({ data }: NodeProps) {
  const d = data as unknown as SweepNodeFields;
  const nodes = useNodes();

  // Union of (effective) relation output names currently on the canvas.
  const available = useMemo(() => {
    const set = new Set<string>();
    for (const n of nodes) {
      if (n.type !== "relation") continue;
      const detail = (n.data.detail as RsqDetail | null) ?? null;
      if (!detail) continue;
      const renames = (n.data.portNames as Record<string, string>) ?? {};
      for (const o of detail.outputs) {
        const r = renames[o.name]?.trim();
        set.add(r ? r : o.name);
      }
    }
    // Keep already-selected outputs visible even if their relation vanished.
    for (const o of d.outputs) set.add(o);
    return [...set].sort();
  }, [nodes, d.outputs]);

  const toggle = (o: string) => {
    d.onChange({
      outputs: d.outputs.includes(o)
        ? d.outputs.filter((x) => x !== o)
        : [...d.outputs, o],
    });
  };

  const running = d.progress !== null;

  const downloadCsv = () => {
    if (!d.series) return;
    const { param, x, ys } = d.series;
    const cols = Object.keys(ys);
    const rows = [
      [param, ...cols].join(","),
      ...x.map((xv, i) =>
        [xv, ...cols.map((c) => ys[c][i] ?? "")].join(","),
      ),
    ];
    const blob = new Blob([rows.join("\n") + "\n"], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sweep_${param || "data"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="gnode gnode-sweep">
      <div className="gnode-head">
        <span className="gnode-kind">sweep</span>
        <span className="gnode-title">{d.param || "—"}</span>
        <button
          className="gnode-x"
          onClick={d.onRemove}
          title="Remove node"
          aria-label="Remove node"
        >
          ×
        </button>
      </div>

      <div className="gnode-sweep-paramrow">
        <Handle
          type="target"
          position={Position.Left}
          id="in:param"
          className="gnode-port gnode-port-in"
        />
        <input
          className="gnode-portname gnode-sweep-param nodrag"
          value={d.param}
          placeholder="quantity to sweep"
          onChange={(e) => d.onChange({ param: e.target.value })}
          title="Swept quantity name (auto-wires to the matching quantity node)"
          aria-label="Swept quantity name"
        />
      </div>

      <div className="gnode-sweep-range nodrag">
        <label className="gnode-sweep-field">
          <span>min</span>
          <input
            type="number"
            step="any"
            value={d.min}
            onChange={(e) => d.onChange({ min: e.target.value })}
            aria-label="Sweep minimum"
          />
        </label>
        <label className="gnode-sweep-field">
          <span>max</span>
          <input
            type="number"
            step="any"
            value={d.max}
            onChange={(e) => d.onChange({ max: e.target.value })}
            aria-label="Sweep maximum"
          />
        </label>
        <label className="gnode-sweep-field">
          <span>steps</span>
          <input
            type="number"
            min={2}
            max={100}
            step={1}
            value={d.steps}
            onChange={(e) => d.onChange({ steps: e.target.value })}
            aria-label="Sweep steps"
          />
        </label>
      </div>

      <div className="gnode-sweep-outs nodrag">
        <span className="gnode-sweep-label">outputs:</span>
        {available.map((o) => (
          <label key={o} className="sweep-out-chip">
            <input
              type="checkbox"
              checked={d.outputs.includes(o)}
              onChange={() => toggle(o)}
            />
            {o}
          </label>
        ))}
        {available.length === 0 && (
          <span className="muted">no relation outputs on canvas</span>
        )}
      </div>

      <div className="gnode-sweep-runrow nodrag">
        <button className="run-btn" onClick={d.onRun} disabled={running}>
          {running ? `sweeping ${d.progress!.i}/${d.progress!.n}…` : "Run sweep"}
        </button>
        {d.series && !running && (
          <>
            <span className="gnode-sweep-meta">{d.series.x.length} pts recorded</span>
            <button
              className="gnode-csv-btn"
              onClick={downloadCsv}
              title="Download recorded sweep data as CSV"
            >
              csv
            </button>
          </>
        )}
      </div>

      {d.error && <div className="gnode-msg err">{d.error}</div>}
    </div>
  );
}
