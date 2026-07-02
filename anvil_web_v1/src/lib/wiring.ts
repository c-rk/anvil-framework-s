// Auto-wiring for the System builder.
//
// Anvil wires relations by MATCHING VARIABLE NAMES: a relation output named `x`
// feeds any input named `x`, and a quantity named `x` feeds any input named `x`.
// We replicate that here purely for VISUALISATION — the solve payload only needs
// the list of quantities and relation names; the backend re-derives the wiring.
//
// An edge is drawn from a "producer" of a name (a quantity node, or a relation
// output port) to every "consumer" of that same name (a relation input port).

import type { RsqDetail } from "./types";

/** A relation node placed on the canvas, with its resolved RSQ detail. */
export interface RelationNodeData {
  /** React Flow node id. */
  nodeId: string;
  /** RSQ registry name. */
  rsqName: string;
  detail: RsqDetail | null;
  /** Optional per-port renames: original port name -> effective match name. */
  portNames?: Record<string, string>;
}

/** A quantity (free input) node placed on the canvas. */
export interface QuantityNodeData {
  nodeId: string;
  /** Effective match name (editable by the user). */
  name: string;
  value: string;
  unit: string;
}

export interface WireEndpoint {
  nodeId: string;
  /** Port handle id; quantity nodes use the sentinel "value". */
  handle: string;
}

export interface Wire {
  id: string;
  /** The variable name that produced this match. */
  variable: string;
  source: WireEndpoint;
  target: WireEndpoint;
}

/** Effective (possibly renamed) name for a relation port. */
export function effectivePortName(
  node: RelationNodeData,
  original: string,
): string {
  const renamed = node.portNames?.[original];
  return renamed && renamed.trim() !== "" ? renamed.trim() : original;
}

/**
 * Compute visual edges from variable-name matches across all canvas nodes.
 *
 * Producers of a name:
 *   - a quantity node whose (effective) name is the variable
 *   - a relation OUTPUT port whose (effective) name is the variable
 * Consumers of a name:
 *   - a relation INPUT port whose (effective) name is the variable
 *
 * A self-edge (relation feeding its own input) is skipped.
 */
export function computeWires(
  quantities: QuantityNodeData[],
  relations: RelationNodeData[],
): Wire[] {
  // variable -> list of producers
  const producers = new Map<string, WireEndpoint[]>();
  // variable -> list of consumers
  const consumers = new Map<string, WireEndpoint[]>();

  const push = (
    map: Map<string, WireEndpoint[]>,
    name: string,
    ep: WireEndpoint,
  ) => {
    const arr = map.get(name);
    if (arr) arr.push(ep);
    else map.set(name, [ep]);
  };

  for (const q of quantities) {
    const name = q.name.trim();
    if (name) push(producers, name, { nodeId: q.nodeId, handle: "value" });
  }

  for (const r of relations) {
    if (!r.detail) continue;
    for (const out of r.detail.outputs) {
      const name = effectivePortName(r, out.name);
      push(producers, name, { nodeId: r.nodeId, handle: `out:${out.name}` });
    }
    for (const inp of r.detail.inputs) {
      const name = effectivePortName(r, inp.name);
      push(consumers, name, { nodeId: r.nodeId, handle: `in:${inp.name}` });
    }
  }

  const wires: Wire[] = [];
  for (const [variable, cons] of consumers) {
    const prods = producers.get(variable);
    if (!prods) continue;
    for (const p of prods) {
      for (const c of cons) {
        if (p.nodeId === c.nodeId) continue; // no self-loops
        wires.push({
          id: `${p.nodeId}.${p.handle}->${c.nodeId}.${c.handle}`,
          variable,
          source: p,
          target: c,
        });
      }
    }
  }
  return wires;
}

/** Names consumed by some relation input but produced by nobody on the canvas. */
export function unresolvedInputs(
  quantities: QuantityNodeData[],
  relations: RelationNodeData[],
): string[] {
  const wires = computeWires(quantities, relations);
  const satisfied = new Set(wires.map((w) => w.variable));
  const missing = new Set<string>();
  for (const r of relations) {
    if (!r.detail) continue;
    for (const inp of r.detail.inputs) {
      const name = effectivePortName(r, inp.name);
      if (!satisfied.has(name)) missing.add(name);
    }
  }
  return [...missing];
}
