// Types mirror the anvil_server Pydantic response models, which in turn mirror
// the real Anvil objects in src/anvil/system.py and src/anvil/inspect.py.

export interface RegistryEntry {
  name: string;
  type: string; // "R" | "S" | "Q"
  domain: string;
  description: string;
  tags: string[];
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

// Input value sent to /api/solve: either a bare scalar or {value, unit}.
export type SolveInputValue = number | string | boolean | { value: number; unit: string };

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

export interface SystemSolveRequest {
  name?: string;
  quantities: SystemQuantity[];
  relations: string[];
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
