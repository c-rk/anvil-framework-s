import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface CsvColumn {
  name: string;
  values: number[];
}

export interface CsvNodeFields {
  /** Editable node label. */
  name: string;
  text: string;
  columns: CsvColumn[];
  rows: number;
  parsing: boolean;
  error: string | null;
  onChangeText: (text: string) => void;
  onParse: () => void;
  onRemove: () => void;
}

/**
 * CSV data node (A5): paste CSV text, parse on the backend, and expose each
 * numeric COLUMN as a named output handle (`out:<col>`) that the auto-wiring
 * can feed into a relation/sweep as a quantity / time-series.
 */
export function CsvNode({ data }: NodeProps) {
  const d = data as unknown as CsvNodeFields;
  return (
    <div className="gnode gnode-csv">
      <div className="gnode-head">
        <span className="gnode-kind">csv</span>
        <span className="gnode-title">{d.name}</span>
        <button
          className="gnode-x"
          onClick={d.onRemove}
          title="Remove node"
          aria-label="Remove node"
        >
          ×
        </button>
      </div>

      <textarea
        className="gnode-csv-text nodrag"
        rows={3}
        placeholder="paste CSV (header + numeric columns)…"
        value={d.text}
        onChange={(e) => d.onChangeText(e.target.value)}
        aria-label="CSV text"
      />
      <div className="gnode-csv-row">
        <button
          className="run-btn gnode-csv-parse nodrag"
          onClick={d.onParse}
          disabled={d.parsing || !d.text.trim()}
        >
          {d.parsing ? "Parsing…" : "Parse"}
        </button>
        {d.columns.length > 0 && (
          <span className="muted gnode-csv-meta">
            {d.columns.length} cols · {d.rows} rows
          </span>
        )}
      </div>
      {d.error && <div className="gnode-msg err">{d.error}</div>}

      <ul className="gnode-port-col gnode-outs gnode-csv-outs">
        {d.columns.map((c) => (
          <li key={c.name} className="gnode-portrow out">
            <span className="gnode-portlabel" title={`${c.values.length} numeric values`}>
              {c.name}
            </span>
            <Handle
              type="source"
              position={Position.Right}
              id={`out:${c.name}`}
              className="gnode-port gnode-port-out"
            />
          </li>
        ))}
        {d.columns.length === 0 && (
          <li className="gnode-portrow muted">parse to expose columns</li>
        )}
      </ul>
    </div>
  );
}
