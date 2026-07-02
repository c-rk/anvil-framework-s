"""HTTP + WebSocket router for the web System-builder.

Endpoints
---------
POST /api/system/solve     build a user-defined System, solve it, return results
WS   /ws/system/solve       same, but stream per-iteration residuals live

A "system" here is a user-defined collection of quantities (name/value/unit)
plus a list of registry relation names. Anvil AUTO-WIRES the relations by
matching variable names and auto-selects gauss_seidel when the dependency graph
has a cycle, so this module only has to:

    sys = anvil.system(name)
    for q in quantities:  sys.add(q.name, q.value, q.unit)
    for r in relations:   sys.use(r)
    sys.solve(method=..., max_iter=..., rtol=..., on_iter=collector)

and then package the result the same way ``executor.solve`` does (value/unit/role
per variable, sorted input/output name lists, solver method, residual history).

The blocking solve is run off the event loop for the WebSocket path using the
same threading pattern as ``ws_routes`` (asyncio.to_thread + an asyncio.Queue
fed via loop.call_soon_threadsafe) so residual frames stream as they happen.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from . import executor
from .config import record_is_native, settings

router = APIRouter()


# --------------------------------------------------------------------------- #
# Inline request schemas
# --------------------------------------------------------------------------- #

class QuantitySpec(BaseModel):
    name: str
    value: float
    unit: Optional[str] = ""


class RelationSpec(BaseModel):
    """A relation (or prebuilt System) by registry name, with optional renames.

    ``map`` follows anvil's ``System.use(name, map=...)`` semantics:
    {relation_input_name: canvas_quantity_name}.
    """

    name: str
    map: Dict[str, str] = Field(default_factory=dict)


class SystemSolveRequest(BaseModel):
    name: Optional[str] = None
    quantities: List[QuantitySpec] = Field(default_factory=list)
    relations: List[Union[str, RelationSpec]] = Field(default_factory=list)
    method: Optional[str] = None
    max_iter: Optional[int] = None
    rtol: Optional[float] = None

    def relation_specs(self) -> List[RelationSpec]:
        return [
            r if isinstance(r, RelationSpec) else RelationSpec(name=r)
            for r in self.relations
        ]


class BuilderError(Exception):
    """A clean, user-facing builder error -> 400 / error frame (never a 500)."""


# --------------------------------------------------------------------------- #
# Core build + solve (used by POST, WS, and the tests directly)
# --------------------------------------------------------------------------- #

def _coerce_request(req: Any) -> SystemSolveRequest:
    """Accept either a SystemSolveRequest or a plain dict (test ergonomics)."""
    if isinstance(req, SystemSolveRequest):
        return req
    if isinstance(req, dict):
        try:
            return SystemSolveRequest(**req)
        except Exception as exc:  # noqa: BLE001
            raise BuilderError(f"bad request: {exc}")
    raise BuilderError("request must be a dict or SystemSolveRequest")


def _validate_relations(relation_names: List[str]) -> None:
    """Reject unknown relations, and (Tier B) non-native ones, with clean errors.

    Read-only use of the registry / config -- mirrors executor.get_record so the
    builder honors the same NATIVE_ONLY filtering as the rest of the HTTP API.
    """
    for name in relation_names:
        rec = executor.get_record(name)
        if rec is None:
            raise BuilderError(f"Unknown relation '{name}': not found in registry.")
        if rec.get("type") == "Q":
            raise BuilderError(
                f"'{name}' is a stored Quantity, not a relation; add it as an "
                f"input value instead."
            )
        if settings.native_only and not record_is_native(rec):
            raise BuilderError(
                f"Relation '{name}' is not available in native-only mode (Tier B)."
            )


def _build_system(req: SystemSolveRequest):
    """Construct a ready-to-solve anvil.System from the request.

    Adds quantities (honoring optional units like executor._coerce/_apply_unit),
    then wires each relation by name. Anvil auto-wires by variable name and
    auto-selects gauss_seidel for cyclic graphs, so no manual wiring is needed.
    """
    import anvil

    if not req.relations:
        raise BuilderError("at least one relation is required.")

    specs = req.relation_specs()
    _validate_relations([s.name for s in specs])

    sys = anvil.system(req.name or "web_system")

    seen = set()
    for q in req.quantities:
        if q.name in seen:
            raise BuilderError(f"duplicate quantity '{q.name}'.")
        seen.add(q.name)
        unit = (q.unit or "").strip()
        if unit:
            qty = executor._apply_unit(q.value, unit)
            if qty is not None:
                sys._add_single(q.name, qty)
            else:
                # Unit string couldn't be resolved; fall back to value + unit hint.
                sys._add_single(q.name, q.value, unit)
        else:
            sys._add_single(q.name, q.value, unit)

    for spec in specs:
        try:
            # load_object resolves project stores first, then the global
            # registry, so project RSQs wire in exactly like built-ins.
            obj = executor.load_object(spec.name)
            sys.use(obj if obj is not None else spec.name, map=spec.map or None)
        except Exception as exc:  # noqa: BLE001
            raise BuilderError(f"could not use relation '{spec.name}': {exc}")

    return sys


def _solve_kwargs(req: SystemSolveRequest) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}
    if req.method:
        kwargs["method"] = req.method
    if req.max_iter is not None:
        kwargs["max_iter"] = int(req.max_iter)
    if req.rtol is not None:
        kwargs["rtol"] = float(req.rtol)
    return kwargs


def _output_names(sys) -> set:
    """Names produced by some relation (everything else is an input/parameter)."""
    outs: set = set()
    for rel in sys._relations:
        outs.update(getattr(rel, "_outputs", []) or [])
    return outs


def _package_result(sys, result, history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the POST/WS response payload (shared shape with executor.solve)."""
    output_names = _output_names(sys)

    parsed = json.loads(result.to_json())  # {name: {value, unit}}, display units
    results: Dict[str, Any] = {}
    for key, vu in parsed.items():
        role = "output" if key in output_names else "input"
        results[key] = {
            "value": vu.get("value"),
            "unit": vu.get("unit", "") or "",
            "role": role,
        }

    return {
        "name": sys.name,
        "method": getattr(result, "method", "") or "",
        "results": results,
        "history": history,
        "inputs": sorted(k for k in results if results[k]["role"] == "input"),
        "outputs": sorted(k for k in results if results[k]["role"] == "output"),
    }


def build_system(req: Any):
    """Validate the request and construct a ready-to-solve System.

    This is the registry-/SQLite-touching half of a solve and MUST run on the
    thread that owns the registry connection (the event-loop thread for the WS
    path -- SQLite objects are bound to their creating thread). Returns a
    ``(SystemSolveRequest, anvil.System)`` pair for ``solve_built`` to consume.
    Raises BuilderError on unknown / non-native relations and bad input.
    """
    req = _coerce_request(req)
    sys = _build_system(req)
    return req, sys


def solve_built(req: SystemSolveRequest, sys, on_iter=None) -> Dict[str, Any]:
    """Run the (blocking) solve on an already-built System and package the result.

    Pure CPU work -- no registry access -- so it is safe to run off the event
    loop (asyncio.to_thread) for the WS path. ``on_iter`` receives
    ``{"iter", "residual"}`` per iteration. The returned payload's ``history`` is
    populated from the collected iterations (empty for a forward/direct solve).
    """
    history: List[Dict[str, Any]] = []

    def _collect(info: Dict[str, Any]):
        frame = {
            "iter": int(info.get("iter", 0)),
            "residual": float(info.get("residual", 0.0)),
        }
        history.append(frame)
        if on_iter is not None:
            on_iter(frame)

    try:
        result = sys.solve(on_iter=_collect, **_solve_kwargs(req))
    except Exception as exc:  # noqa: BLE001 - surface as a clean builder error
        raise BuilderError(f"solve failed: {exc}")

    return _package_result(sys, result, history)


def solve_system(req: Any, on_iter=None) -> Dict[str, Any]:
    """Build, solve, and package a user-defined system (single-thread convenience).

    Used by the POST path and the tests, where build + solve happen on the same
    thread. The WS path instead calls ``build_system`` (event-loop thread) and
    ``solve_built`` (worker thread) separately so registry/SQLite access stays on
    the connection's owning thread while the blocking solve runs off the loop.

    Raises BuilderError on any user-facing problem (unknown relation, bad units,
    underdetermined/non-converging solve, ...). Callers translate that into a
    400 / error frame -- never a 500 stack trace.
    """
    req, sys = build_system(req)
    return solve_built(req, sys, on_iter=on_iter)


# --------------------------------------------------------------------------- #
# POST endpoint
# --------------------------------------------------------------------------- #

@router.post("/api/system/solve")
async def post_system_solve(req: SystemSolveRequest) -> Dict[str, Any]:
    try:
        return solve_system(req)
    except BuilderError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - last-resort guard, still 400 not 500
        raise HTTPException(status_code=400, detail=f"system solve failed: {exc}")


# --------------------------------------------------------------------------- #
# WebSocket endpoint (live residual streaming)
# --------------------------------------------------------------------------- #

_SENTINEL = object()


def _run_solve_blocking(req: SystemSolveRequest, sys, loop, queue: "asyncio.Queue"):
    """Run the (blocking) solve on a worker thread, streaming frames.

    The System is built on the EVENT-LOOP thread BEFORE this runs (registry /
    SQLite access must stay on the thread that opened the connection -- see the
    async-handler convention in main.py / ws_routes.py). This worker only runs
    the CPU-bound solve + packaging (no further registry access).

    Pushes ("iter", frame) tuples onto ``queue`` via the event loop as the solver
    iterates, then a final ("result", payload) or ("error", msg) tuple, then a
    sentinel. Runs OFF the event-loop thread (asyncio.to_thread).
    """

    def emit(kind: str, payload: Any):
        loop.call_soon_threadsafe(queue.put_nowait, (kind, payload))

    def on_iter(frame: Dict[str, Any]):
        emit("iter", {
            "type": "iter",
            "iter": int(frame["iter"]),
            "residual": float(frame["residual"]),
        })

    try:
        payload = solve_built(req, sys, on_iter=on_iter)
        payload = {"type": "result", **payload}
        emit("result", payload)
    except BuilderError as exc:
        emit("error", {"type": "error", "message": str(exc)})
    except Exception as exc:  # noqa: BLE001
        emit("error", {"type": "error", "message": f"{exc}"})
    finally:
        loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)


@router.websocket("/ws/system/solve")
async def ws_system_solve(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
    except WebSocketDisconnect:
        return

    try:
        parsed = SystemSolveRequest(**json.loads(raw))
    except Exception as exc:  # noqa: BLE001
        await websocket.send_json({"type": "error", "message": f"bad request: {exc}"})
        await websocket.close()
        return

    # Build the System (registry / SQLite access) on the EVENT-LOOP thread; the
    # worker thread below only runs the blocking solve.
    try:
        req, sys = build_system(parsed)
    except BuilderError as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close()
        return
    except Exception as exc:  # noqa: BLE001
        await websocket.send_json({"type": "error", "message": f"{exc}"})
        await websocket.close()
        return

    loop = asyncio.get_running_loop()
    queue: "asyncio.Queue" = asyncio.Queue()

    solve_task = asyncio.create_task(
        asyncio.to_thread(_run_solve_blocking, req, sys, loop, queue)
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
