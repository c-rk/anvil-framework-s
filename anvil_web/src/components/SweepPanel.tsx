import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import type { RsqDetail, SweepResponse } from "../lib/types";
import { LineChart, type Series } from "./LineChart";

interface Props {
  /** RSQ name to sweep (relation or system). */
  name: string;
}

/**
 * Parametric sweep: pick an input param + min/max/steps, call POST /api/sweep,
 * and draw output(s) vs the swept param. Self-loads the RSQ detail to populate
 * the param/output pickers.
 */
export function SweepPanel({ name }: Props) {
  const [detail, setDetail] = useState<RsqDetail | null>(null);
  const [param, setParam] = useState("");
  const [min, setMin] = useState("0");
  const [max, setMax] = useState("1");
  const [steps, setSteps] = useState("11");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [res, setRes] = useState<SweepResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setRes(null);
    setErr(null);
    api
      .rsq(name)
      .then((d) => {
        if (cancelled) return;
        setDetail(d);
        if (d.inputs.length) setParam(d.inputs[0].name);
        setPicked(new Set(d.outputs.map((o) => o.name)));
      })
      .catch((e) => !cancelled && setErr(String(e?.message ?? e)));
    return () => {
      cancelled = true;
    };
  }, [name]);

  function toggleOutput(o: string) {
    setPicked((p) => {
      const next = new Set(p);
      if (next.has(o)) next.delete(o);
      else next.add(o);
      return next;
    });
  }

  async function run() {
    if (!detail || !param) return;
    const lo = Number(min);
    const hi = Number(max);
    const n = Math.max(2, Math.floor(Number(steps)));
    if (!Number.isFinite(lo) || !Number.isFinite(hi) || !Number.isFinite(n)) {
      setErr("min/max/steps must be numbers");
      return;
    }
    const values = Array.from(
      { length: n },
      (_, i) => lo + (i / (n - 1)) * (hi - lo),
    );
    setBusy(true);
    setErr(null);
    try {
      const r = await api.sweep({
        name: detail.name,
        param,
        values,
        outputs: [...picked],
        si: true,
      });
      setRes(r);
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  const series: Series[] = useMemo(() => {
    if (!res) return [];
    const xs = res.data[res.param];
    if (!xs) return [];
    const out: Series[] = [];
    for (const [col, ys] of Object.entries(res.data)) {
      if (col === res.param) continue;
      const pts: [number, number][] = [];
      for (let i = 0; i < xs.length && i < ys.length; i++) {
        const x = xs[i];
        const y = ys[i];
        if (typeof x === "number" && typeof y === "number") pts.push([x, y]);
      }
      if (pts.length) out.push({ label: col, points: pts });
    }
    return out;
  }, [res]);

  if (err && !detail) {
    return <div className="panel error">{err}</div>;
  }
  if (!detail) {
    return <div className="panel muted">Loading {name}…</div>;
  }

  return (
    <div className="sweep-panel">
      <div className="sweep-controls">
        <label className="field">
          <span className="field-name">param</span>
          <select
            value={param}
            onChange={(e) => setParam(e.target.value)}
            aria-label="Sweep parameter"
          >
            {detail.inputs.map((inp) => (
              <option key={inp.name} value={inp.name}>
                {inp.name}
                {inp.unit ? ` (${inp.unit})` : ""}
              </option>
            ))}
            {detail.inputs.length === 0 && <option value="">no inputs</option>}
          </select>
        </label>
        <label className="field">
          <span className="field-name">min</span>
          <input
            type="number"
            step="any"
            value={min}
            onChange={(e) => setMin(e.target.value)}
          />
        </label>
        <label className="field">
          <span className="field-name">max</span>
          <input
            type="number"
            step="any"
            value={max}
            onChange={(e) => setMax(e.target.value)}
          />
        </label>
        <label className="field">
          <span className="field-name">steps</span>
          <input
            type="number"
            min={2}
            step={1}
            value={steps}
            onChange={(e) => setSteps(e.target.value)}
          />
        </label>
        <button
          className="run-btn"
          disabled={busy || !param}
          onClick={run}
        >
          {busy ? "Sweeping…" : "Run sweep"}
        </button>
      </div>

      {detail.outputs.length > 0 && (
        <div className="sweep-outputs">
          <span className="field-name">outputs:</span>
          {detail.outputs.map((o) => (
            <label key={o.name} className="sweep-out-chip">
              <input
                type="checkbox"
                checked={picked.has(o.name)}
                onChange={() => toggleOutput(o.name)}
              />
              {o.name}
            </label>
          ))}
        </div>
      )}

      {err && <div className="panel error">{err}</div>}

      {res && series.length > 0 ? (
        <LineChart
          series={series}
          title={`${res.name}: output vs ${res.param}`}
          xLabel={res.param}
          yLabel="output"
        />
      ) : res ? (
        <p className="muted">No numeric output columns returned.</p>
      ) : (
        <p className="muted">Configure a sweep and run it.</p>
      )}
    </div>
  );
}
