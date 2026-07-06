import type { Edge, Node } from "@xyflow/react";

/**
 * Layered left-to-right auto-layout for the canvas.
 *
 * Nodes are assigned a column by longest-path dependency depth (sources in
 * column 0, each edge pushing its target at least one column right), then
 * stacked vertically inside each column preserving their current top-to-bottom
 * order. Column widths and row heights use the measured node sizes so blocks
 * never overlap regardless of label length.
 */

const X_GAP = 90;
const Y_GAP = 48;
const MARGIN = 40;
const DEFAULT_W = 260;
const DEFAULT_H = 120;

export function layeredLayout(nodes: Node[], edges: Edge[]): Node[] {
  if (nodes.length === 0) return nodes;

  const ids = new Set(nodes.map((n) => n.id));
  const depth = new Map<string, number>();
  nodes.forEach((n) => depth.set(n.id, 0));

  // Longest-path layering. Iteration count is capped at node count so a
  // cyclic graph (feedback systems are legal) still terminates.
  for (let i = 0; i < nodes.length; i++) {
    let changed = false;
    for (const e of edges) {
      if (!ids.has(e.source) || !ids.has(e.target)) continue;
      const d = (depth.get(e.source) ?? 0) + 1;
      if (d > (depth.get(e.target) ?? 0) && d <= nodes.length) {
        depth.set(e.target, d);
        changed = true;
      }
    }
    if (!changed) break;
  }

  // Group by column, preserving current vertical order within each column.
  const columns = new Map<number, Node[]>();
  [...nodes]
    .sort((a, b) => a.position.y - b.position.y || a.position.x - b.position.x)
    .forEach((n) => {
      const d = depth.get(n.id) ?? 0;
      const col = columns.get(d);
      if (col) col.push(n);
      else columns.set(d, [n]);
    });

  const pos = new Map<string, { x: number; y: number }>();
  let x = MARGIN;
  for (const key of [...columns.keys()].sort((a, b) => a - b)) {
    const col = columns.get(key)!;
    let y = MARGIN;
    let colWidth = 0;
    for (const n of col) {
      const w = n.measured?.width ?? DEFAULT_W;
      const h = n.measured?.height ?? DEFAULT_H;
      pos.set(n.id, { x, y });
      y += h + Y_GAP;
      colWidth = Math.max(colWidth, w);
    }
    x += colWidth + X_GAP;
  }

  return nodes.map((n) => {
    const p = pos.get(n.id);
    return p ? { ...n, position: p } : n;
  });
}
