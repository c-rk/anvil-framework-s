import type { SolveResponse, SweepResponse } from "./types";

export function triggerDownload(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function exportResultJSON(result: SolveResponse) {
  triggerDownload(
    `${result.name}_result.json`,
    JSON.stringify(result, null, 2),
    "application/json"
  );
}

export function exportResultCSV(result: SolveResponse) {
  const lines = ["variable,value,unit,role"];
  for (const [key, rv] of Object.entries(result.results)) {
    const v = rv.value === null ? "" : String(rv.value);
    lines.push(`${key},${v},${rv.unit},${rv.role}`);
  }
  triggerDownload(`${result.name}_result.csv`, lines.join("\n"), "text/csv");
}

/** Export a sweep response as a wide CSV (param column + one per output). */
export function exportSweepCSV(res: SweepResponse) {
  const cols = Object.keys(res.data);
  if (cols.length === 0) {
    triggerDownload(`${res.name}_sweep.csv`, "", "text/csv");
    return;
  }
  const n = Math.max(...cols.map((c) => res.data[c].length));
  const lines = [cols.join(",")];
  for (let i = 0; i < n; i++) {
    lines.push(
      cols
        .map((c) => {
          const v = res.data[c][i];
          return v === null || v === undefined ? "" : String(v);
        })
        .join(","),
    );
  }
  triggerDownload(`${res.name}_sweep.csv`, lines.join("\n"), "text/csv");
}

export function exportSweepJSON(res: SweepResponse) {
  triggerDownload(
    `${res.name}_sweep.json`,
    JSON.stringify(res, null, 2),
    "application/json",
  );
}

/** Export an arbitrary column table {col: values[]} to CSV. */
export function exportColumnsCSV(
  filename: string,
  columns: Record<string, (number | string | null)[]>,
) {
  const cols = Object.keys(columns);
  if (cols.length === 0) {
    triggerDownload(filename, "", "text/csv");
    return;
  }
  const n = Math.max(...cols.map((c) => columns[c].length));
  const lines = [cols.join(",")];
  for (let i = 0; i < n; i++) {
    lines.push(
      cols
        .map((c) => {
          const v = columns[c][i];
          return v === null || v === undefined ? "" : String(v);
        })
        .join(","),
    );
  }
  triggerDownload(filename, lines.join("\n"), "text/csv");
}
