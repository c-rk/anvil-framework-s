// Crash-recovery autosave of the working canvas.
//
// Named saves now live on the SERVER (PUT/GET/DELETE /api/canvases). The only
// thing kept in localStorage is a single silent autosave slot so a refresh or
// crash doesn't lose the canvas the user was editing.

import type { CanvasGraph } from "./canvasGraph";

const AUTOSAVE_KEY = "anvil-canvas-autosave";

export interface AutosavePayload {
  version: 2;
  savedAt: string;
  /** Server canvas name the user was working on (null when unsaved). */
  canvasName: string | null;
  /** Signature of the last server-saved state (drives the dirty flag). */
  savedSig: string;
  graph: CanvasGraph;
}

export function writeAutosave(
  canvasName: string | null,
  savedSig: string,
  graph: CanvasGraph,
): void {
  const payload: AutosavePayload = {
    version: 2,
    savedAt: new Date().toISOString(),
    canvasName,
    savedSig,
    graph,
  };
  try {
    localStorage.setItem(AUTOSAVE_KEY, JSON.stringify(payload));
  } catch {
    /* quota / private mode — autosave is best-effort */
  }
}

export function readAutosave(): AutosavePayload | null {
  try {
    const raw = localStorage.getItem(AUTOSAVE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AutosavePayload> | null;
    if (!parsed || typeof parsed !== "object" || !parsed.graph) return null;
    return {
      version: 2,
      savedAt: typeof parsed.savedAt === "string" ? parsed.savedAt : "",
      canvasName: typeof parsed.canvasName === "string" ? parsed.canvasName : null,
      savedSig: typeof parsed.savedSig === "string" ? parsed.savedSig : "",
      graph: parsed.graph as CanvasGraph,
    };
  } catch {
    return null;
  }
}

export function clearAutosave(): void {
  try {
    localStorage.removeItem(AUTOSAVE_KEY);
  } catch {
    /* ignore */
  }
}
