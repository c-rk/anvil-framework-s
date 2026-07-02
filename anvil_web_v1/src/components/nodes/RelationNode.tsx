import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { RsqDetail } from "../../lib/types";
import { MathView } from "../MathView";

export interface RelationNodeFields {
  rsqName: string;
  detail: RsqDetail | null;
  loading: boolean;
  error: string | null;
  /** original port name -> rename (effective match name). */
  portNames: Record<string, string>;
  onRenamePort: (original: string, value: string) => void;
  onRemove: () => void;
}

/**
 * Relation (RSQ) node: shows the RSQ name, its KaTeX formula (if any), and
 * labelled input ports (left) + output ports (right). Each input port name is
 * editable so the user can override name-matching.
 */
export function RelationNode({ data }: NodeProps) {
  const d = data as unknown as RelationNodeFields;
  const detail = d.detail;
  const inputs = detail?.inputs ?? [];
  const outputs = detail?.outputs ?? [];

  return (
    <div className="gnode gnode-relation">
      <div className="gnode-head">
        <span className="gnode-kind">relation</span>
        <span className="gnode-title">{d.rsqName}</span>
        <button
          className="gnode-x"
          onClick={d.onRemove}
          title="Remove node"
          aria-label="Remove node"
        >
          ×
        </button>
      </div>

      {d.loading && <div className="gnode-msg">loading…</div>}
      {d.error && <div className="gnode-msg err">{d.error}</div>}

      {detail && (
        <>
          {detail.latex && (
            <div className="gnode-formula nodrag">
              <MathView latex={detail.latex} fallback={detail.signature} />
            </div>
          )}

          <div className="gnode-ports">
            <ul className="gnode-port-col gnode-ins">
              {inputs.map((inp) => (
                <li key={inp.name} className="gnode-portrow">
                  <Handle
                    type="target"
                    position={Position.Left}
                    id={`in:${inp.name}`}
                    className="gnode-port gnode-port-in"
                  />
                  <input
                    className="gnode-portname nodrag"
                    value={d.portNames[inp.name] ?? inp.name}
                    onChange={(e) => d.onRenamePort(inp.name, e.target.value)}
                    title={`input: ${inp.name}${inp.unit ? ` (${inp.unit})` : ""}`}
                    aria-label={`Rename input ${inp.name}`}
                  />
                </li>
              ))}
              {inputs.length === 0 && (
                <li className="gnode-portrow muted">no inputs</li>
              )}
            </ul>
            <ul className="gnode-port-col gnode-outs">
              {outputs.map((out) => (
                <li key={out.name} className="gnode-portrow out">
                  <span className="gnode-portlabel" title={out.unit || out.name}>
                    {out.name}
                  </span>
                  <Handle
                    type="source"
                    position={Position.Right}
                    id={`out:${out.name}`}
                    className="gnode-port gnode-port-out"
                  />
                </li>
              ))}
              {outputs.length === 0 && (
                <li className="gnode-portrow muted">no outputs</li>
              )}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
