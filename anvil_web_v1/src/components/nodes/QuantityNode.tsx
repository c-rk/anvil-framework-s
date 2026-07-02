import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface QuantityNodeFields {
  name: string;
  value: string;
  unit: string;
  onChange: (patch: Partial<Omit<QuantityNodeFields, "onChange" | "onRemove">>) => void;
  onRemove: () => void;
}

/**
 * Editable quantity (free input) node: name + numeric value + unit.
 * Emits a single output handle ("value") that the auto-wiring matches by name.
 */
export function QuantityNode({ data }: NodeProps) {
  const d = data as unknown as QuantityNodeFields;
  return (
    <div className="gnode gnode-quantity">
      <div className="gnode-head">
        <span className="gnode-kind">quantity</span>
        <button
          className="gnode-x"
          onClick={d.onRemove}
          title="Remove node"
          aria-label="Remove node"
        >
          ×
        </button>
      </div>
      <input
        className="gnode-name nodrag"
        value={d.name}
        placeholder="name"
        onChange={(e) => d.onChange({ name: e.target.value })}
        aria-label="Quantity name"
      />
      <div className="gnode-valrow">
        <input
          className="gnode-val nodrag"
          type="number"
          step="any"
          value={d.value}
          placeholder="value"
          onChange={(e) => d.onChange({ value: e.target.value })}
          aria-label="Quantity value"
        />
        <input
          className="gnode-unit nodrag"
          value={d.unit}
          placeholder="unit"
          onChange={(e) => d.onChange({ unit: e.target.value })}
          aria-label="Quantity unit"
        />
      </div>
      <Handle
        type="source"
        position={Position.Right}
        id="value"
        className="gnode-port gnode-port-out"
      />
    </div>
  );
}
