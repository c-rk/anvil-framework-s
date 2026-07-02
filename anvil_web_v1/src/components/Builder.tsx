import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { api } from "../lib/api";
import type {
  RegistryEntry,
  RsqDetail,
  SystemQuantity,
  SystemSolveRequest,
} from "../lib/types";
import {
  computeWires,
  effectivePortName,
  unresolvedInputs,
  type QuantityNodeData,
  type RelationNodeData,
} from "../lib/wiring";
import { QuantityNode } from "./nodes/QuantityNode";
import { RelationNode } from "./nodes/RelationNode";
import { SystemSolvePanel } from "./SystemSolvePanel";

const nodeTypes = { quantity: QuantityNode, relation: RelationNode };

let idSeq = 1;
const nextId = (p: string) => `${p}_${idSeq++}`;

interface Props {
  entries: RegistryEntry[];
}

/** Inner builder (must be inside a ReactFlowProvider to use the instance). */
function BuilderInner({ entries }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Detail cache for relation RSQs, plus a request to (re)run the solve.
  const [details, setDetails] = useState<Record<string, RsqDetail | null>>({});
  const [solveReq, setSolveReq] = useState<SystemSolveRequest | null>(null);
  const [solveLiveMode, setSolveLiveMode] = useState(true);
  const [solveErr, setSolveErr] = useState<string | null>(null);

  // -------- node mutation helpers (stored on node.data via closures) -------
  const removeNode = useCallback(
    (id: string) => {
      setNodes((ns: Node[]) => ns.filter((n) => n.id !== id));
    },
    [setNodes],
  );

  const patchQuantity = useCallback(
    (id: string, patch: Partial<QuantityNodeData>) => {
      setNodes((ns: Node[]) =>
        ns.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, ...patch } } : n,
        ),
      );
    },
    [setNodes],
  );

  const renamePort = useCallback(
    (id: string, original: string, value: string) => {
      setNodes((ns: Node[]) =>
        ns.map((n) => {
          if (n.id !== id) return n;
          const portNames = {
            ...(n.data.portNames as Record<string, string>),
            [original]: value,
          };
          return { ...n, data: { ...n.data, portNames } };
        }),
      );
    },
    [setNodes],
  );

  // ----------------------------- add nodes ---------------------------------
  function addQuantity() {
    const id = nextId("q");
    const node: Node = {
      id,
      type: "quantity",
      position: { x: 60, y: 60 + (nodes.length % 6) * 90 },
      data: {
        name: "x",
        value: "1",
        unit: "",
        onChange: (patch: Partial<QuantityNodeData>) =>
          patchQuantity(id, patch),
        onRemove: () => removeNode(id),
      },
    };
    setNodes((ns: Node[]) => [...ns, node]);
  }

  const addRelation = useCallback(
    (rsqName: string, position: { x: number; y: number }) => {
      const id = nextId("r");
      const node: Node = {
        id,
        type: "relation",
        position,
        data: {
          rsqName,
          detail: details[rsqName] ?? null,
          loading: !details[rsqName],
          error: null,
          portNames: {},
          onRenamePort: (orig: string, val: string) =>
            renamePort(id, orig, val),
          onRemove: () => removeNode(id),
        },
      };
      setNodes((ns: Node[]) => [...ns, node]);

      // Lazy-load detail if we don't have it yet.
      if (details[rsqName] === undefined) {
        api
          .rsq(rsqName)
          .then((d) => {
            setDetails((m) => ({ ...m, [rsqName]: d }));
            setNodes((ns: Node[]) =>
              ns.map((n) =>
                n.id === id
                  ? { ...n, data: { ...n.data, detail: d, loading: false } }
                  : n,
              ),
            );
          })
          .catch((e) => {
            setNodes((ns: Node[]) =>
              ns.map((n) =>
                n.id === id
                  ? {
                      ...n,
                      data: {
                        ...n.data,
                        loading: false,
                        error: String(e?.message ?? e),
                      },
                    }
                  : n,
              ),
            );
          });
      }
    },
    [details, removeNode, renamePort, setNodes],
  );

  // Keep cached details flowing into existing relation nodes.
  useEffect(() => {
    setNodes((ns: Node[]) =>
      ns.map((n) => {
        if (n.type !== "relation") return n;
        const rsqName = n.data.rsqName as string;
        const d = details[rsqName];
        if (d && n.data.detail !== d) {
          return { ...n, data: { ...n.data, detail: d, loading: false } };
        }
        return n;
      }),
    );
  }, [details, setNodes]);

  // --------------------------- drag & drop ---------------------------------
  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const rsqName = e.dataTransfer.getData("application/anvil-rsq");
      if (!rsqName || !rfInstance) return;
      const position = rfInstance.screenToFlowPosition({
        x: e.clientX,
        y: e.clientY,
      });
      addRelation(rsqName, position);
    },
    [rfInstance, addRelation],
  );

  // ------------------------ derive canvas model ----------------------------
  const { quantityData, relationData } = useMemo(() => {
    const quantityData: QuantityNodeData[] = [];
    const relationData: RelationNodeData[] = [];
    for (const n of nodes) {
      if (n.type === "quantity") {
        quantityData.push({
          nodeId: n.id,
          name: String(n.data.name ?? ""),
          value: String(n.data.value ?? ""),
          unit: String(n.data.unit ?? ""),
        });
      } else if (n.type === "relation") {
        relationData.push({
          nodeId: n.id,
          rsqName: String(n.data.rsqName ?? ""),
          detail: (n.data.detail as RsqDetail | null) ?? null,
          portNames: (n.data.portNames as Record<string, string>) ?? {},
        });
      }
    }
    return { quantityData, relationData };
  }, [nodes]);

  // -------------------- auto-wiring -> visual edges -------------------------
  const wires = useMemo(
    () => computeWires(quantityData, relationData),
    [quantityData, relationData],
  );

  useEffect(() => {
    const autoEdges: Edge[] = wires.map((w) => ({
      id: w.id,
      source: w.source.nodeId,
      sourceHandle: w.source.handle,
      target: w.target.nodeId,
      targetHandle: w.target.handle,
      label: w.variable,
      animated: true,
      className: "auto-edge",
    }));
    setEdges(autoEdges);
  }, [wires, setEdges]);

  // Manual connections are allowed but the solve ignores edges anyway.
  const onConnect = useCallback(
    (c: Connection) => setEdges((eds: Edge[]) => addEdge({ ...c }, eds)),
    [setEdges],
  );

  const missing = useMemo(
    () => unresolvedInputs(quantityData, relationData),
    [quantityData, relationData],
  );

  // ------------------------------- solve -----------------------------------
  function buildRequest(): SystemSolveRequest | null {
    const quantities: SystemQuantity[] = [];
    for (const q of quantityData) {
      const name = q.name.trim();
      if (!name) continue;
      const value = Number(q.value);
      if (!Number.isFinite(value)) continue;
      const quant: SystemQuantity = { name, value };
      if (q.unit.trim()) quant.unit = q.unit.trim();
      quantities.push(quant);
    }
    const relations = relationData.map((r) => r.rsqName);
    if (relations.length === 0) {
      setSolveErr("Add at least one relation node to solve.");
      return null;
    }
    return { name: "builder_system", quantities, relations };
  }

  function solve(liveMode: boolean) {
    setSolveErr(null);
    const req = buildRequest();
    if (!req) return;
    setSolveLiveMode(liveMode);
    setSolveReq(req);
  }

  // Note any relation port renames so the user sees effective match names.
  const effectiveNote = useMemo(() => {
    const renamed: string[] = [];
    for (const r of relationData) {
      if (!r.detail) continue;
      for (const p of [...r.detail.inputs, ...r.detail.outputs]) {
        const eff = effectivePortName(r, p.name);
        if (eff !== p.name) renamed.push(`${p.name}→${eff}`);
      }
    }
    return renamed;
  }, [relationData]);

  const relationEntries = entries.filter((e) => e.type === "R" || e.type === "S");

  return (
    <div className="builder">
      <aside className="builder-palette">
        <div className="palette-head">Palette</div>
        <p className="palette-hint">
          Drag a relation onto the canvas, or add a quantity. Edges are wired
          automatically by matching variable names.
        </p>
        <button className="run-btn add-q-btn" onClick={addQuantity}>
          + Quantity node
        </button>
        <div className="palette-list">
          {relationEntries.map((e) => (
            <div
              key={e.name}
              className="palette-item"
              draggable
              onDragStart={(ev) => {
                ev.dataTransfer.setData("application/anvil-rsq", e.name);
                ev.dataTransfer.effectAllowed = "copy";
              }}
              onDoubleClick={() => addRelation(e.name, { x: 320, y: 80 })}
              title={e.description || e.name}
            >
              <span className="palette-name">{e.name}</span>
              <span className={`badge badge-${e.type}`}>{e.type}</span>
            </div>
          ))}
          {relationEntries.length === 0 && (
            <div className="muted palette-empty">No relations in registry.</div>
          )}
        </div>
      </aside>

      <div className="builder-canvas" ref={wrapRef}>
        <div className="builder-toolbar">
          <button
            className="run-btn"
            onClick={() => solve(true)}
            disabled={relationData.length === 0}
            title="Stream residuals live over a WebSocket"
          >
            Solve System (live)
          </button>
          <button
            className="run-btn live-btn"
            onClick={() => solve(false)}
            disabled={relationData.length === 0}
            title="Non-streaming POST fallback"
          >
            Solve (POST)
          </button>
          <span className="builder-stat">
            {relationData.length} relation
            {relationData.length === 1 ? "" : "s"} · {quantityData.length}{" "}
            quantit{quantityData.length === 1 ? "y" : "ies"} · {wires.length}{" "}
            wire{wires.length === 1 ? "" : "s"}
          </span>
          {missing.length > 0 && (
            <span className="builder-missing" title="Inputs not produced by any node">
              unresolved: {missing.join(", ")}
            </span>
          )}
        </div>

        <div className="builder-flow">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onInit={setRfInstance}
            onDrop={onDrop}
            onDragOver={onDragOver}
            nodeTypes={nodeTypes}
            fitView
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={18} />
            <Controls />
            <MiniMap pannable zoomable />
          </ReactFlow>
          {nodes.length === 0 && (
            <div className="builder-empty">
              Drag a relation from the palette to begin building a System.
            </div>
          )}
        </div>
      </div>

      <aside className="builder-results">
        <div className="palette-head">Solve</div>
        {effectiveNote.length > 0 && (
          <div className="muted rename-note">renamed: {effectiveNote.join(", ")}</div>
        )}
        {solveErr && <div className="panel error">{solveErr}</div>}
        {solveReq ? (
          <SystemSolvePanel
            key={JSON.stringify(solveReq) + String(solveLiveMode)}
            request={solveReq}
            live={solveLiveMode}
          />
        ) : (
          <p className="muted">
            Wire up a System and press “Solve System”. Residuals and results
            appear here.
          </p>
        )}
      </aside>
    </div>
  );
}

export function Builder({ entries }: Props) {
  return (
    <ReactFlowProvider>
      <BuilderInner entries={entries} />
    </ReactFlowProvider>
  );
}
