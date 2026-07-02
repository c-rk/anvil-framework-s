"""WebSocket router for LIVE solver-residual streaming.

Endpoint
--------
WS  /ws/solve

Protocol
--------
Client -> Server (one JSON message):
    {"name": <rsq name>, "inputs": {<name>: <scalar | {value, unit}>}, "method"?: <str>}

Server -> Client (a stream of JSON frames):
    {"type": "iter",   "iter": <int>, "residual": <float>}        # one per solver iteration
    {"type": "result", "name", "method", "results", "inputs", "outputs"}  # final, same shape as executor.solve
    {"type": "error",  "message": <str>}                           # on failure

The socket is closed by the server after the result/error frame.

Because the Anvil solver is blocking (and runs CPU-bound numpy code), it is run
off the event loop via ``asyncio.to_thread``. The per-iteration ``on_iter``
callback (which fires on the solver thread) pushes frames onto an
``asyncio.Queue`` using ``loop.call_soon_threadsafe`` so they are marshalled
back to the event-loop thread and streamed to the socket as they happen.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from . import executor

router = APIRouter()


# --------------------------------------------------------------------------- #
# Inline request schema
# --------------------------------------------------------------------------- #

class WsSolveRequest(BaseModel):
    """The single JSON message the client sends to open a live solve."""

    name: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    method: Optional[str] = None
    si: bool = False


# --------------------------------------------------------------------------- #
# Blocking solve with a live iteration callback
# --------------------------------------------------------------------------- #

_SENTINEL = object()


def _build_system(name: str, inputs: Dict[str, Any]):
    """Build a configured, ready-to-solve System for either an "S" or "R" RSQ.

    Mirrors anvil_server.app.executor.sweep's construction so the solve and its
    result shape stay consistent with the rest of the HTTP API.
    """
    import anvil

    rec = executor.get_record(name)
    if rec is None:
        raise KeyError(name)

    coerced = {k: executor._coerce_input(v) for k, v in inputs.items()}

    if rec["type"] == "S":
        sys = getattr(anvil.S, name).copy()
        if coerced:
            sys.set(**coerced)
        return sys

    # Relation: wrap as a one-relation System so a coupled relation can iterate.
    report = anvil.check(name, verbose=False)
    defaults = report.get("defaults", {}) or {}
    sys = anvil.system(f"_ws_{name}")
    for inp in report.get("inputs", []) or []:
        if inp in coerced:
            sys._add_single(inp, coerced[inp])
        elif inp in defaults:
            sys._add_single(inp, defaults[inp])
    sys.use(name)
    return sys


def _result_payload(name: str, result, si: bool, input_names) -> Dict[str, Any]:
    """Package a solved Result into the same dict shape as executor.solve."""
    parsed = json.loads(result.to_json(si=si))
    results: Dict[str, Any] = {}
    for key, vu in parsed.items():
        results[key] = {
            "value": vu.get("value"),
            "unit": vu.get("unit", "") or "",
            "role": "input" if key in input_names else "output",
        }

    return {
        "type": "result",
        "name": name,
        "method": getattr(result, "method", "") or "",
        "results": results,
        "inputs": sorted(k for k in results if results[k]["role"] == "input"),
        "outputs": sorted(k for k in results if results[k]["role"] == "output"),
    }


def _run_solve_blocking(req: WsSolveRequest, sys, input_names, loop,
                        queue: "asyncio.Queue"):
    """Run the (blocking) solve on a worker thread.

    The System is built on the event-loop thread BEFORE this runs (registry /
    SQLite access must stay on the thread that opened the connection — see the
    async-handler convention in main.py / executor.py). This worker only runs
    the CPU-bound solve and packages the result (no further registry access).

    Pushes ("iter", frame) tuples onto ``queue`` via the event loop as the
    solver iterates, then a final ("result", payload) or ("error", msg) tuple
    and a sentinel. Runs OFF the event-loop thread (asyncio.to_thread).
    """

    def emit(kind: str, payload: Any):
        loop.call_soon_threadsafe(queue.put_nowait, (kind, payload))

    def on_iter(info: Dict[str, Any]):
        emit("iter", {
            "type": "iter",
            "iter": int(info.get("iter", 0)),
            "residual": float(info.get("residual", 0.0)),
        })

    try:
        solve_kwargs: Dict[str, Any] = {"on_iter": on_iter}
        if req.method:
            solve_kwargs["method"] = req.method
        result = sys.solve(**solve_kwargs)
        emit("result", _result_payload(req.name, result, req.si, input_names))
    except Exception as exc:  # noqa: BLE001 - surface any solver error
        emit("error", {"type": "error", "message": f"{exc}"})
    finally:
        loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)


# --------------------------------------------------------------------------- #
# WebSocket endpoint
# --------------------------------------------------------------------------- #

@router.websocket("/ws/solve")
async def ws_solve(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
    except WebSocketDisconnect:
        return

    try:
        req = WsSolveRequest(**json.loads(raw))
    except Exception as exc:  # noqa: BLE001
        await websocket.send_json({"type": "error", "message": f"bad request: {exc}"})
        await websocket.close()
        return

    # Build the System and read the registry on the EVENT-LOOP thread: registry
    # access touches SQLite, which (per the executor/main async convention) must
    # stay on the thread that opened it. The worker thread only runs the solve.
    try:
        import anvil

        sys = _build_system(req.name, req.inputs)
        report = anvil.check(req.name, verbose=False)
        input_names = set(report.get("inputs", []) or [])
    except KeyError:
        await websocket.send_json(
            {"type": "error", "message": f"RSQ '{req.name}' not found"}
        )
        await websocket.close()
        return
    except Exception as exc:  # noqa: BLE001
        await websocket.send_json({"type": "error", "message": f"{exc}"})
        await websocket.close()
        return

    loop = asyncio.get_running_loop()
    queue: "asyncio.Queue" = asyncio.Queue()

    # Run the blocking solve concurrently; drain its frames as they arrive.
    solve_task = asyncio.create_task(
        asyncio.to_thread(_run_solve_blocking, req, sys, input_names, loop, queue)
    )

    try:
        while True:
            item = await queue.get()
            if item is _SENTINEL:
                break
            _kind, payload = item
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        await solve_task
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001 - already closed
            pass
