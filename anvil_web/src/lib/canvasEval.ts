// Client-side canvas evaluation passes (A3).
//
// The canvas mixes three node kinds that produce named values:
//   - quantity nodes          (concrete user values)
//   - relation nodes (RSQs)   (solved on the backend; outputs known only after)
//   - arithmetic/transform    (pure, evaluated here in the browser)
//
// Solving is done in passes:
//   PRE-PASS  — topologically evaluate arithmetic blocks that depend ONLY on
//               quantity values or other already-resolved blocks. Their results
//               become extra concrete quantities sent to /api/system/solve.
//   (solve)   — backend solves the relation network with originals + pre-pass.
//   POST-PASS — evaluate arithmetic blocks that depend on relation OUTPUTS, for
//               display only.
//
// Cycles through arithmetic are detected: if a block needs a name that is only
// produced by a relation which itself (transitively) consumes the block's
// output, we cannot place it in the pre-pass; it is reported as a cycle.

import {
  ARITH_SPECS,
  computeArith,
  expressionVariablesFor,
  propagateUnit,
} from "./arithmetic";
import type { ArithBlockModel } from "./arithmetic";

export interface ResolvedValue {
  value: number;
  unit: string;
}

export interface PrePassResult {
  /** name -> resolved value, for blocks evaluable before the backend solve. */
  derived: Record<string, ResolvedValue>;
  /** blockNodeId -> computed value (for on-node display). */
  blockValues: Record<string, ResolvedValue>;
  /** blockNodeId -> error string (unresolved dep, cycle, or compute error). */
  blockErrors: Record<string, string>;
  /** Block node ids that depend on relation outputs (deferred to post-pass). */
  deferred: string[];
}

export interface CanvasEvalInput {
  /** Concrete quantity-node values keyed by their (effective) name. */
  quantities: Record<string, ResolvedValue>;
  /** Names produced by relation OUTPUT ports (values unknown pre-solve). */
  relationOutputs: Set<string>;
  /** Arithmetic/transform blocks on the canvas. */
  blocks: ArithBlockModel[];
}

/** Inputs (port -> source variable name) a block consumes. */
function blockInputNames(b: ArithBlockModel): string[] {
  const spec = ARITH_SPECS[b.op];
  if (spec.arity === "expression") {
    return expressionVariablesFor(b.expression ?? "");
  }
  // Each port maps to a source variable; default to the port name itself but
  // allow a per-port override (so two "x" ports across blocks don't collide).
  return spec.ports.map((p) => (b.portSources?.[p]?.trim() || p));
}

/**
 * Run the PRE-PASS: resolve every block that can be computed from quantities
 * and other resolved blocks, in dependency order. Returns derived values plus
 * the list of blocks deferred to the post-pass (depend on relation outputs).
 */
export function prePass(input: CanvasEvalInput): PrePassResult {
  const { quantities, relationOutputs, blocks } = input;

  // Map: produced-name -> block (a block produces its output name).
  const byOutput = new Map<string, ArithBlockModel>();
  for (const b of blocks) {
    const out = (b.outName?.trim() || ARITH_SPECS[b.op].defaultOut);
    byOutput.set(out, b);
  }

  const derived: Record<string, ResolvedValue> = {};
  const blockValues: Record<string, ResolvedValue> = {};
  const blockErrors: Record<string, string> = {};
  const deferred: string[] = [];

  // Topological evaluation with cycle detection over the block graph.
  const visiting = new Set<string>(); // block node ids on the current stack
  const done = new Set<string>(); // block node ids resolved or terminally failed

  // Resolve a NAME to a value: quantity, already-derived block, or recurse into
  // the producing block. Returns null if it can't be resolved pre-solve.
  function resolveName(name: string): ResolvedValue | null | "deferred" {
    if (name in quantities) return quantities[name];
    if (name in derived) return derived[name];
    if (relationOutputs.has(name)) return "deferred";
    const producer = byOutput.get(name);
    if (producer) {
      const ok = resolveBlock(producer);
      if (ok === "deferred") return "deferred";
      if (ok && name in derived) return derived[name];
    }
    return null;
  }

  function resolveBlock(b: ArithBlockModel): boolean | "deferred" {
    if (done.has(b.id)) {
      return b.id in blockValues ? true : b.id in blockErrors ? false : false;
    }
    if (visiting.has(b.id)) {
      blockErrors[b.id] = "cycle: this block depends on itself";
      done.add(b.id);
      return false;
    }
    visiting.add(b.id);

    const spec = ARITH_SPECS[b.op];
    const inputNames = blockInputNames(b);
    const portVals: Record<string, number> = {};
    const portUnits: Record<string, string> = {};
    let deferredDep = false;

    // For named-port ops we map ports -> source names positionally; for the
    // expression op we resolve each referenced variable by name.
    const resolveInto = (key: string, name: string): boolean => {
      const r = resolveName(name);
      if (r === "deferred") {
        deferredDep = true;
        return false;
      }
      if (r == null) {
        blockErrors[b.id] = `unresolved input: ${name}`;
        return false;
      }
      portVals[key] = r.value;
      portUnits[key] = r.unit;
      return true;
    };

    let ok = true;
    if (spec.arity === "expression") {
      for (const name of inputNames) {
        if (!resolveInto(name, name)) ok = false;
      }
    } else {
      spec.ports.forEach((port, i) => {
        if (!resolveInto(port, inputNames[i])) ok = false;
      });
    }

    visiting.delete(b.id);

    if (deferredDep) {
      // Needs a relation output — defer to post-pass (not an error).
      done.add(b.id);
      if (!deferred.includes(b.id)) deferred.push(b.id);
      return "deferred";
    }
    if (!ok) {
      done.add(b.id);
      return false;
    }

    // Compute.
    let value: number;
    try {
      if (spec.arity === "expression") {
        value = evalExpressionSafe(b.expression ?? "", portVals);
      } else {
        value = computeArith(b.op, portVals, { a: b.a, b: b.b });
      }
    } catch (e: any) {
      blockErrors[b.id] = String(e?.message ?? e);
      done.add(b.id);
      return false;
    }
    if (!Number.isFinite(value)) {
      blockErrors[b.id] = "result is not finite";
      done.add(b.id);
      return false;
    }

    const unit =
      spec.arity === "expression" ? "" : propagateUnit(b.op, portUnits);
    const rv: ResolvedValue = { value, unit };
    const outName = b.outName?.trim() || spec.defaultOut;
    blockValues[b.id] = rv;
    derived[outName] = rv;
    done.add(b.id);
    return true;
  }

  for (const b of blocks) resolveBlock(b);

  return { derived, blockValues, blockErrors, deferred };
}

export interface PostPassInput {
  quantities: Record<string, ResolvedValue>;
  /** All resolved relation outputs after the backend solve. */
  relationValues: Record<string, ResolvedValue>;
  /** Pre-pass derived values (still valid). */
  derived: Record<string, ResolvedValue>;
  blocks: ArithBlockModel[];
  /** Only these block ids were deferred. */
  deferredIds: string[];
}

/**
 * Run the POST-PASS: evaluate deferred blocks now that relation outputs are
 * known. Display-only. Resolves recursively across blocks too.
 */
export function postPass(input: PostPassInput): {
  blockValues: Record<string, ResolvedValue>;
  blockErrors: Record<string, string>;
} {
  const { quantities, relationValues, derived, blocks } = input;
  const blockValues: Record<string, ResolvedValue> = {};
  const blockErrors: Record<string, string> = {};

  const byId = new Map(blocks.map((b) => [b.id, b]));
  const byOutput = new Map<string, ArithBlockModel>();
  for (const b of blocks) {
    const out = b.outName?.trim() || ARITH_SPECS[b.op].defaultOut;
    byOutput.set(out, b);
  }

  const env: Record<string, ResolvedValue> = {
    ...quantities,
    ...derived,
    ...relationValues,
  };

  const visiting = new Set<string>();
  const done = new Set<string>();

  function resolveName(name: string): ResolvedValue | null {
    if (name in env) return env[name];
    const producer = byOutput.get(name);
    if (producer) {
      if (resolveBlock(producer)) return env[name] ?? null;
    }
    return null;
  }

  function resolveBlock(b: ArithBlockModel): boolean {
    if (done.has(b.id)) return b.id in blockValues;
    if (visiting.has(b.id)) {
      blockErrors[b.id] = "cycle: this block depends on itself";
      done.add(b.id);
      return false;
    }
    visiting.add(b.id);
    const spec = ARITH_SPECS[b.op];
    const inputNames = blockInputNames(b);
    const portVals: Record<string, number> = {};
    const portUnits: Record<string, string> = {};
    let ok = true;

    const grab = (key: string, name: string) => {
      const r = resolveName(name);
      if (r == null) {
        blockErrors[b.id] = `unresolved input: ${name}`;
        ok = false;
        return;
      }
      portVals[key] = r.value;
      portUnits[key] = r.unit;
    };

    if (spec.arity === "expression") {
      for (const name of inputNames) grab(name, name);
    } else {
      spec.ports.forEach((port, i) => grab(port, inputNames[i]));
    }
    visiting.delete(b.id);
    if (!ok) {
      done.add(b.id);
      return false;
    }
    let value: number;
    try {
      value =
        spec.arity === "expression"
          ? evalExpressionSafe(b.expression ?? "", portVals)
          : computeArith(b.op, portVals, { a: b.a, b: b.b });
    } catch (e: any) {
      blockErrors[b.id] = String(e?.message ?? e);
      done.add(b.id);
      return false;
    }
    if (!Number.isFinite(value)) {
      blockErrors[b.id] = "result is not finite";
      done.add(b.id);
      return false;
    }
    const unit = spec.arity === "expression" ? "" : propagateUnit(b.op, portUnits);
    const rv: ResolvedValue = { value, unit };
    blockValues[b.id] = rv;
    env[b.outName?.trim() || spec.defaultOut] = rv;
    done.add(b.id);
    return true;
  }

  for (const id of input.deferredIds) {
    const b = byId.get(id);
    if (b) resolveBlock(b);
  }
  return { blockValues, blockErrors };
}

// Local import to avoid a circular dependency note: evalExpression lives in expr.ts.
import { evalExpression } from "./expr";
function evalExpressionSafe(src: string, vars: Record<string, number>): number {
  if (!src.trim()) throw new Error("empty expression");
  return evalExpression(src, vars);
}
