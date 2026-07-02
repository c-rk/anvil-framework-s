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
  CanvasListItem,
  ExampleCanvas,
  ExampleScriptItem,
  ExampleSummary,
  RegistryEntry,
  RsqDetail,
  SystemQuantity,
  SystemSolveRequest,
} from "../lib/types";
import {
  computeWires,
  effectivePortName,
  unresolvedInputs,
  type ExtraConsumer,
  type QuantityNodeData,
  type RelationNodeData,
} from "../lib/wiring";
import { expressionVariablesFor } from "../lib/arithmetic";
import { QuantityNode } from "./nodes/QuantityNode";
import { RelationNode } from "./nodes/RelationNode";
import { ArithBlockNode } from "./nodes/ArithBlockNode";
import { CsvNode } from "./nodes/CsvNode";
import { SweepNode, type SweepSeriesData } from "./nodes/SweepNode";
import { PlotNode } from "./nodes/PlotNode";
import { SystemSolvePanel } from "./SystemSolvePanel";
import { groupByDomain } from "../lib/grouping";
import { rsqDocsUrl, NEW_TAB } from "../lib/docs";
import {
  ARITH_SPECS,
  type ArithBlockModel,
  type ArithOp,
} from "../lib/arithmetic";
import { prePass, postPass, type ResolvedValue } from "../lib/canvasEval";
import {
  fromGraph,
  graphIsEmpty,
  graphSignature,
  toGraph,
  SWEEP_MAX_STEPS,
  type CanvasGraph,
  type SweepConfig,
} from "../lib/canvasGraph";
import { readAutosave, writeAutosave } from "../lib/canvasStore";
import { triggerDownload } from "../lib/export";
import { fmtNum } from "../lib/numbers";

const nodeTypes = {
  quantity: QuantityNode,
  relation: RelationNode,
  arith: ArithBlockNode,
  csv: CsvNode,
  sweep: SweepNode,
  plot: PlotNode,
};

let idSeq = 1;
const nextId = (p: string) => `${p}_${idSeq++}`;

/** Valid server-side canvas name (mirrors the backend rule). */
const NAME_RE = /^[A-Za-z0-9_-]+$/;

// Block palette groupings (the new A9 sections).
const BLOCK_SECTIONS: { title: string; ops: ArithOp[] }[] = [
  { title: "Arithmetic", ops: ["add", "subtract", "multiply", "divide", "power"] },
  {
    title: "Transform",
    ops: [
      "negate",
      "abs",
      "sqrt",
      "exp",
      "ln",
      "log10",
      "sin",
      "cos",
      "tan",
      "sin_deg",
      "cos_deg",
      "tan_deg",
      "scale_offset",
      "expression",
    ],
  },
];

interface Props {
  entries: RegistryEntry[];
  dropRequest?: { name: string; seq: number } | null;
}

function BuilderInner({ entries, dropRequest }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const [details, setDetails] = useState<Record<string, RsqDetail | null>>({});
  const [solveReq, setSolveReq] = useState<SystemSolveRequest | null>(null);
  const [solveErr, setSolveErr] = useState<string | null>(null);

  // Server canvas persistence state.
  const [canvasName, setCanvasName] = useState<string | null>(null);
  const [savedSig, setSavedSig] = useState<string>("");
  const [serverCanvases, setServerCanvases] = useState<CanvasListItem[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[] | null>(null);
  const [warnNote, setWarnNote] = useState<string | null>(null);

  // -------- node mutation helpers --------
  const removeNode = useCallback(
    (id: string) => setNodes((ns: Node[]) => ns.filter((n) => n.id !== id)),
    [setNodes],
  );

  const patchData = useCallback(
    (id: string, patch: Record<string, unknown>) => {
      setNodes((ns: Node[]) =>
        ns.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...patch } } : n)),
      );
    },
    [setNodes],
  );

  const patchQuantity = useCallback(
    (id: string, patch: Partial<QuantityNodeData>) => patchData(id, patch),
    [patchData],
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
  const addQuantity = useCallback(
    (
      seed?: { name?: string; value?: string; unit?: string; position?: { x: number; y: number } },
    ) => {
      const id = nextId("q");
      const node: Node = {
        id,
        type: "quantity",
        position: seed?.position ?? { x: 60, y: 60 + (idSeq % 6) * 90 },
        data: {
          name: seed?.name ?? "x",
          value: seed?.value ?? "1",
          unit: seed?.unit ?? "",
          onChange: (patch: Partial<QuantityNodeData>) => patchQuantity(id, patch),
          onRemove: () => removeNode(id),
        },
      };
      setNodes((ns: Node[]) => [...ns, node]);
      return id;
    },
    [patchQuantity, removeNode, setNodes],
  );

  const addRelation = useCallback(
    (rsqName: string, position: { x: number; y: number }, portNames: Record<string, string> = {}) => {
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
          portNames,
          onRenamePort: (orig: string, val: string) => renamePort(id, orig, val),
          onRemove: () => removeNode(id),
        },
      };
      setNodes((ns: Node[]) => [...ns, node]);

      if (details[rsqName] === undefined) {
        api
          .rsq(rsqName)
          .then((d) => {
            setDetails((m) => ({ ...m, [rsqName]: d }));
            setNodes((ns: Node[]) =>
              ns.map((n) =>
                n.id === id ? { ...n, data: { ...n.data, detail: d, loading: false } } : n,
              ),
            );
          })
          .catch((e) => {
            setNodes((ns: Node[]) =>
              ns.map((n) =>
                n.id === id
                  ? { ...n, data: { ...n.data, loading: false, error: String(e?.message ?? e) } }
                  : n,
              ),
            );
          });
      }
    },
    [details, removeNode, renamePort, setNodes],
  );

  const addArith = useCallback(
    (
      op: ArithOp,
      position?: { x: number; y: number },
      seed?: Partial<ArithBlockModel>,
      forcedId?: string,
    ) => {
      const id = forcedId ?? nextId("a");
      const spec = ARITH_SPECS[op];
      const node: Node = {
        id,
        type: "arith",
        position: position ?? { x: 320, y: 80 + (idSeq % 6) * 90 },
        data: {
          id,
          op,
          outName: seed?.outName ?? spec.defaultOut,
          portSources: seed?.portSources ?? {},
          a: seed?.a ?? 1,
          b: seed?.b ?? 0,
          expression: seed?.expression ?? "",
          computed: null,
          computeError: null,
          onChange: (patch: Partial<ArithBlockModel>) => patchData(id, patch),
          onRemove: () => removeNode(id),
        },
      };
      setNodes((ns: Node[]) => [...ns, node]);
      return id;
    },
    [patchData, removeNode, setNodes],
  );

  const parseCsvNode = useCallback(
    (id: string, text: string) => {
      patchData(id, { parsing: true, error: null });
      api
        .csv(text)
        .then((r) => {
          const columns = r.columns
            .map((c) => ({
              name: c,
              values: (r.data[c] ?? []).filter(
                (v): v is number => typeof v === "number" && Number.isFinite(v),
              ),
            }))
            .filter((c) => c.values.length > 0);
          patchData(id, { parsing: false, columns, rows: r.rows, error: columns.length ? null : "no numeric columns" });
        })
        .catch((e) => patchData(id, { parsing: false, error: String(e?.message ?? e) }));
    },
    [patchData],
  );

  const addCsv = useCallback(
    (
      position?: { x: number; y: number },
      seed?: { name?: string; text?: string },
      forcedId?: string,
    ) => {
      const id = forcedId ?? nextId("csv");
      const node: Node = {
        id,
        type: "csv",
        position: position ?? { x: 80, y: 80 + (idSeq % 6) * 90 },
        data: {
          name: seed?.name ?? "data",
          text: seed?.text ?? "",
          columns: [],
          rows: 0,
          parsing: false,
          error: null,
          onChangeText: (text: string) => patchData(id, { text }),
          onParse: () => {
            // read latest text from node state via functional update
            setNodes((ns: Node[]) => {
              const n = ns.find((x) => x.id === id);
              const text = (n?.data.text as string) ?? "";
              if (text.trim()) parseCsvNode(id, text);
              return ns;
            });
          },
          onRemove: () => removeNode(id),
        },
      };
      setNodes((ns: Node[]) => [...ns, node]);
      if (seed?.text?.trim()) parseCsvNode(id, seed.text);
      return id;
    },
    [parseCsvNode, patchData, removeNode, setNodes],
  );

  // The sweep runner is defined further down (it needs the canvas model);
  // node callbacks call through this ref so they never go stale.
  const runSweepRef = useRef<(id: string) => void>(() => {});

  const addSweep = useCallback(
    (
      position?: { x: number; y: number },
      seed?: Partial<SweepConfig>,
      forcedId?: string,
    ) => {
      const id = forcedId ?? nextId("sw");
      const node: Node = {
        id,
        type: "sweep",
        position: position ?? { x: 360, y: 120 + (idSeq % 6) * 90 },
        data: {
          param: seed?.param ?? "",
          min: seed?.min !== undefined ? String(seed.min) : "0",
          max: seed?.max !== undefined ? String(seed.max) : "1",
          steps: seed?.steps !== undefined ? String(seed.steps) : "21",
          outputs: seed?.outputs ?? [],
          progress: null,
          series: null,
          error: null,
          onChange: (patch: Record<string, unknown>) => patchData(id, patch),
          onRun: () => runSweepRef.current(id),
          onRemove: () => removeNode(id),
        },
      };
      setNodes((ns: Node[]) => [...ns, node]);
      return id;
    },
    [patchData, removeNode, setNodes],
  );

  const addPlot = useCallback(
    (
      position?: { x: number; y: number },
      seed?: { source?: string },
      forcedId?: string,
    ) => {
      const id = forcedId ?? nextId("pl");
      const node: Node = {
        id,
        type: "plot",
        position: position ?? { x: 640, y: 120 + (idSeq % 6) * 90 },
        data: {
          source: seed?.source ?? "",
          onChange: (patch: Record<string, unknown>) => patchData(id, patch),
          onRemove: () => removeNode(id),
        },
      };
      setNodes((ns: Node[]) => [...ns, node]);
      return id;
    },
    [patchData, removeNode, setNodes],
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

  // spotlight-driven drop
  const lastDropSeq = useRef(0);
  useEffect(() => {
    if (!dropRequest) return;
    if (dropRequest.seq === lastDropSeq.current) return;
    lastDropSeq.current = dropRequest.seq;
    const offset = (dropRequest.seq % 6) * 40;
    addRelation(dropRequest.name, { x: 320 + offset, y: 80 + offset });
  }, [dropRequest, addRelation]);

  const [collapsedDomains, setCollapsedDomains] = useState<Record<string, boolean>>({});
  const [paletteTab, setPaletteTab] = useState<"relations" | "blocks">("relations");

  // --------------------------- drag & drop ---------------------------------
  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!rfInstance) return;
      const position = rfInstance.screenToFlowPosition({ x: e.clientX, y: e.clientY });
      const rsqName = e.dataTransfer.getData("application/anvil-rsq");
      if (rsqName) {
        addRelation(rsqName, position);
        return;
      }
      const op = e.dataTransfer.getData("application/anvil-arith") as ArithOp;
      if (op) {
        addArith(op, position);
        return;
      }
      const special = e.dataTransfer.getData("application/anvil-special");
      if (special === "quantity") addQuantity({ position });
      else if (special === "csv") addCsv(position);
      else if (special === "sweep") addSweep(position);
      else if (special === "plot") addPlot(position);
    },
    [rfInstance, addRelation, addArith, addQuantity, addCsv, addSweep, addPlot],
  );

  // ------------------------ derive canvas model ----------------------------
  const { quantityData, relationData, blockData } = useMemo(() => {
    const quantityData: QuantityNodeData[] = [];
    const relationData: RelationNodeData[] = [];
    const blockData: ArithBlockModel[] = [];
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
      } else if (n.type === "arith") {
        blockData.push({
          id: n.id,
          op: n.data.op as ArithOp,
          outName: String(n.data.outName ?? ""),
          portSources: (n.data.portSources as Record<string, string>) ?? {},
          a: typeof n.data.a === "number" ? (n.data.a as number) : Number(n.data.a),
          b: typeof n.data.b === "number" ? (n.data.b as number) : Number(n.data.b),
          expression: String(n.data.expression ?? ""),
        });
      }
    }
    return { quantityData, relationData, blockData };
  }, [nodes]);

  // CSV columns become extra producers (name -> array). For wiring we treat
  // CSV column names as quantity producers so relations can consume them.
  const csvProducers = useMemo(() => {
    const out: { nodeId: string; name: string }[] = [];
    for (const n of nodes) {
      if (n.type !== "csv") continue;
      const cols = (n.data.columns as { name: string }[]) ?? [];
      for (const c of cols) out.push({ nodeId: n.id, name: c.name });
    }
    return out;
  }, [nodes]);

  // Pre-pass: resolve arithmetic blocks from quantities (client-side).
  const prePassResult = useMemo(() => {
    const quantities: Record<string, ResolvedValue> = {};
    for (const q of quantityData) {
      const name = q.name.trim();
      const val = Number(q.value);
      if (name && Number.isFinite(val)) quantities[name] = { value: val, unit: q.unit.trim() };
    }
    // Relation outputs are produced names we cannot resolve until backend solve.
    const relationOutputs = new Set<string>();
    for (const r of relationData) {
      if (!r.detail) continue;
      for (const o of r.detail.outputs) relationOutputs.add(effectivePortName(r, o.name));
    }
    return prePass({ quantities, relationOutputs, blocks: blockData });
  }, [quantityData, relationData, blockData]);

  // Push pre-pass computed values onto the block nodes for display.
  useEffect(() => {
    setNodes((ns: Node[]) =>
      ns.map((n) => {
        if (n.type !== "arith") return n;
        const v = prePassResult.blockValues[n.id] ?? null;
        const err = prePassResult.blockErrors[n.id] ?? null;
        const deferred = prePassResult.deferred.includes(n.id);
        const computed = v;
        const computeError = err ?? (deferred ? "awaiting solve…" : null);
        if (n.data.computed === computed && n.data.computeError === computeError) return n;
        return { ...n, data: { ...n.data, computed, computeError } };
      }),
    );
  }, [prePassResult, setNodes]);

  // -------------------- auto-wiring -> visual edges -------------------------
  // Extend quantity producers with CSV columns and pre-pass-derived block names.
  const wireQuantities = useMemo(() => {
    const list: QuantityNodeData[] = [...quantityData];
    for (const c of csvProducers) {
      list.push({ nodeId: c.nodeId, name: c.name, value: "", unit: "" });
    }
    return list;
  }, [quantityData, csvProducers]);

  const blockProducers = useMemo(() => {
    // Treat each arith block's output name as a producer for wiring.
    return blockData.map((b) => ({
      nodeId: b.id,
      name: b.outName.trim() || ARITH_SPECS[b.op].defaultOut,
    }));
  }, [blockData]);

  // Block input ports become extra consumers so edges render into blocks too.
  const blockConsumers = useMemo<ExtraConsumer[]>(() => {
    const out: ExtraConsumer[] = [];
    for (const b of blockData) {
      const spec = ARITH_SPECS[b.op];
      if (spec.arity === "expression") {
        for (const v of expressionVariablesFor(b.expression ?? "")) {
          out.push({ nodeId: b.id, name: v, handle: `in:${v}` });
        }
      } else {
        for (const port of spec.ports) {
          const src = (b.portSources?.[port]?.trim() || port);
          out.push({ nodeId: b.id, name: src, handle: `in:${port}` });
        }
      }
    }
    return out;
  }, [blockData]);

  // Sweep blocks consume the quantity they sweep — auto-wire by param name.
  const sweepConsumers = useMemo<ExtraConsumer[]>(() => {
    const out: ExtraConsumer[] = [];
    for (const n of nodes) {
      if (n.type !== "sweep") continue;
      const p = String(n.data.param ?? "").trim();
      if (p) out.push({ nodeId: n.id, name: p, handle: "in:param" });
    }
    return out;
  }, [nodes]);

  const wires = useMemo(() => {
    const qs: QuantityNodeData[] = [
      ...wireQuantities,
      ...blockProducers.map((p) => ({ nodeId: p.nodeId, name: p.name, value: "", unit: "" })),
    ];
    return computeWires(qs, relationData, [...blockConsumers, ...sweepConsumers]);
  }, [wireQuantities, blockProducers, relationData, blockConsumers, sweepConsumers]);

  useEffect(() => {
    const autoEdges: Edge[] = wires.map((w) => ({
      id: w.id,
      source: w.source.nodeId,
      sourceHandle: w.source.handle === "value" ? undefined : w.source.handle,
      target: w.target.nodeId,
      targetHandle: w.target.handle,
      label: w.variable,
      animated: true,
      className: "auto-edge",
      data: { auto: true },
    }));
    // Replace only auto edges; user-drawn (manual) edges persist.
    setEdges((eds: Edge[]) => [
      ...eds.filter((e) => !(e.data as { auto?: boolean } | undefined)?.auto),
      ...autoEdges,
    ]);
  }, [wires, setEdges]);

  const onConnect = useCallback(
    (c: Connection) => {
      // Connecting a quantity into a sweep block's target handle adopts that
      // quantity's name as the swept param (the visual edge is then auto-wired).
      if (c.targetHandle === "in:param") {
        setNodes((ns: Node[]) => {
          const target = ns.find((n) => n.id === c.target);
          const source = ns.find((n) => n.id === c.source);
          if (target?.type === "sweep" && source?.type === "quantity") {
            const name = String(source.data.name ?? "").trim();
            if (name) {
              return ns.map((n) =>
                n.id === target.id ? { ...n, data: { ...n.data, param: name } } : n,
              );
            }
          }
          return ns;
        });
        return;
      }
      setEdges((eds: Edge[]) =>
        addEdge({ ...c, className: "manual-edge", data: { auto: false } }, eds),
      );
    },
    [setEdges, setNodes],
  );

  const missing = useMemo(
    () => unresolvedInputs(wireQuantities, relationData),
    [wireQuantities, relationData],
  );

  // ------------------------------- solve -----------------------------------
  const buildRequest = useCallback(
    (
      override?: { name: string; value: number },
    ): { req?: SystemSolveRequest; error?: string } => {
      const quantities: SystemQuantity[] = [];
      for (const q of quantityData) {
        const name = q.name.trim();
        if (!name) continue;
        let value = Number(q.value);
        if (!Number.isFinite(value)) continue;
        if (override && name === override.name) value = override.value;
        const quant: SystemQuantity = { name, value };
        if (q.unit.trim()) quant.unit = q.unit.trim();
        quantities.push(quant);
      }
      // Add pre-pass-derived block outputs as concrete quantities (A3 step ii).
      for (const [name, rv] of Object.entries(prePassResult.derived)) {
        if (quantities.some((q) => q.name === name)) continue;
        const quant: SystemQuantity = { name, value: rv.value };
        if (rv.unit) quant.unit = rv.unit;
        quantities.push(quant);
      }
      if (relationData.length === 0) {
        return { error: "Add at least one relation node to solve." };
      }
      const pending = relationData.filter((r) => !r.detail).map((r) => r.rsqName);
      if (pending.length > 0) {
        return {
          error: `Still loading relation details: ${pending.join(", ")}. Try again in a moment.`,
        };
      }
      // Port renames are passed to the backend as anvil map= semantics
      // ({relation_input: canvas_name}), so renamed inputs stay live during
      // iterative (coupled) solves instead of being copied once.
      const relations = relationData.map((r) => {
        const map: Record<string, string> = {};
        if (r.detail) {
          for (const p of r.detail.inputs) {
            const eff = effectivePortName(r, p.name);
            if (eff !== p.name) map[p.name] = eff;
          }
        }
        return Object.keys(map).length ? { name: r.rsqName, map } : r.rsqName;
      });
      return { req: { name: "builder_system", quantities, relations } };
    },
    [quantityData, relationData, prePassResult],
  );

  function solve() {
    setSolveErr(null);
    const { req, error } = buildRequest();
    if (!req) {
      if (error) setSolveErr(error);
      return;
    }
    setSolveReq(req);
  }

  // POST-PASS: when the backend solve returns, evaluate deferred blocks.
  const onSolveResult = useCallback(
    (results: Record<string, { value: number | string | boolean | null; unit: string }>) => {
      const quantities: Record<string, ResolvedValue> = {};
      for (const q of quantityData) {
        const val = Number(q.value);
        if (q.name.trim() && Number.isFinite(val))
          quantities[q.name.trim()] = { value: val, unit: q.unit.trim() };
      }
      const relationValues: Record<string, ResolvedValue> = {};
      for (const [k, rv] of Object.entries(results)) {
        if (typeof rv.value === "number")
          relationValues[k] = { value: rv.value, unit: rv.unit || "" };
      }
      const out = postPass({
        quantities,
        relationValues,
        derived: prePassResult.derived,
        blocks: blockData,
        deferredIds: prePassResult.deferred,
      });
      setNodes((ns: Node[]) =>
        ns.map((n) => {
          if (n.type !== "arith") return n;
          if (!prePassResult.deferred.includes(n.id)) return n;
          const v = out.blockValues[n.id] ?? null;
          const err = out.blockErrors[n.id] ?? null;
          return { ...n, data: { ...n.data, computed: v, computeError: err } };
        }),
      );
    },
    [quantityData, blockData, prePassResult, setNodes],
  );

  // ------------------------------- sweeps -----------------------------------
  // CLIENT-SIDE system sweep: one POST /api/system/solve per step with the
  // swept quantity's value overridden; results are recorded on the sweep node.
  const runSweep = useCallback(
    async (id: string) => {
      const node = nodes.find((n) => n.id === id);
      if (!node || node.type !== "sweep") return;
      const param = String(node.data.param ?? "").trim();
      const lo = Number(node.data.min);
      const hi = Number(node.data.max);
      const rawSteps = Math.floor(Number(node.data.steps));
      const outputs = (node.data.outputs as string[]) ?? [];

      if (!param) {
        patchData(id, { error: "set the quantity name to sweep" });
        return;
      }
      if (!Number.isFinite(lo) || !Number.isFinite(hi) || !Number.isFinite(rawSteps)) {
        patchData(id, { error: "min / max / steps must be numbers" });
        return;
      }
      if (outputs.length === 0) {
        patchData(id, { error: "pick at least one output to record" });
        return;
      }
      const n = Math.max(2, Math.min(SWEEP_MAX_STEPS, rawSteps));
      const probe = buildRequest({ name: param, value: lo });
      if (!probe.req) {
        patchData(id, { error: probe.error ?? "cannot build solve request" });
        return;
      }
      if (!probe.req.quantities.some((q) => q.name === param)) {
        patchData(id, { error: `no quantity named “${param}” on the canvas` });
        return;
      }

      patchData(id, { error: null, series: null, progress: { i: 0, n } });
      const x: number[] = [];
      const ys: Record<string, (number | null)[]> = {};
      for (const o of outputs) ys[o] = [];
      try {
        for (let i = 0; i < n; i++) {
          const v = lo + (i / (n - 1)) * (hi - lo);
          const { req } = buildRequest({ name: param, value: v });
          if (!req) throw new Error("solve request became invalid mid-sweep");
          const res = await api.solveSystem({ ...req, name: "canvas_sweep" });
          x.push(v);
          for (const o of outputs) {
            const rv = res.results[o];
            ys[o].push(rv && typeof rv.value === "number" ? rv.value : null);
          }
          patchData(id, { progress: { i: i + 1, n } });
        }
        const series: SweepSeriesData = { param, x, ys };
        patchData(id, { progress: null, series });
      } catch (e: any) {
        patchData(id, { progress: null, error: String(e?.message ?? e) });
      }
    },
    [nodes, buildRequest, patchData],
  );

  useEffect(() => {
    runSweepRef.current = runSweep;
  }, [runSweep]);

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

  // ------------------- canvas graph <-> nodes (server I/O) ------------------
  const currentGraph = useMemo(
    () => toGraph(nodes, canvasName ?? "untitled"),
    [nodes, canvasName],
  );
  const currentSig = useMemo(() => graphSignature(currentGraph), [currentGraph]);
  const dirty = nodes.length > 0 && currentSig !== savedSig;

  /** Clear the canvas and re-place every node from a (normalised) graph. */
  const restoreGraph = useCallback(
    (g: CanvasGraph) => {
      // Keep generated ids clear of preserved block ids.
      for (const b of g.blocks) {
        const m = /_(\d+)$/.exec(b.id);
        if (m) idSeq = Math.max(idSeq, Number(m[1]) + 1);
      }
      setNodes([]);
      setEdges([]);
      // Defer so the clear commits before re-adding.
      setTimeout(() => {
        for (const q of g.quantities)
          addQuantity({ name: q.name, value: String(q.value), unit: q.unit, position: q.pos });
        for (const r of g.relations) addRelation(r.name, r.pos, { ...r.renames });
        for (const b of g.blocks) {
          if (b.kind === "arith") {
            addArith(b.config.op, b.pos, b.config, b.id);
          } else if (b.kind === "sweep") {
            addSweep(b.pos, b.config, b.id);
          } else if (b.kind === "plot") {
            addPlot(b.pos, b.config, b.id);
          } else {
            addCsv(b.pos, b.config, b.id);
          }
        }
      }, 0);
    },
    [addQuantity, addRelation, addArith, addSweep, addPlot, addCsv, setNodes, setEdges],
  );

  // Crash-recovery autosave: restore silently on mount, then keep a single
  // debounced localStorage slot in sync with the working canvas.
  const autosaveReady = useRef(false);
  useEffect(() => {
    const saved = readAutosave();
    if (saved) {
      const g = fromGraph(saved.graph);
      if (!graphIsEmpty(g)) {
        setCanvasName(saved.canvasName);
        setSavedSig(saved.savedSig);
        restoreGraph(g);
      }
    }
    autosaveReady.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!autosaveReady.current) return;
    const t = window.setTimeout(
      () => writeAutosave(canvasName, savedSig, currentGraph),
      800,
    );
    return () => window.clearTimeout(t);
  }, [currentGraph, canvasName, savedSig]);

  // Toast auto-dismiss.
  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 5000);
    return () => window.clearTimeout(t);
  }, [toast]);

  const refreshCanvases = useCallback(() => {
    api
      .canvases()
      .then((r) => setServerCanvases(r.items))
      .catch(() => {
        /* list refresh is best-effort */
      });
  }, []);

  function doNew() {
    if (
      nodes.length > 0 &&
      !window.confirm("Clear the canvas? Unsaved changes will be lost.")
    )
      return;
    setNodes([]);
    setEdges([]);
    setCanvasName(null);
    setSavedSig("");
    setWarnings(null);
    setWarnNote(null);
    setSolveReq(null);
    setSolveErr(null);
  }

  const doSave = useCallback(async (): Promise<{ name: string; script: string } | null> => {
    let name = canvasName;
    if (!name) {
      const v = window.prompt("Save canvas as (letters, digits, _ and - only):", "");
      if (!v || !v.trim()) return null;
      name = v.trim();
    }
    if (!NAME_RE.test(name)) {
      setToast("invalid name — letters, digits, _ and - only");
      return null;
    }
    const graph = toGraph(nodes, name);
    try {
      const r = await api.saveCanvas(name, graph);
      setCanvasName(name);
      setSavedSig(graphSignature(graph));
      setToast(`saved ${r.path}`);
      return { name, script: r.script };
    } catch (e: any) {
      setToast(`save failed: ${String(e?.message ?? e)}`);
      return null;
    }
  }, [canvasName, nodes]);

  function doLoad(name: string) {
    api
      .canvas(name)
      .then((r) => {
        const g = fromGraph(r.canvas);
        restoreGraph(g);
        setCanvasName(r.name || name);
        setSavedSig(graphSignature(g));
        setWarnings(r.warnings?.length ? r.warnings : null);
        setWarnNote(null);
      })
      .catch((e) => setToast(`load failed: ${String(e?.message ?? e)}`));
  }

  function doDelete(name: string) {
    if (!window.confirm(`Delete saved canvas “${name}” from the server?`)) return;
    api
      .deleteCanvas(name)
      .then(() => {
        setToast(`deleted ${name}`);
        if (name === canvasName) {
          // The working copy stays; it just no longer exists server-side.
          setCanvasName(null);
          setSavedSig("");
        }
        refreshCanvases();
      })
      .catch((e) => setToast(`delete failed: ${String(e?.message ?? e)}`));
  }

  async function doDownloadPy() {
    // PUT first when unsaved/dirty so the script reflects the canvas.
    if (dirty || !canvasName) {
      const r = await doSave();
      if (r) triggerDownload(`${r.name}.py`, r.script, "text/x-python");
      return;
    }
    try {
      const r = await api.canvas(canvasName);
      triggerDownload(`${canvasName}.py`, r.script, "text/x-python");
    } catch (e: any) {
      setToast(`download failed: ${String(e?.message ?? e)}`);
    }
  }

  function doImportPy(file: File) {
    file.text().then((script) => {
      api
        .parseCanvasScript(script)
        .then((r) => {
          const g = fromGraph(r.canvas);
          if (g.quantities.length === 0 && g.relations.length === 0) {
            setWarnings(r.warnings ?? []);
            setWarnNote("This script couldn't be auto-converted (see warnings).");
            return;
          }
          restoreGraph(g);
          setCanvasName(null);
          setSavedSig("");
          setWarnings(r.warnings?.length ? r.warnings : null);
          setWarnNote(null);
        })
        .catch((e) => setToast(`import failed: ${String(e?.message ?? e)}`));
    });
  }

  // ------------------------------- examples ---------------------------------
  const [examples, setExamples] = useState<ExampleSummary[]>([]);
  const [scriptExamples, setScriptExamples] = useState<ExampleScriptItem[]>([]);
  const [examplesLoaded, setExamplesLoaded] = useState(false);
  function loadExampleMenus() {
    if (examplesLoaded) return;
    setExamplesLoaded(true);
    api
      .examples()
      .then((r) => setExamples(r.items))
      .catch(() => {
        /* curated examples unavailable */
      });
    api
      .exampleScripts()
      .then((r) => setScriptExamples(r.items))
      .catch(() => {
        /* example scripts unavailable */
      });
  }

  function loadExample(id: string) {
    api
      .example(id)
      .then((ex: ExampleCanvas) => {
        setNodes([]);
        setEdges([]);
        setCanvasName(null);
        setSavedSig("");
        setWarnings(null);
        setWarnNote(null);
        setTimeout(() => {
          const pos = ex.positions ?? {};
          for (const q of ex.quantities) {
            const value = Array.isArray(q.value) ? "" : String(q.value);
            const p = pos[q.name] ?? { x: 80, y: 80 };
            // Array-valued example quantities (e.g. signal) become CSV nodes
            // (single-column producers); scalars stay quantities.
            if (Array.isArray(q.value)) {
              addCsv(p, { name: q.name, text: `${q.name}\n${q.value.join("\n")}` });
            } else {
              addQuantity({ name: q.name, value, unit: q.unit, position: p });
            }
          }
          for (const rel of ex.relations) {
            const p = pos[rel] ?? { x: 360, y: 140 };
            addRelation(rel, p);
          }
        }, 0);
      })
      .catch((e) => setToast(`example failed: ${String(e?.message ?? e)}`));
  }

  function loadScriptExample(id: string) {
    api
      .exampleScript(id)
      .then((r) => {
        const g = fromGraph(r.canvas);
        if (g.quantities.length === 0 && g.relations.length === 0) {
          setWarnings(r.warnings ?? []);
          setWarnNote("This script couldn't be auto-converted (see warnings).");
          return;
        }
        restoreGraph(g);
        setCanvasName(null);
        setSavedSig("");
        setWarnings(r.warnings?.length ? r.warnings : null);
        setWarnNote(null);
      })
      .catch((e) => setToast(`example failed: ${String(e?.message ?? e)}`));
  }

  const relationEntries = entries.filter((e) => e.type === "R" || e.type === "S");
  const paletteGroups = groupByDomain(relationEntries);
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="builder">
      <aside className="builder-palette">
        <div className="palette-head">Palette</div>
        <div className="calc-page-tabs">
          <button
            className={`subtab ${paletteTab === "relations" ? "active" : ""}`}
            onClick={() => setPaletteTab("relations")}
          >
            Relations
          </button>
          <button
            className={`subtab ${paletteTab === "blocks" ? "active" : ""}`}
            onClick={() => setPaletteTab("blocks")}
          >
            Blocks
          </button>
        </div>

        {paletteTab === "relations" ? (
          <>
            <p className="palette-hint">
              Drag a relation onto the canvas, or add a quantity. Edges wire
              automatically by matching variable names.
            </p>
            <button className="run-btn add-q-btn" onClick={() => addQuantity()}>
              + Quantity node
            </button>
            <div className="palette-list">
              {paletteGroups.map((g) => {
                const open = !collapsedDomains[g.domain];
                return (
                  <section key={g.domain} className="domain-group">
                    <button
                      className="domain-head"
                      onClick={() =>
                        setCollapsedDomains((c) => ({ ...c, [g.domain]: !c[g.domain] }))
                      }
                      aria-expanded={open}
                    >
                      <span className="domain-caret">{open ? "▾" : "▸"}</span>
                      <span className="domain-name">{g.domain}</span>
                      <span className="domain-count">{g.entries.length}</span>
                    </button>
                    {open &&
                      g.entries.map((e) => (
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
                          <a
                            className="palette-doc"
                            href={rsqDocsUrl(e.name)}
                            {...NEW_TAB}
                            title={`Docs for ${e.name}`}
                            onClick={(ev) => ev.stopPropagation()}
                            onDragStart={(ev) => ev.preventDefault()}
                          >
                            ↗
                          </a>
                          <span className={`badge badge-${e.type}`}>{e.type}</span>
                        </div>
                      ))}
                  </section>
                );
              })}
              {relationEntries.length === 0 && (
                <div className="muted palette-empty">No relations in registry.</div>
              )}
            </div>
          </>
        ) : (
          <div className="palette-list">
            <p className="palette-hint">
              Drag a block onto the canvas. Blocks compute client-side and feed
              relations by output name.
            </p>
            <section className="domain-group">
              <div className="domain-head static">
                <span className="domain-name">Data</span>
              </div>
              <div
                className="palette-item"
                draggable
                onDragStart={(ev) => {
                  ev.dataTransfer.setData("application/anvil-special", "quantity");
                  ev.dataTransfer.effectAllowed = "copy";
                }}
                onDoubleClick={() => addQuantity()}
              >
                <span className="palette-name">quantity</span>
                <span className="badge badge-Q">Q</span>
              </div>
              <div
                className="palette-item"
                draggable
                onDragStart={(ev) => {
                  ev.dataTransfer.setData("application/anvil-special", "csv");
                  ev.dataTransfer.effectAllowed = "copy";
                }}
                onDoubleClick={() => addCsv()}
              >
                <span className="palette-name">CSV data</span>
                <span className="badge badge-Q">CSV</span>
              </div>
            </section>
            <section className="domain-group">
              <div className="domain-head static">
                <span className="domain-name">Analysis</span>
              </div>
              <div
                className="palette-item"
                draggable
                onDragStart={(ev) => {
                  ev.dataTransfer.setData("application/anvil-special", "sweep");
                  ev.dataTransfer.effectAllowed = "copy";
                }}
                onDoubleClick={() => addSweep()}
                title="Sweep a quantity across a range, re-solving the system each step"
              >
                <span className="palette-name">sweep</span>
                <span className="palette-sym">x: a→b</span>
              </div>
              <div
                className="palette-item"
                draggable
                onDragStart={(ev) => {
                  ev.dataTransfer.setData("application/anvil-special", "plot");
                  ev.dataTransfer.effectAllowed = "copy";
                }}
                onDoubleClick={() => addPlot()}
                title="Plot a sweep block's recorded series"
              >
                <span className="palette-name">plot</span>
                <span className="palette-sym">y(x)</span>
              </div>
            </section>
            {BLOCK_SECTIONS.map((sec) => (
              <section key={sec.title} className="domain-group">
                <div className="domain-head static">
                  <span className="domain-name">{sec.title}</span>
                  <span className="domain-count">{sec.ops.length}</span>
                </div>
                {sec.ops.map((op) => (
                  <div
                    key={op}
                    className="palette-item"
                    draggable
                    onDragStart={(ev) => {
                      ev.dataTransfer.setData("application/anvil-arith", op);
                      ev.dataTransfer.effectAllowed = "copy";
                    }}
                    onDoubleClick={() => addArith(op)}
                    title={ARITH_SPECS[op].label}
                  >
                    <span className="palette-name">{ARITH_SPECS[op].label}</span>
                    <span className="palette-sym">{ARITH_SPECS[op].symbol}</span>
                  </div>
                ))}
              </section>
            ))}
          </div>
        )}
      </aside>

      <div className="builder-canvas" ref={wrapRef}>
        <div className="builder-toolbar">
          <button
            className="run-btn"
            onClick={solve}
            disabled={relationData.length === 0}
            title="Streams residuals live; falls back to plain HTTP automatically."
          >
            Solve
          </button>

          <span className="toolbar-sep" />

          <span
            className="canvas-name"
            title={dirty ? "unsaved changes" : "saved"}
          >
            {canvasName ?? "untitled"}
            {dirty ? " *" : ""}
          </span>

          <button className="ghost-btn toolbar-btn" onClick={doNew}>
            New
          </button>
          <button
            className="ghost-btn toolbar-btn"
            onClick={() => void doSave()}
            disabled={nodes.length === 0}
            title="Save the canvas to the server as a python script"
          >
            Save
          </button>

          <select
            className="trace-select toolbar-menu"
            value=""
            onMouseDown={refreshCanvases}
            onChange={(e) => {
              if (e.target.value) doLoad(e.target.value);
            }}
            aria-label="Load a saved canvas"
          >
            <option value="">Load ▾</option>
            {serverCanvases.map((c) => (
              <option key={c.name} value={c.name} title={c.description}>
                {c.name}
              </option>
            ))}
            {serverCanvases.length === 0 && <option disabled>no saved canvases</option>}
          </select>

          <select
            className="trace-select toolbar-menu"
            value=""
            onMouseDown={refreshCanvases}
            onChange={(e) => {
              if (e.target.value) doDelete(e.target.value);
            }}
            aria-label="Delete a saved canvas"
          >
            <option value="">Delete ▾</option>
            {serverCanvases.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
            {serverCanvases.length === 0 && <option disabled>no saved canvases</option>}
          </select>

          <button
            className="ghost-btn toolbar-btn"
            onClick={() => void doDownloadPy()}
            disabled={nodes.length === 0}
            title="Download this canvas as a python script (saves first if needed)"
          >
            Download .py
          </button>
          <button
            className="ghost-btn toolbar-btn"
            onClick={() => fileInputRef.current?.click()}
            title="Import a python script and convert it to a canvas"
          >
            Import .py
          </button>

          <select
            className="trace-select toolbar-menu"
            value=""
            onMouseDown={loadExampleMenus}
            onChange={(e) => {
              const v = e.target.value;
              if (v.startsWith("ex:")) loadExample(v.slice(3));
              else if (v.startsWith("py:")) loadScriptExample(v.slice(3));
            }}
            aria-label="Example canvases"
          >
            <option value="">Examples ▾</option>
            <optgroup label="Curated canvases">
              {examples.map((ex) => (
                <option key={ex.id} value={`ex:${ex.id}`}>
                  {ex.name}
                </option>
              ))}
              {examplesLoaded && examples.length === 0 && (
                <option disabled>none available</option>
              )}
            </optgroup>
            <optgroup label="Example scripts (best-effort)">
              {scriptExamples.map((ex) => (
                <option key={ex.id} value={`py:${ex.id}`}>
                  {ex.title}
                </option>
              ))}
              {examplesLoaded && scriptExamples.length === 0 && (
                <option disabled>none available</option>
              )}
            </optgroup>
            {!examplesLoaded && <option disabled>loading…</option>}
          </select>

          <input
            ref={fileInputRef}
            type="file"
            accept=".py,text/x-python"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) doImportPy(f);
              e.target.value = "";
            }}
          />

          {toast && <span className="toolbar-toast">{toast}</span>}

          <span className="builder-stat">
            {relationData.length} rel · {quantityData.length} qty · {blockData.length} blk · {wires.length} wire
          </span>
          {missing.length > 0 && (
            <span className="builder-missing" title="Inputs not produced by any node">
              unresolved: {missing.join(", ")}
            </span>
          )}
        </div>

        {(warnings !== null || warnNote) && (
          <div className="canvas-warn-banner" role="status">
            <div className="canvas-warn-head">
              <span>{warnNote ?? "Converted with warnings:"}</span>
              <button
                className="gnode-x"
                onClick={() => {
                  setWarnings(null);
                  setWarnNote(null);
                }}
                title="Dismiss"
                aria-label="Dismiss warnings"
              >
                ×
              </button>
            </div>
            {warnings && warnings.length > 0 && (
              <ul className="canvas-warn-list">
                {warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
          </div>
        )}

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
              Drag a relation or block from the palette, or load an example, to begin.
            </div>
          )}
        </div>
      </div>

      <aside className="builder-results">
        <div className="palette-head">Solve</div>
        {effectiveNote.length > 0 && (
          <div className="muted rename-note">renamed: {effectiveNote.join(", ")}</div>
        )}
        {Object.keys(prePassResult.derived).length > 0 && (
          <div className="muted rename-note">
            derived: {Object.entries(prePassResult.derived)
              .map(([k, v]) => `${k}=${fmtNum(v.value)}`)
              .join(", ")}
          </div>
        )}
        {solveErr && <div className="panel error">{solveErr}</div>}
        {solveReq ? (
          <SystemSolvePanel
            key={JSON.stringify(solveReq)}
            request={solveReq}
            live={true}
            onResult={onSolveResult}
          />
        ) : (
          <p className="muted">
            Wire up a System and press “Solve”. Residuals and results appear here.
            Use a sweep block on the canvas to scan a quantity, and a plot block
            to chart it.
          </p>
        )}
      </aside>
    </div>
  );
}

export function Builder({ entries, dropRequest }: Props) {
  return (
    <ReactFlowProvider>
      <BuilderInner entries={entries} dropRequest={dropRequest} />
    </ReactFlowProvider>
  );
}
