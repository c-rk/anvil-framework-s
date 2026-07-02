import type { SolveResponse } from "./types";

function triggerDownload(filename: string, content: string, mime: string) {
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
