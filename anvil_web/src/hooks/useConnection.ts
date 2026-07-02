import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { HealthResponse } from "../lib/types";

export type ConnStatus = "connecting" | "connected" | "disconnected";

interface Connection {
  status: ConnStatus;
  health: HealthResponse | null;
  /** Force an immediate re-check (e.g. after a WS close is observed). */
  recheck: () => void;
}

/**
 * Polls GET /healthz and exposes a coarse connection status.
 *
 * - Starts in "connecting", flips to "connected" on the first successful poll
 *   and "disconnected" when a poll fails (fetch error or non-2xx).
 * - Polls slowly while connected, faster while down so it recovers promptly.
 * - All fetch errors are swallowed here so an unreachable backend never throws.
 */
export function useConnection(): Connection {
  const [status, setStatus] = useState<ConnStatus>("connecting");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const timer = useRef<number | null>(null);
  const mounted = useRef(true);

  const check = useCallback(async () => {
    try {
      const h = await api.health();
      if (!mounted.current) return true;
      setHealth(h);
      setStatus("connected");
      return true;
    } catch {
      if (!mounted.current) return false;
      setStatus("disconnected");
      return false;
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    let stopped = false;

    const loop = async () => {
      const ok = await check();
      if (stopped || !mounted.current) return;
      // Poll every 15s while healthy, every 3s while trying to recover.
      const delay = ok ? 15000 : 3000;
      timer.current = window.setTimeout(loop, delay);
    };
    loop();

    return () => {
      stopped = true;
      mounted.current = false;
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [check]);

  const recheck = useCallback(() => {
    if (timer.current) window.clearTimeout(timer.current);
    void check().then((ok) => {
      const delay = ok ? 15000 : 3000;
      timer.current = window.setTimeout(function loop() {
        void check().then((o) => {
          timer.current = window.setTimeout(loop, o ? 15000 : 3000);
        });
      }, delay);
    });
  }, [check]);

  return { status, health, recheck };
}
