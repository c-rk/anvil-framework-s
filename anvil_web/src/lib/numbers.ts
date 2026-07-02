// Shared numeric helpers.

/** Parse comma / space / newline / semicolon-separated numbers into an array. */
export function parseNumberArray(text: string): number[] {
  if (!text) return [];
  return text
    .split(/[\s,;]+/)
    .map((s) => s.trim())
    .filter((s) => s !== "")
    .map((s) => Number(s))
    .filter((n) => Number.isFinite(n));
}

/** Compact numeric formatter shared across results/charts. */
export function fmtNum(v: number | string | boolean | null): string {
  if (typeof v === "number") {
    const a = Math.abs(v);
    if (v === 0) return "0";
    if (a >= 1e6 || a < 1e-3) return v.toExponential(4);
    return v.toPrecision(6).replace(/\.?0+$/, "");
  }
  return v === null ? "—" : String(v);
}
