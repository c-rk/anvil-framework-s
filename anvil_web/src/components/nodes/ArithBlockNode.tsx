import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  ARITH_OPS,
  ARITH_SPECS,
  expressionVariablesFor,
  type ArithBlockModel,
  type ArithOp,
} from "../../lib/arithmetic";

export interface ArithBlockFields extends ArithBlockModel {
  /** Computed value + unit (from the eval pass) for on-node display. */
  computed?: { value: number; unit: string } | null;
  computeError?: string | null;
  onChange: (patch: Partial<ArithBlockModel>) => void;
  onRemove: () => void;
}

const fmt = (v: number): string => {
  const a = Math.abs(v);
  if (v === 0) return "0";
  if (a >= 1e6 || a < 1e-3) return v.toExponential(4);
  return v.toPrecision(6).replace(/\.?0+$/, "");
};

/**
 * Arithmetic / transform block node. Inputs enter on the left (one handle per
 * port), the single named output leaves on the right. The output name is
 * editable so blocks don't collide when auto-wired by variable name.
 */
export function ArithBlockNode({ data }: NodeProps) {
  const d = data as unknown as ArithBlockFields;
  const spec = ARITH_SPECS[d.op];
  const exprPorts =
    spec.arity === "expression" ? expressionVariablesFor(d.expression ?? "") : [];
  const ports = spec.arity === "expression" ? exprPorts : spec.ports;
  const outName = d.outName?.trim() || spec.defaultOut;

  return (
    <div className="gnode gnode-arith">
      <div className="gnode-head">
        <span className="gnode-kind">block</span>
        <span className="gnode-title">{spec.symbol}</span>
        <button
          className="gnode-x"
          onClick={d.onRemove}
          title="Remove node"
          aria-label="Remove node"
        >
          ×
        </button>
      </div>

      <select
        className="gnode-op nodrag"
        value={d.op}
        onChange={(e) => d.onChange({ op: e.target.value as ArithOp })}
        aria-label="Operation"
      >
        {ARITH_OPS.map((op) => (
          <option key={op} value={op}>
            {ARITH_SPECS[op].label}
          </option>
        ))}
      </select>

      {spec.arity === "expression" && (
        <input
          className="gnode-expr nodrag"
          value={d.expression ?? ""}
          placeholder="e.g. a*sin(b) + 2"
          onChange={(e) => d.onChange({ expression: e.target.value })}
          aria-label="Expression"
        />
      )}

      {spec.arity === "scale_offset" && (
        <div className="gnode-coeffs nodrag">
          <label className="gnode-coeff">
            <span>a</span>
            <input
              type="number"
              step="any"
              value={d.a ?? 1}
              onChange={(e) => d.onChange({ a: Number(e.target.value) })}
              aria-label="scale a"
            />
          </label>
          <label className="gnode-coeff">
            <span>b</span>
            <input
              type="number"
              step="any"
              value={d.b ?? 0}
              onChange={(e) => d.onChange({ b: Number(e.target.value) })}
              aria-label="offset b"
            />
          </label>
        </div>
      )}

      <div className="gnode-ports">
        <ul className="gnode-port-col gnode-ins">
          {ports.map((port, i) => (
            <li key={port + i} className="gnode-portrow">
              <Handle
                type="target"
                position={Position.Left}
                id={`in:${port}`}
                className="gnode-port gnode-port-in"
              />
              {spec.arity === "expression" ? (
                <span className="gnode-portlabel" title={`variable ${port}`}>
                  {port}
                </span>
              ) : (
                <input
                  className="gnode-portname nodrag"
                  value={d.portSources?.[port] ?? port}
                  onChange={(e) =>
                    d.onChange({
                      portSources: { ...(d.portSources ?? {}), [port]: e.target.value },
                    })
                  }
                  title={`input ${port}: source variable name`}
                  aria-label={`source for ${port}`}
                />
              )}
            </li>
          ))}
          {ports.length === 0 && (
            <li className="gnode-portrow muted">no inputs</li>
          )}
        </ul>
        <ul className="gnode-port-col gnode-outs">
          <li className="gnode-portrow out">
            <input
              className="gnode-portname gnode-outname nodrag"
              value={d.outName ?? ""}
              placeholder={spec.defaultOut}
              onChange={(e) => d.onChange({ outName: e.target.value })}
              title="output variable name (editable)"
              aria-label="output name"
            />
            <Handle
              type="source"
              position={Position.Right}
              id={`out:${outName}`}
              className="gnode-port gnode-port-out"
            />
          </li>
        </ul>
      </div>

      <div className="gnode-result nodrag">
        {d.computeError ? (
          <span className="gnode-result-err" title={d.computeError}>
            {d.computeError}
          </span>
        ) : d.computed ? (
          <span className="gnode-result-val">
            {outName} = {fmt(d.computed.value)}
            {d.computed.unit ? ` ${d.computed.unit}` : ""}
          </span>
        ) : (
          <span className="muted">— not evaluated —</span>
        )}
      </div>
    </div>
  );
}
