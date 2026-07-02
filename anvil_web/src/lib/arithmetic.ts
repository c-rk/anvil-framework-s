// Arithmetic / transform block definitions for the Canvas.
//
// Each block kind declares its input PORT NAMES and a pure compute function.
// Compute runs entirely client-side (see the eval passes in canvasEval.ts).
// A block exposes ONE named output value whose name is editable so multiple
// blocks don't collide when auto-wired by variable name.

import { expressionVariables } from "./expr";

export type ArithOp =
  | "add"
  | "subtract"
  | "multiply"
  | "divide"
  | "power"
  | "negate"
  | "abs"
  | "sqrt"
  | "exp"
  | "ln"
  | "log10"
  | "sin"
  | "cos"
  | "tan"
  | "sin_deg"
  | "cos_deg"
  | "tan_deg"
  | "scale_offset"
  | "expression";

export interface ArithSpec {
  op: ArithOp;
  label: string;
  /** Display symbol/short form for the node header. */
  symbol: string;
  /** Fixed input port names (for the named-port ops). Empty for expression. */
  ports: string[];
  /**
   * For unary ops the single port; binary ops have two ports. `expression`
   * derives ports dynamically from the formula text.
   */
  arity: "unary" | "binary" | "scale_offset" | "expression";
  /** Default editable output name. */
  defaultOut: string;
}

const D = (Math.PI / 180);

export const ARITH_SPECS: Record<ArithOp, ArithSpec> = {
  add: { op: "add", label: "Add", symbol: "a + b", ports: ["a", "b"], arity: "binary", defaultOut: "sum" },
  subtract: { op: "subtract", label: "Subtract", symbol: "a − b", ports: ["a", "b"], arity: "binary", defaultOut: "diff" },
  multiply: { op: "multiply", label: "Multiply", symbol: "a × b", ports: ["a", "b"], arity: "binary", defaultOut: "prod" },
  divide: { op: "divide", label: "Divide", symbol: "a ÷ b", ports: ["a", "b"], arity: "binary", defaultOut: "quot" },
  power: { op: "power", label: "Power", symbol: "a ^ b", ports: ["a", "b"], arity: "binary", defaultOut: "pow" },
  negate: { op: "negate", label: "Negate", symbol: "−x", ports: ["x"], arity: "unary", defaultOut: "neg" },
  abs: { op: "abs", label: "Absolute", symbol: "|x|", ports: ["x"], arity: "unary", defaultOut: "absval" },
  sqrt: { op: "sqrt", label: "Square root", symbol: "√x", ports: ["x"], arity: "unary", defaultOut: "root" },
  exp: { op: "exp", label: "Exponential", symbol: "eˣ", ports: ["x"], arity: "unary", defaultOut: "expv" },
  ln: { op: "ln", label: "Natural log", symbol: "ln x", ports: ["x"], arity: "unary", defaultOut: "lnv" },
  log10: { op: "log10", label: "Log base 10", symbol: "log₁₀ x", ports: ["x"], arity: "unary", defaultOut: "logv" },
  sin: { op: "sin", label: "Sine (rad)", symbol: "sin x", ports: ["x"], arity: "unary", defaultOut: "sinv" },
  cos: { op: "cos", label: "Cosine (rad)", symbol: "cos x", ports: ["x"], arity: "unary", defaultOut: "cosv" },
  tan: { op: "tan", label: "Tangent (rad)", symbol: "tan x", ports: ["x"], arity: "unary", defaultOut: "tanv" },
  sin_deg: { op: "sin_deg", label: "Sine (deg)", symbol: "sin x°", ports: ["x"], arity: "unary", defaultOut: "sinv" },
  cos_deg: { op: "cos_deg", label: "Cosine (deg)", symbol: "cos x°", ports: ["x"], arity: "unary", defaultOut: "cosv" },
  tan_deg: { op: "tan_deg", label: "Tangent (deg)", symbol: "tan x°", ports: ["x"], arity: "unary", defaultOut: "tanv" },
  scale_offset: { op: "scale_offset", label: "Scale + offset", symbol: "a·x + b", ports: ["x"], arity: "scale_offset", defaultOut: "y" },
  expression: { op: "expression", label: "Expression", symbol: "f(…)", ports: [], arity: "expression", defaultOut: "result" },
};

export const ARITH_OPS: ArithOp[] = Object.keys(ARITH_SPECS) as ArithOp[];

/**
 * Serializable model of an arithmetic/transform block on the canvas. Stored on
 * the React Flow node's `data` and used by the eval passes + save/load.
 */
export interface ArithBlockModel {
  /** React Flow node id. */
  id: string;
  op: ArithOp;
  /** Editable output variable name (defaults to the spec's defaultOut). */
  outName: string;
  /** Per-port source-name override: port -> upstream variable name. */
  portSources?: Record<string, string>;
  /** scale_offset coefficients. */
  a?: number;
  b?: number;
  /** Free formula for the expression op. */
  expression?: string;
}

/** Variables referenced by an expression block's formula. */
export function expressionVariablesFor(src: string): string[] {
  return expressionVariables(src);
}

/** Compute a unary/binary/scale op from resolved port values. */
export function computeArith(
  op: ArithOp,
  ports: Record<string, number>,
  cfg: { a?: number; b?: number },
): number {
  const x = ports.x;
  const a = ports.a;
  const b = ports.b;
  switch (op) {
    case "add":
      return a + b;
    case "subtract":
      return a - b;
    case "multiply":
      return a * b;
    case "divide":
      return a / b;
    case "power":
      return Math.pow(a, b);
    case "negate":
      return -x;
    case "abs":
      return Math.abs(x);
    case "sqrt":
      return Math.sqrt(x);
    case "exp":
      return Math.exp(x);
    case "ln":
      return Math.log(x);
    case "log10":
      return Math.log10(x);
    case "sin":
      return Math.sin(x);
    case "cos":
      return Math.cos(x);
    case "tan":
      return Math.tan(x);
    case "sin_deg":
      return Math.sin(x * D);
    case "cos_deg":
      return Math.cos(x * D);
    case "tan_deg":
      return Math.tan(x * D);
    case "scale_offset":
      return (cfg.a ?? 1) * x + (cfg.b ?? 0);
    default:
      throw new Error(`computeArith does not handle ${op}`);
  }
}

/**
 * Best-effort unit propagation for an arithmetic op given input units.
 * Conservative: only carries a unit where it is unambiguous; otherwise "".
 */
export function propagateUnit(
  op: ArithOp,
  units: Record<string, string>,
): string {
  const ux = units.x ?? "";
  const ua = units.a ?? "";
  const ub = units.b ?? "";
  switch (op) {
    case "add":
    case "subtract":
      // Same unit if both agree.
      return ua && ua === ub ? ua : ua || ub ? "" : "";
    case "negate":
    case "abs":
    case "scale_offset":
      return ux;
    // Products/quotients/powers/transcendentals: drop to unitless.
    default:
      return "";
  }
}
