"""In-process execution layer (Tier A) wrapping the public Anvil API.

This module is the single place that talks to ``anvil``. Keeping it isolated
makes it straightforward to later swap in a different execution backend
(e.g. a subprocess / sandbox tier) without touching the HTTP layer.
"""

from __future__ import annotations

import inspect as _pyinspect
import json
from typing import Any, Dict, List, Optional

import numpy as np

import anvil
from anvil import registry

from .config import (
    has_array_input,
    is_adapter,
    is_calculator_ok,
    record_is_native,
    settings,
)

# Arrays longer than this are downsampled when serialized into a JSON response,
# so a 100k-sample FFT spectrum doesn't blow up the payload.
MAX_ARRAY_LEN = 2048


# --------------------------------------------------------------------------- #
# Project registries (ANVIL_PROJECT / --project)
# --------------------------------------------------------------------------- #

_project_stores: Optional[List[Any]] = None


def project_stores() -> List[Any]:
    """Open (once) every project store under settings.project_path.

    Accepts a project directory (containing .anvil/project_*.db), a .anvil
    directory, or a direct .db path. SQLite connections are thread-bound, so
    this must only ever be called from the event-loop thread (the same
    convention as the global registry).
    """
    global _project_stores
    if _project_stores is not None:
        return _project_stores
    _project_stores = []
    if not settings.project_path:
        return _project_stores
    from pathlib import Path

    from anvil.registry.store import Store

    p = Path(settings.project_path)
    candidates: List[Path] = []
    if p.is_file() and p.suffix == ".db":
        candidates = [p]
    else:
        anvil_dir = p if p.name == ".anvil" else p / ".anvil"
        if anvil_dir.is_dir():
            candidates = sorted(anvil_dir.glob("project_*.db"))
    for db in candidates:
        try:
            _project_stores.append(Store(db))
        except Exception:  # noqa: BLE001 - unreadable db: skip, don't crash
            continue
    return _project_stores


def _project_record(name: str):
    """(record, store) for a project RSQ, or (None, None)."""
    for store in project_stores():
        rec = store.get(name)
        if rec is not None:
            return rec, store
    return None, None


def load_object(name: str):
    """Load the live RSQ object for a name, project stores first, then global.

    Returns the loaded Relation/System/Quantity, or None when unknown.
    """
    from anvil.registry.loader import load_rsq

    rec, store = _project_record(name)
    if rec is not None:
        return load_rsq(rec, store)
    rec = get_record(name)
    if rec is None:
        return None
    return load_rsq(rec, registry._get_store())


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

def list_registry(calc_only: bool = False) -> List[Dict[str, Any]]:
    """Return registry entries, filtered for Tier B when NATIVE_ONLY is set.

    Each entry carries ``calculator_ok`` (a plain Relation the web calculator can
    drive) and ``array_input`` (takes a 1-D array / time-series input). When
    ``calc_only`` is True, only ``calculator_ok`` entries are returned.
    """
    store = registry._get_store()

    # Project records come first and shadow same-named globals (matching the
    # Project read semantics: project store first, global fallback).
    project_names: set = set()
    records: List[tuple] = []
    for ps in project_stores():
        for r in ps.get_all():
            if r["name"] not in project_names:
                project_names.add(r["name"])
                records.append((r, True))
    for r in store.get_all():
        if r["name"] not in project_names:
            records.append((r, False))

    out = []
    for r, is_project in records:
        if settings.native_only and not record_is_native(r):
            continue
        calc_ok = is_calculator_ok(r)
        if calc_only and not calc_ok:
            continue
        out.append(
            {
                "name": r["name"],
                "type": r["type"],
                "domain": r.get("domain", "") or "",
                "description": r.get("description", "") or "",
                "tags": r.get("tags", []) or [],
                "calculator_ok": calc_ok,
                "array_input": has_array_input(r),
                "adapter": is_adapter(r),
                "project": is_project,
            }
        )
    return out


def refresh_registry() -> Dict[str, Any]:
    """Re-seed (if needed) and rebuild the live namespaces from the store.

    Makes RSQs added to the DB after server start immediately solvable in-process
    (anvil.R / anvil.S etc. are repopulated). Returns a small status dict.
    """
    try:
        from anvil.seed import seed as _seed
        _seed()
    except Exception:
        pass
    registry._rebuild_namespaces()
    return {"status": "ok", "rsq_count": rsq_count()}


def get_record(name: str) -> Optional[Dict[str, Any]]:
    rec, _ = _project_record(name)
    if rec is None:
        rec = registry._get_store().get(name)
    if rec is None:
        return None
    if settings.native_only and not record_is_native(rec):
        return None
    return rec


# --------------------------------------------------------------------------- #
# RSQ detail
# --------------------------------------------------------------------------- #

def _build_signature(name: str, inputs: List[str], defaults: Dict[str, Any]) -> str:
    parts = []
    for inp in inputs:
        if inp in defaults:
            parts.append(f"{inp}={defaults[inp]}")
        else:
            parts.append(inp)
    return f"{name}({', '.join(parts)})"


def _report_from_record(rec: Dict[str, Any], store) -> Dict[str, Any]:
    """anvil.check-shaped report for a PROJECT record (check is global-only)."""
    from anvil.registry.loader import load_rsq
    from anvil.relation import Relation
    from anvil.system import System

    obj = load_rsq(rec, store)
    inputs: List[str] = []
    outputs: List[str] = []
    defaults: Dict[str, Any] = {}
    if isinstance(obj, System):
        rel = obj.as_relation()
        inputs = list(getattr(rel, "_inputs", []) or [])
        outputs = sorted(getattr(rel, "_outputs", []) or [])
    elif isinstance(obj, Relation) or callable(obj):
        fn = obj.func if isinstance(obj, Relation) else obj
        try:
            sig = _pyinspect.signature(fn)
            inputs = list(sig.parameters)
            defaults = {
                k: p.default
                for k, p in sig.parameters.items()
                if p.default is not _pyinspect.Parameter.empty
            }
        except (TypeError, ValueError):
            pass
        outputs = sorted(getattr(obj, "_outputs", []) or [])
    return {
        "name": rec["name"],
        "type": rec["type"],
        "domain": rec.get("domain", "") or "",
        "description": rec.get("description", "") or "",
        "version": rec.get("version", "") or "",
        "inputs": inputs,
        "outputs": outputs,
        "defaults": defaults,
    }


def describe(name: str) -> Optional[Dict[str, Any]]:
    """Build an RSQ detail dict from anvil.check + the registry record."""
    rec = get_record(name)
    if rec is None:
        return None

    proj_rec, proj_store = _project_record(name)
    if proj_rec is not None:
        try:
            report = _report_from_record(proj_rec, proj_store)
        except Exception:  # noqa: BLE001 - broken project RSQ source
            return None
    else:
        report = anvil.check(name, verbose=False)
    if not report.get("name"):
        return None

    meta = rec.get("metadata") or {}
    meta_inputs = meta.get("inputs", {}) or {}
    meta_outputs = meta.get("outputs", {}) or {}

    inputs: List[str] = report.get("inputs", []) or []
    outputs: List[str] = report.get("outputs", []) or []
    defaults: Dict[str, Any] = report.get("defaults", {}) or {}

    input_objs = []
    for inp in inputs:
        mi = meta_inputs.get(inp, {}) if isinstance(meta_inputs, dict) else {}
        default = defaults.get(inp, mi.get("default"))
        input_objs.append(
            {
                "name": inp,
                "default": _jsonable(default),
                "unit": mi.get("unit", "") or "",
                "desc": mi.get("desc", "") or "",
            }
        )

    output_objs = []
    for outp in outputs:
        mo = meta_outputs.get(outp, {}) if isinstance(meta_outputs, dict) else {}
        output_objs.append(
            {
                "name": outp,
                "unit": mo.get("unit", "") or "",
                "desc": mo.get("desc", "") or "",
            }
        )

    # LaTeX: only if the RSQ metadata explicitly provides one. Otherwise the
    # frontend falls back to the Python signature.
    latex = meta.get("latex") or None

    return {
        "name": report["name"],
        "type": report.get("type", rec["type"]),
        "domain": report.get("domain", "") or rec.get("domain", "") or "",
        "description": report.get("description", "") or rec.get("description", "") or "",
        "version": report.get("version", "") or rec.get("version", "") or "",
        "signature": _build_signature(report["name"], inputs, defaults),
        "latex": latex,
        "inputs": input_objs,
        "outputs": output_objs,
        "defaults": {k: _jsonable(v) for k, v in defaults.items()},
        "tags": rec.get("tags", []) or [],
        "calculator_ok": is_calculator_ok(rec),
        "array_input": has_array_input(rec),
        "adapter": is_adapter(rec),
    }


# --------------------------------------------------------------------------- #
# Solve
# --------------------------------------------------------------------------- #

def _coerce_input(raw: Any):
    """Turn a request input value into something anvil.solve accepts.

    Accepts:
      * a bare scalar (number / string / bool),
      * a list/array -> numpy float array (time-series / signal),
      * {"value": x, "unit": "Pa"} -> x * unit-stub (scalar), and
      * {"value": [...], "unit": "s"} -> numpy array (unit currently dropped for
        arrays since Anvil array RSQs operate on raw arrays).
    Falls back to the bare value if a scalar unit can't be resolved.
    """
    if isinstance(raw, dict):
        value = raw.get("value")
        if _is_arraylike(value):
            return _to_array(value)
        unit = (raw.get("unit") or "").strip()
        if unit:
            q = _apply_unit(value, unit)
            if q is not None:
                return q
        return value
    if _is_arraylike(raw):
        return _to_array(raw)
    return raw


def _is_arraylike(v: Any) -> bool:
    return isinstance(v, (list, tuple)) or isinstance(v, np.ndarray)


def _to_array(v: Any) -> np.ndarray:
    """Coerce a list/tuple to a float numpy array; fall back to object array."""
    try:
        return np.asarray(v, dtype=float)
    except (TypeError, ValueError):
        return np.asarray(v)


def _apply_unit(value: Any, unit: str):
    """Best-effort build of an Anvil Quantity from a value and unit string."""
    try:
        return anvil.Quantity(float(value), unit)
    except Exception:
        return None


def solve(name: str, inputs: Dict[str, Any], si: bool = False) -> Dict[str, Any]:
    rec = get_record(name)
    if rec is None:
        raise KeyError(name)

    # Tier B: route untrusted RSQ execution through the subprocess-isolated,
    # restricted-namespace sandbox with a wall-clock timeout. Tier A keeps the
    # fast in-process path below unchanged.
    if settings.native_only and settings.sandbox_enabled:
        from .sandbox import run_sandboxed_solve
        return run_sandboxed_solve(
            name, inputs, timeout_s=settings.sandbox_timeout_s, si=si
        )

    kwargs = {k: _coerce_input(v) for k, v in inputs.items()}

    proj_rec, proj_store = _project_record(name)
    if proj_rec is not None:
        report = _report_from_record(proj_rec, proj_store)
    else:
        report = anvil.check(name, verbose=False)
    input_names = set(report.get("inputs", []) or [])

    # Array / time-series inputs can't go through System.solve (it coerces every
    # quantity with float(), which raises on arrays). When any input is an array,
    # OR the RSQ is a known array RSQ, call the relation directly and package the
    # returned dict ourselves.
    any_array = any(isinstance(v, np.ndarray) for v in kwargs.values())
    if rec["type"] == "R" and (any_array or has_array_input(rec)):
        rel = load_object(name) if proj_rec is not None else None
        return _solve_relation_direct(name, kwargs, input_names, rel=rel)

    if proj_rec is not None:
        # Project RSQ: anvil.solve only sees the global registry, so build the
        # one-relation System around the loaded object directly.
        obj = load_object(name)
        s = anvil.system(name)
        for k, v in kwargs.items():
            s._add_single(k, v)
        s.use(obj)
        result = s.solve()
    else:
        result = anvil.solve(name, **kwargs)

    # to_json gives us {name: {value, unit}} honoring display vs si.
    parsed = json.loads(result.to_json(si=si))

    results: Dict[str, Any] = {}
    for key, vu in parsed.items():
        results[key] = {
            "value": vu.get("value"),
            "unit": vu.get("unit", "") or "",
            "role": "input" if key in input_names else "output",
        }

    return {
        "name": name,
        "method": getattr(result, "method", "") or "",
        "results": results,
        "inputs": sorted(k for k in results if results[k]["role"] == "input"),
        "outputs": sorted(k for k in results if results[k]["role"] == "output"),
    }


def _solve_relation_direct(name: str, kwargs: Dict[str, Any],
                           input_names: set, rel=None) -> Dict[str, Any]:
    """Call a Relation directly (anvil.R.<name>(**kwargs)) and package results.

    Used for array / time-series RSQs (fft_spectrum, signal_statistics, ...)
    which the System-based solver can't run. Array outputs are serialized via
    ``_serialize_value`` (capped / downsampled lists with a note). ``rel`` may
    be passed directly for project RSQs (which anvil.R does not know about).
    """
    if rel is None:
        rel = getattr(anvil.R, name, None)
    if rel is None:
        # Fall back to loading from the record (newly-pushed, namespaces stale).
        raise KeyError(name)

    out = rel(**kwargs)
    if not isinstance(out, dict):
        out = {"result": out}

    results: Dict[str, Any] = {}
    # Echo scalar inputs back as inputs (skip arrays to keep payload small).
    for k, v in kwargs.items():
        ser, note = _serialize_value(v)
        entry = {"value": ser, "unit": "", "role": "input"}
        if note:
            entry["note"] = note
        results[k] = entry
    # Outputs from the relation return dict.
    for k, v in out.items():
        ser, note = _serialize_value(v)
        entry = {"value": ser, "unit": "", "role": "output"}
        if note:
            entry["note"] = note
        results[k] = entry

    return {
        "name": name,
        "method": "direct",
        "results": results,
        "inputs": sorted(k for k in results if results[k]["role"] == "input"),
        "outputs": sorted(k for k in results if results[k]["role"] == "output"),
    }


def _serialize_value(v: Any):
    """Serialize a solve value into a JSON-safe form + optional note.

    Returns ``(json_value, note_or_None)``. Scalars pass through; numpy arrays
    become lists, downsampled to MAX_ARRAY_LEN with a note describing the cap.
    """
    if isinstance(v, np.ndarray):
        arr = v
        note = None
        full_len = int(arr.size)
        if arr.ndim > 1:
            # Flatten higher-dim arrays (e.g. spectrogram) row-major for transport.
            arr = arr.reshape(-1)
            note = f"array shape {tuple(v.shape)} flattened ({full_len} values)"
        if arr.size > MAX_ARRAY_LEN:
            step = int(np.ceil(arr.size / MAX_ARRAY_LEN))
            arr = arr[::step]
            cap_note = (f"downsampled {full_len} -> {arr.size} values "
                        f"(every {step}th) for transport")
            note = f"{note}; {cap_note}" if note else cap_note
        lst = [_finite(x) for x in arr.tolist()]
        return lst, note
    if isinstance(v, (np.floating, np.integer)):
        return _finite(float(v)), None
    if isinstance(v, (list, tuple)):
        return [_serialize_value(x)[0] for x in v], None
    if isinstance(v, float):
        return _finite(v), None
    if v is None or isinstance(v, (bool, int, str)):
        return v, None
    # Anvil Quantity or unknown -> reuse _jsonable.
    return _jsonable(v), None


def _finite(x: Any) -> Any:
    """Replace NaN/inf with None so the value is strict-JSON serializable."""
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return x
    if xf != xf or xf in (float("inf"), float("-inf")):
        return None
    return xf


# --------------------------------------------------------------------------- #
# Sweep
# --------------------------------------------------------------------------- #

def sweep(
    name: str,
    param: str,
    values: List[float],
    outputs: Optional[List[str]] = None,
    inputs: Optional[Dict[str, Any]] = None,
    si: bool = True,
) -> Dict[str, Any]:
    rec = get_record(name)
    if rec is None:
        raise KeyError(name)

    fixed = {k: _coerce_input(v) for k, v in (inputs or {}).items()}

    if rec["type"] == "S":
        sys = getattr(anvil.S, name).copy()
        if fixed:
            sys.set(**fixed)
        sweep_result = sys.sweep(param, list(values))
    else:
        # Relation: build a one-relation System so we can sweep a parameter.
        sys = anvil.system(f"_sweep_{name}")
        # Seed every input. The swept param gets the first value as a seed;
        # remaining inputs use provided fixed values or their defaults.
        report = anvil.check(name, verbose=False)
        defaults = report.get("defaults", {}) or {}
        for inp in report.get("inputs", []) or []:
            if inp == param:
                sys._add_single(inp, float(values[0]) if values else 0.0)
            elif inp in fixed:
                sys._add_single(inp, fixed[inp])
            elif inp in defaults:
                sys._add_single(inp, defaults[inp])
        sys.use(name)
        sweep_result = sys.sweep(param, list(values))

    data = json.loads(sweep_result.to_json(si=si))

    # Restrict to requested outputs (always keep the swept param column).
    if outputs:
        keep = {param} | set(outputs)
        data = {k: v for k, v in data.items() if k in keep}

    out_keys = [k for k in data.keys() if k != param]
    return {"name": name, "param": param, "data": data, "outputs": out_keys}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    # Quantity -> its display value, else string.
    try:
        return float(v.value)  # anvil Quantity
    except Exception:
        pass
    try:
        return float(v)
    except Exception:
        return str(v)


# --------------------------------------------------------------------------- #
# CSV parsing
# --------------------------------------------------------------------------- #

# Cap on rows kept in the per-column ``data`` payload (downsampled beyond this).
MAX_CSV_ROWS = 5000


def parse_csv(text: str, max_rows: int = MAX_CSV_ROWS) -> Dict[str, Any]:
    """Parse raw CSV text into columns + per-column data.

    Returns ``{columns, rows, preview, data, note?}``. Numeric columns are
    returned as numbers (with non-parseable cells as None); other columns stay
    strings. Large files are downsampled in ``data`` (preview always shows the
    first ~10 actual rows).
    """
    import csv
    import io

    text = text.lstrip("﻿")  # strip a UTF-8 BOM if present
    reader = csv.reader(io.StringIO(text))
    all_rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not all_rows:
        return {"columns": [], "rows": 0, "preview": [], "data": {}}

    header = [h.strip() for h in all_rows[0]]
    # If the header row looks numeric, synthesize column names instead.
    if all(_looks_numeric(h) for h in header):
        ncol = len(header)
        header = [f"col{i}" for i in range(ncol)]
        body = all_rows
    else:
        body = all_rows[1:]

    ncol = len(header)
    # Build raw cell columns.
    raw_cols: List[List[str]] = [[] for _ in range(ncol)]
    for row in body:
        for i in range(ncol):
            raw_cols[i].append(row[i].strip() if i < len(row) else "")

    n_rows = len(body)

    # Decide numeric vs text per column, then convert.
    data: Dict[str, List[Any]] = {}
    for i, col_name in enumerate(header):
        cells = raw_cols[i]
        nonempty = [c for c in cells if c != ""]
        numeric = bool(nonempty) and all(_looks_numeric(c) for c in nonempty)
        if numeric:
            data[col_name] = [_finite(float(c)) if c != "" else None for c in cells]
        else:
            data[col_name] = list(cells)

    note = None
    if n_rows > max_rows:
        step = int(np.ceil(n_rows / max_rows))
        data = {k: v[::step] for k, v in data.items()}
        note = (f"downsampled {n_rows} -> {len(next(iter(data.values())))} rows "
                f"(every {step}th) in 'data' for transport")

    preview = []
    for row in body[:10]:
        preview.append({header[i]: (row[i].strip() if i < len(row) else "")
                        for i in range(ncol)})

    result = {
        "columns": header,
        "rows": n_rows,
        "preview": preview,
        "data": data,
    }
    if note:
        result["note"] = note
    return result


def _looks_numeric(s: str) -> bool:
    s = s.strip()
    if s == "":
        return False
    try:
        float(s)
        return True
    except ValueError:
        return False


# --------------------------------------------------------------------------- #
# Visualization (optional; matplotlib guarded)
# --------------------------------------------------------------------------- #

def matplotlib_available() -> bool:
    try:
        import matplotlib  # noqa: F401
        return True
    except Exception:
        return False


def _fig_to_base64(fig) -> str:
    import base64
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def render_sweep_png(name: str, param: str, values: List[float],
                     outputs: Optional[List[str]] = None,
                     inputs: Optional[Dict[str, Any]] = None,
                     si: bool = True) -> Dict[str, Any]:
    """Run a sweep and render it to a base64 PNG via anvil.viz.sweep_plot.

    Returns ``{png_base64: str}``. Raises RuntimeError if matplotlib is missing.
    """
    if not matplotlib_available():
        raise RuntimeError("matplotlib not available")
    import matplotlib
    matplotlib.use("Agg")  # headless backend
    from anvil import viz

    rec = get_record(name)
    if rec is None:
        raise KeyError(name)

    fixed = {k: _coerce_input(v) for k, v in (inputs or {}).items()}

    if rec["type"] == "S":
        sys = getattr(anvil.S, name).copy()
        if fixed:
            sys.set(**fixed)
        sweep_result = sys.sweep(param, list(values))
    else:
        sys = anvil.system(f"_vizsweep_{name}")
        report = anvil.check(name, verbose=False)
        defaults = report.get("defaults", {}) or {}
        for inp in report.get("inputs", []) or []:
            if inp == param:
                sys._add_single(inp, float(values[0]) if values else 0.0)
            elif inp in fixed:
                sys._add_single(inp, fixed[inp])
            elif inp in defaults:
                sys._add_single(inp, defaults[inp])
        sys.use(name)
        sweep_result = sys.sweep(param, list(values))

    fig = viz.sweep_plot(sweep_result, y=outputs, show=False)
    b64 = _fig_to_base64(fig)
    import matplotlib.pyplot as plt
    plt.close(fig)
    return {"png_base64": b64}


def render_convergence_png(name: str, inputs: Optional[Dict[str, Any]] = None,
                           method: Optional[str] = None) -> Dict[str, Any]:
    """Solve a (cyclic) RSQ with monitoring and render its convergence PNG."""
    if not matplotlib_available():
        raise RuntimeError("matplotlib not available")
    import matplotlib
    matplotlib.use("Agg")
    from anvil import viz

    rec = get_record(name)
    if rec is None:
        raise KeyError(name)

    coerced = {k: _coerce_input(v) for k, v in (inputs or {}).items()}
    if rec["type"] == "S":
        sys = getattr(anvil.S, name).copy()
        if coerced:
            sys.set(**coerced)
    else:
        report = anvil.check(name, verbose=False)
        defaults = report.get("defaults", {}) or {}
        sys = anvil.system(f"_vizconv_{name}")
        for inp in report.get("inputs", []) or []:
            if inp in coerced:
                sys._add_single(inp, coerced[inp])
            elif inp in defaults:
                sys._add_single(inp, defaults[inp])
        sys.use(name)

    solve_kwargs: Dict[str, Any] = {"monitor": True}
    if method:
        solve_kwargs["method"] = method
    sys.solve(**solve_kwargs)
    ax = viz.convergence(sys, show=False)
    if ax is None:
        raise RuntimeError("no convergence history (solve did not iterate)")
    fig = ax.figure
    b64 = _fig_to_base64(fig)
    import matplotlib.pyplot as plt
    plt.close(fig)
    return {"png_base64": b64}


def anvil_version() -> str:
    return getattr(anvil, "__version__", "unknown")


def rsq_count() -> int:
    return len(list_registry())
