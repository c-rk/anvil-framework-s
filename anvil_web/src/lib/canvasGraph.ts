// CanvasGraph <-> React Flow conversion.
//
// The backend persists canvases as python scripts; its wire format is the
// CanvasGraph JSON shape (see anvil_server). `toGraph` serialises the current
// React Flow node state; `fromGraph` coerces an arbitrary JSON payload back to
// a NORMALISED CanvasGraph that the Builder can place on the canvas (edges are
// re-drawn by the existing auto-wiring, so they are not persisted).
//
// Both directions funnel block configs through the same normalisers so that
// `graphSignature(toGraph(nodes)) === graphSignature(fromGraph(raw))` after a
// round-trip — that equality drives the toolbar's dirty-asterisk.

import type { Node } from "@xyflow/react";
import { ARITH_SPECS, type ArithOp } from "./arithmetic";

export interface GraphPos {
  x: number;
  y: number;
}

export interface GraphQuantity {
  name: string;
  value: number;
  unit: string;
  pos: GraphPos;
}

export interface GraphRelation {
  name: string;
  pos: GraphPos;
  /** original port name -> renamed (effective) name; only real renames. */
  renames: Record<string, string>;
}

export interface ArithConfig {
  op: ArithOp;
  outName: string;
  portSources: Record<string, string>;
  a: number;
  b: number;
  expression: string;
}

export interface SweepConfig {
  param: string;
  min: number;
  max: number;
  steps: number;
  outputs: string[];
}

export interface PlotConfig {
  /** id of the sweep block whose recorded series this plot renders. */
  source: string;
}

export interface CsvConfig {
  name: string;
  text: string;
}

export type GraphBlock =
  | { id: string; kind: "arith"; config: ArithConfig; pos: GraphPos }
  | { id: string; kind: "sweep"; config: SweepConfig; pos: GraphPos }
  | { id: string; kind: "plot"; config: PlotConfig; pos: GraphPos }
  | { id: string; kind: "csv"; config: CsvConfig; pos: GraphPos };

export interface CanvasGraph {
  name: string;
  description: string;
  quantities: GraphQuantity[];
  relations: GraphRelation[];
  blocks: GraphBlock[];
}

/** Hard cap on client-side sweep steps (one solve request per step). */
export const SWEEP_MAX_STEPS = 100;

// ------------------------------ normalisers --------------------------------

const num = (v: unknown, fallback: number): number => {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : fallback;
};

const str = (v: unknown, fallback = ""): string =>
  typeof v === "string" ? v : v == null ? fallback : String(v);

/** Round positions for a stable signature across drag jitter / JSON trips. */
const roundPos = (p: { x?: unknown; y?: unknown } | undefined): GraphPos => ({
  x: Math.round(num(p?.x, 0) * 100) / 100,
  y: Math.round(num(p?.y, 0) * 100) / 100,
});

const strMap = (v: unknown): Record<string, string> => {
  const out: Record<string, string> = {};
  if (v && typeof v === "object") {
    for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
      if (typeof val === "string") out[k] = val;
    }
  }
  return out;
};

const strArray = (v: unknown): string[] =>
  Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];

function normArithConfig(c: Record<string, unknown>): ArithConfig {
  const op = str(c.op, "add");
  return {
    op: (op in ARITH_SPECS ? op : "add") as ArithOp,
    outName: str(c.outName).trim(),
    portSources: strMap(c.portSources),
    a: num(c.a, 1),
    b: num(c.b, 0),
    expression: str(c.expression),
  };
}

function normSweepConfig(c: Record<string, unknown>): SweepConfig {
  return {
    param: str(c.param).trim(),
    min: num(c.min, 0),
    max: num(c.max, 1),
    steps: Math.max(2, Math.min(SWEEP_MAX_STEPS, Math.floor(num(c.steps, 21)))),
    outputs: strArray(c.outputs),
  };
}

function normPlotConfig(c: Record<string, unknown>): PlotConfig {
  return { source: str(c.source).trim() };
}

function normCsvConfig(c: Record<string, unknown>): CsvConfig {
  return { name: str(c.name, "data") || "data", text: str(c.text) };
}

/** Only renames that differ from the original, trimmed. */
function normRenames(v: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [orig, renamed] of Object.entries(strMap(v))) {
    const t = renamed.trim();
    if (t && t !== orig) out[orig] = t;
  }
  return out;
}

// ------------------------------- toGraph ------------------------------------

/** Serialise the current React Flow nodes into a CanvasGraph. */
export function toGraph(nodes: Node[], name: string, description = ""): CanvasGraph {
  const quantities: GraphQuantity[] = [];
  const relations: GraphRelation[] = [];
  const blocks: GraphBlock[] = [];

  for (const n of nodes) {
    const d = n.data as Record<string, unknown>;
    const pos = roundPos(n.position);
    switch (n.type) {
      case "quantity":
        quantities.push({
          name: str(d.name).trim(),
          value: num(d.value, 0),
          unit: str(d.unit).trim(),
          pos,
        });
        break;
      case "relation":
        relations.push({
          name: str(d.rsqName),
          pos,
          renames: normRenames(d.portNames),
        });
        break;
      case "arith":
        blocks.push({ id: n.id, kind: "arith", config: normArithConfig(d), pos });
        break;
      case "sweep":
        blocks.push({ id: n.id, kind: "sweep", config: normSweepConfig(d), pos });
        break;
      case "plot":
        blocks.push({ id: n.id, kind: "plot", config: normPlotConfig(d), pos });
        break;
      case "csv":
        blocks.push({ id: n.id, kind: "csv", config: normCsvConfig(d), pos });
        break;
    }
  }
  return { name, description, quantities, relations, blocks };
}

// ------------------------------ fromGraph ------------------------------------

/**
 * Coerce an arbitrary JSON payload (server canvas / parse result / autosave)
 * into a normalised CanvasGraph. Never throws; unknown entries are dropped.
 */
export function fromGraph(raw: unknown): CanvasGraph {
  const o = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;

  const quantities: GraphQuantity[] = [];
  if (Array.isArray(o.quantities)) {
    for (const q of o.quantities) {
      if (!q || typeof q !== "object") continue;
      const qq = q as Record<string, unknown>;
      quantities.push({
        name: str(qq.name).trim(),
        value: num(qq.value, 0),
        unit: str(qq.unit).trim(),
        pos: roundPos(qq.pos as GraphPos | undefined),
      });
    }
  }

  const relations: GraphRelation[] = [];
  if (Array.isArray(o.relations)) {
    for (const r of o.relations) {
      if (!r || typeof r !== "object") continue;
      const rr = r as Record<string, unknown>;
      const name = str(rr.name).trim();
      if (!name) continue;
      relations.push({
        name,
        pos: roundPos(rr.pos as GraphPos | undefined),
        renames: normRenames(rr.renames),
      });
    }
  }

  const blocks: GraphBlock[] = [];
  if (Array.isArray(o.blocks)) {
    let i = 0;
    for (const b of o.blocks) {
      i += 1;
      if (!b || typeof b !== "object") continue;
      const bb = b as Record<string, unknown>;
      const id = str(bb.id).trim() || `blk_${i}`;
      const pos = roundPos(bb.pos as GraphPos | undefined);
      const cfg = (bb.config && typeof bb.config === "object"
        ? bb.config
        : {}) as Record<string, unknown>;
      switch (bb.kind) {
        case "arith":
          blocks.push({ id, kind: "arith", config: normArithConfig(cfg), pos });
          break;
        case "sweep":
          blocks.push({ id, kind: "sweep", config: normSweepConfig(cfg), pos });
          break;
        case "plot":
          blocks.push({ id, kind: "plot", config: normPlotConfig(cfg), pos });
          break;
        case "csv":
          blocks.push({ id, kind: "csv", config: normCsvConfig(cfg), pos });
          break;
      }
    }
  }

  return {
    name: str(o.name),
    description: str(o.description),
    quantities,
    relations,
    blocks,
  };
}

/** True when a graph carries no meaningful content. */
export function graphIsEmpty(g: CanvasGraph): boolean {
  return g.quantities.length === 0 && g.relations.length === 0 && g.blocks.length === 0;
}

/**
 * Content signature of a graph (name/description excluded). Two graphs with
 * the same signature render the same canvas — used for the dirty flag.
 */
export function graphSignature(g: CanvasGraph): string {
  return JSON.stringify([g.quantities, g.relations, g.blocks]);
}
