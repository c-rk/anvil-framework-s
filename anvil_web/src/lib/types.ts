// Types mirror the anvil_server Pydantic response models, which in turn mirror
// the real Anvil objects in src/anvil/system.py and src/anvil/inspect.py.

export interface RegistryEntry {
  name: string;
  type: string; // "R" | "S" | "Q"
  domain: string;
  description: string;
  tags: string[];
  // Optional fields the backend may add (degrade gracefully if absent).
  // `calculator_ok` flags RSQs the single-RSQ Calculator can solve directly;
  // `array_input` flags RSQs that accept vector/array inputs;
  // `adapter` flags RSQs that wrap an external solver/library.
  calculator_ok?: boolean;
  array_input?: boolean;
  adapter?: boolean;
  /** True when the RSQ comes from a mounted project registry (--project). */
  project?: boolean;
}

export interface RsqDetailFull extends RsqDetail {
  calculator_ok?: boolean;
  array_input?: boolean;
  adapter?: boolean;
}

export interface RegistryResponse {
  tier: string;
  native_only: boolean;
  count: number;
  items: RegistryEntry[];
}

export interface RsqInput {
  name: string;
  default: number | string | boolean | null;
  unit: string;
  desc: string;
}

export interface RsqOutput {
  name: string;
  unit: string;
  desc: string;
}

export interface RsqDetail {
  name: string;
  type: string;
  domain: string;
  description: string;
  version: string;
  signature: string;
  latex: string | null;
  inputs: RsqInput[];
  outputs: RsqOutput[];
  defaults: Record<string, number | string | boolean | null>;
  tags: string[];
  // Same flags as the registry entry (the /api/rsq/{name} endpoint includes them).
  calculator_ok?: boolean;
  array_input?: boolean;
  adapter?: boolean;
}

export interface ResultValue {
  value: number | string | boolean | null;
  unit: string;
  role: string; // "input" | "output"
}

export interface SolveResponse {
  name: string;
  method: string;
  results: Record<string, ResultValue>;
  inputs: string[];
  outputs: string[];
}

export interface HealthResponse {
  status: string;
  anvil_version: string;
  tier: string;
  native_only: boolean;
  rsq_count: number;
}

// Input value sent to /api/solve: a bare scalar, an array (time-series), or
// {value, unit} where value may itself be a scalar or array.
export type SolveScalar = number | string | boolean;
export type SolveInputValue =
  | SolveScalar
  | SolveScalar[]
  | { value: number | number[]; unit: string };

// ---- Live solve (WS /ws/solve) frames -------------------------------------

export interface WsIterFrame {
  type: "iter";
  iter: number;
  residual: number;
}

// The final result frame mirrors SolveResponse with a discriminant tag.
export interface WsResultFrame extends SolveResponse {
  type: "result";
}

export interface WsErrorFrame {
  type: "error";
  message: string;
}

export type WsFrame = WsIterFrame | WsResultFrame | WsErrorFrame;

// ---- Sweep (POST /api/sweep) ----------------------------------------------

export interface SweepRequest {
  name: string;
  param: string;
  values: number[];
  outputs?: string[];
  inputs?: Record<string, SolveInputValue>;
  si?: boolean;
}

export interface SweepResponse {
  name: string;
  param: string;
  // Each key is a column (the swept param plus each output); values are aligned
  // arrays of one entry per sweep step.
  data: Record<string, (number | null)[]>;
  outputs: string[];
}

// ---- System solve (POST /api/system/solve, WS /ws/system/solve) ------------

export interface SystemQuantity {
  name: string;
  value: number;
  unit?: string;
}

/** Relation by registry name with optional input renames (anvil map= semantics:
 *  {relation_input_name: canvas_quantity_name}). Plain strings still accepted. */
export interface SystemRelationSpec {
  name: string;
  map?: Record<string, string>;
}

export interface SystemSolveRequest {
  name?: string;
  quantities: SystemQuantity[];
  relations: (string | SystemRelationSpec)[];
  method?: string;
  max_iter?: number;
  rtol?: number;
}

export interface SystemHistoryPoint {
  iter: number;
  residual: number;
}

export interface SystemSolveResponse {
  name: string;
  method: string;
  results: Record<string, ResultValue>;
  history: SystemHistoryPoint[];
  inputs: string[];
  outputs: string[];
}

// ---- Live system solve (WS /ws/system/solve) frames ------------------------

export interface SysWsIterFrame {
  type: "iter";
  iter: number;
  residual: number;
  // Optional per-iteration variable snapshot (for the variable-trace plot).
  variables?: Record<string, number>;
}

export interface SysWsResultFrame extends SystemSolveResponse {
  type: "result";
}

export interface SysWsErrorFrame {
  type: "error";
  message: string;
}

export type SystemWsFrame =
  | SysWsIterFrame
  | SysWsResultFrame
  | SysWsErrorFrame;

// ---- CSV data (POST /api/data/csv) ----------------------------------------

export interface CsvResponse {
  columns: string[];
  rows: number;
  preview: Record<string, unknown>[];
  // Each column -> aligned array of (downsampled) values.
  data: Record<string, (number | string | null)[]>;
}

// ---- Example canvases (GET /api/examples, /api/examples/{id}) --------------

export interface ExampleSummary {
  id: string;
  name: string;
  description: string;
  domain: string;
  relations: string[];
  array_input: boolean;
  n_quantities: number;
}

export interface ExampleListResponse {
  count: number;
  items: ExampleSummary[];
}

export interface ExampleQuantity {
  name: string;
  value: number | string | number[];
  unit: string;
}

export interface ExampleCanvas {
  id: string;
  name: string;
  description: string;
  domain?: string;
  quantities: ExampleQuantity[];
  relations: string[];
  positions?: Record<string, { x: number; y: number }>;
  array_input?: boolean;
}

// ---- Server-side canvases (GET/PUT/DELETE /api/canvases) -------------------
// The `canvas` payloads carry the backend CanvasGraph shape; they are coerced
// client-side via fromGraph() in lib/canvasGraph.ts, hence `unknown` here.

export interface CanvasListItem {
  name: string;
  description: string;
  modified: string;
}

export interface CanvasListResponse {
  items: CanvasListItem[];
}

export interface CanvasGetResponse {
  name: string;
  script: string;
  canvas: unknown;
  warnings: string[];
}

export interface CanvasPutResponse {
  script: string;
  path: string;
}

export interface CanvasParseResponse {
  canvas: unknown;
  warnings: string[];
}

// ---- Example scripts (GET /api/example-scripts) -----------------------------

export interface ExampleScriptItem {
  id: string;
  title: string;
}

export interface ExampleScriptListResponse {
  items: ExampleScriptItem[];
}

export interface ExampleScriptResponse {
  script: string;
  canvas: unknown;
  warnings: string[];
}

// ---- Server-side plot (POST /api/viz/sweep, /api/viz/convergence) ----------

export interface VizSweepRequest {
  name: string;
  param: string;
  values: number[];
  outputs?: string[];
  inputs?: Record<string, SolveInputValue>;
  si?: boolean;
}

export interface VizResponse {
  png_base64: string;
}
