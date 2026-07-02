import type {
  CanvasGetResponse,
  CanvasListResponse,
  CanvasParseResponse,
  CanvasPutResponse,
  CsvResponse,
  ExampleCanvas,
  ExampleListResponse,
  ExampleScriptListResponse,
  ExampleScriptResponse,
  HealthResponse,
  RegistryResponse,
  RsqDetail,
  SolveInputValue,
  SolveResponse,
  SweepRequest,
  SweepResponse,
  SystemSolveRequest,
  SystemSolveResponse,
  SystemWsFrame,
  VizResponse,
  VizSweepRequest,
  WsFrame,
} from "./types";

// API base URL. Overridable via VITE_API_BASE (see .env.example).
// Default: same origin when the SPA is served by the backend itself
// (python -m anvil_server.run); the Vite dev server (port 5173) still
// targets the conventional local backend port.
function defaultApiBase(): string {
  if (typeof window !== "undefined" && window.location.origin.startsWith("http")) {
    const devPorts = new Set(["5173", "5174"]);
    if (!devPorts.has(window.location.port)) return window.location.origin;
  }
  return "http://127.0.0.1:8000";
}

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ??
  defaultApiBase();

// WebSocket base, derived from API_BASE (http -> ws, https -> wss).
export const WS_BASE: string = API_BASE.replace(/^http/, "ws");

/**
 * Open a live-solve WebSocket and stream residual frames.
 *
 * Sends {name, inputs, method?} once connected, then invokes `onFrame` for each
 * JSON frame ("iter" / "result" / "error"). Returns a handle with `close()`.
 * The socket auto-closes after a "result" or "error" frame.
 */
export function solveLive(
  body: { name: string; inputs: Record<string, SolveInputValue>; method?: string },
  onFrame: (frame: WsFrame) => void,
  onClose?: (err?: string) => void,
): { close: () => void } {
  const ws = new WebSocket(`${WS_BASE}/ws/solve`);
  let closedErr: string | undefined;

  ws.onopen = () => ws.send(JSON.stringify(body));
  ws.onmessage = (ev) => {
    try {
      const frame = JSON.parse(ev.data) as WsFrame;
      if (frame.type === "error") closedErr = frame.message;
      onFrame(frame);
    } catch {
      /* ignore malformed frame */
    }
  };
  ws.onerror = () => {
    closedErr = closedErr ?? "WebSocket connection error";
  };
  ws.onclose = () => onClose?.(closedErr);

  return {
    close: () => {
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    },
  };
}

/**
 * Open a live system-solve WebSocket and stream residual frames.
 *
 * Mirrors {@link solveLive} but targets `/ws/system/solve` and sends the full
 * {@link SystemSolveRequest} (quantities + relation names). Invokes `onFrame`
 * for each JSON frame ("iter" / "result" / "error"). The socket auto-closes
 * after a terminal frame.
 */
export function solveSystemLive(
  body: SystemSolveRequest,
  onFrame: (frame: SystemWsFrame) => void,
  onClose?: (err?: string) => void,
): { close: () => void } {
  const ws = new WebSocket(`${WS_BASE}/ws/system/solve`);
  let closedErr: string | undefined;

  ws.onopen = () => ws.send(JSON.stringify(body));
  ws.onmessage = (ev) => {
    try {
      const frame = JSON.parse(ev.data) as SystemWsFrame;
      if (frame.type === "error") closedErr = frame.message;
      onFrame(frame);
    } catch {
      /* ignore malformed frame */
    }
  };
  ws.onerror = () => {
    closedErr = closedErr ?? "WebSocket connection error";
  };
  ws.onclose = () => onClose?.(closedErr);

  return {
    close: () => {
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    },
  };
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const detail = await safeDetail(res);
    throw new Error(detail || `GET ${path} failed (${res.status})`);
  }
  return (await res.json()) as T;
}

/** Error carrying the HTTP status so callers can branch (e.g. 501 viz fallback). */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await safeDetail(res);
    throw new ApiError(detail || `POST ${path} failed (${res.status})`, res.status);
  }
  return (await res.json()) as T;
}

async function putJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await safeDetail(res);
    throw new ApiError(detail || `PUT ${path} failed (${res.status})`, res.status);
  }
  return (await res.json()) as T;
}

async function deleteJSON(path: string): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
  if (!res.ok) {
    const detail = await safeDetail(res);
    throw new ApiError(detail || `DELETE ${path} failed (${res.status})`, res.status);
  }
}

async function safeDetail(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (data && typeof data.detail === "string") return data.detail;
  } catch {
    /* ignore */
  }
  return "";
}

export const api = {
  health: () => getJSON<HealthResponse>("/healthz"),
  registry: (calcOnly = false) =>
    getJSON<RegistryResponse>(`/api/registry${calcOnly ? "?calc=1" : ""}`),
  rsq: (name: string) => getJSON<RsqDetail>(`/api/rsq/${encodeURIComponent(name)}`),
  solve: (name: string, inputs: Record<string, SolveInputValue>, si = false) =>
    postJSON<SolveResponse>("/api/solve", { name, inputs, si }),
  sweep: (req: SweepRequest) =>
    postJSON<SweepResponse>("/api/sweep", { si: true, ...req }),
  solveSystem: (req: SystemSolveRequest) =>
    postJSON<SystemSolveResponse>("/api/system/solve", req),
  csv: (text: string, maxRows?: number) =>
    postJSON<CsvResponse>("/api/data/csv", { text, max_rows: maxRows }),
  examples: () => getJSON<ExampleListResponse>("/api/examples"),
  example: (id: string) =>
    getJSON<ExampleCanvas>(`/api/examples/${encodeURIComponent(id)}`),
  vizSweep: (req: VizSweepRequest) =>
    postJSON<VizResponse>("/api/viz/sweep", { si: true, ...req }),

  // ---- server-side canvases (python-script persistence) -------------------
  canvases: () => getJSON<CanvasListResponse>("/api/canvases"),
  canvas: (name: string) =>
    getJSON<CanvasGetResponse>(`/api/canvases/${encodeURIComponent(name)}`),
  saveCanvas: (name: string, canvas: unknown) =>
    putJSON<CanvasPutResponse>(`/api/canvases/${encodeURIComponent(name)}`, { canvas }),
  deleteCanvas: (name: string) =>
    deleteJSON(`/api/canvases/${encodeURIComponent(name)}`),
  parseCanvasScript: (script: string) =>
    postJSON<CanvasParseResponse>("/api/canvases/parse", { script }),
  exampleScripts: () => getJSON<ExampleScriptListResponse>("/api/example-scripts"),
  exampleScript: (id: string) =>
    getJSON<ExampleScriptResponse>(`/api/example-scripts/${encodeURIComponent(id)}`),
};
