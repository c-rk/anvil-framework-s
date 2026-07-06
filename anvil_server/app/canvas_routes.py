"""Canvas <-> Python-script bridge.

Canvases are persisted as RUNNABLE Anvil scripts in the repo-level ``canvases/``
folder. A saved canvas runs standalone (``python canvases/<name>.py``) and loads
back into the web canvas with full fidelity via a single-line JSON metadata
comment. Foreign scripts (e.g. ``examples/ex*.py``) are imported best-effort by
AST analysis -- the source is NEVER executed during parsing.

Canonical format (v1)::

    \"\"\"Anvil canvas: <name>

    <description>
    \"\"\"
    # %% anvil-canvas v1
    import numpy as np
    import anvil

    sys = anvil.system("<name>")
    sys.add("P0", 7000000.0, "Pa")
    sys.use("choked_mass_flow")

    result = sys.solve()
    result.summary()

    sweep = sys.sweep("P0", np.linspace(5000000.0, 9000000.0, 20))
    sweep.summary(outputs=["mdot"])

    # %% anvil-canvas-meta
    # {"version": 1, "positions": {...}, "blocks": [...], "renames": {...}}

Endpoints
---------
GET    /api/canvases                  list saved canvases
GET    /api/canvases/{name}           load one (script + parsed CanvasGraph)
PUT    /api/canvases/{name}           save a CanvasGraph as a canonical script
DELETE /api/canvases/{name}           remove a saved canvas
POST   /api/canvases/parse            best-effort parse of arbitrary script text
GET    /api/example-scripts           list examples/*.py
GET    /api/example-scripts/{fname}   best-effort parse of one example script
"""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

_REPO_ROOT = Path(__file__).resolve().parents[2]
CANVAS_DIR = _REPO_ROOT / "canvases"
EXAMPLES_DIR = _REPO_ROOT / "examples"

_MARKER = "# %% anvil-canvas v1"
_META_MARKER = "# %% anvil-canvas-meta"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #

class CanvasQuantity(BaseModel):
    name: str
    value: float
    unit: str = ""
    pos: Dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "y": 0.0})


class CanvasRelation(BaseModel):
    name: str
    pos: Dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "y": 0.0})
    renames: Dict[str, str] = Field(default_factory=dict)


class CanvasBlock(BaseModel):
    id: str
    kind: str  # "arith" | "sweep" | "plot" | "csv"
    config: Dict[str, Any] = Field(default_factory=dict)
    pos: Dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "y": 0.0})


class CanvasGraph(BaseModel):
    name: str = "canvas"
    description: str = ""
    quantities: List[CanvasQuantity] = Field(default_factory=list)
    relations: List[CanvasRelation] = Field(default_factory=list)
    blocks: List[CanvasBlock] = Field(default_factory=list)


class SaveRequest(BaseModel):
    canvas: CanvasGraph


class ParseRequest(BaseModel):
    script: str


# --------------------------------------------------------------------------- #
# Serializer: CanvasGraph -> canonical runnable script
# --------------------------------------------------------------------------- #

def serialize_canvas(canvas: CanvasGraph) -> str:
    name = canvas.name or "canvas"
    desc = (canvas.description or "").strip()
    lines: List[str] = []
    lines.append(f'"""Anvil canvas: {name}')
    lines.append("")
    if desc:
        lines.append(desc)
        lines.append("")
    lines.append('Runs standalone:  python <this file>.py')
    lines.append('"""')
    lines.append(_MARKER)
    lines.append("import numpy as np")
    lines.append("import anvil")
    lines.append("")
    lines.append(f'sys = anvil.system({name!r})')

    for q in canvas.quantities:
        if q.unit:
            lines.append(f'sys.add({q.name!r}, {q.value!r}, {q.unit!r})')
        else:
            lines.append(f'sys.add({q.name!r}, {q.value!r})')

    for r in canvas.relations:
        if r.renames:
            lines.append(f'sys.use({r.name!r}, map={dict(r.renames)!r})')
        else:
            lines.append(f'sys.use({r.name!r})')

    lines.append("")
    lines.append("result = sys.solve()")
    lines.append("result.summary()")

    # Arithmetic blocks: full fidelity lives in the meta JSON; emit a readable
    # comment so the standalone script documents the derived math.
    arith = [b for b in canvas.blocks if b.kind == "arith"]
    if arith:
        lines.append("")
        lines.append("# Arithmetic blocks (evaluated client-side on the canvas):")
        for b in arith:
            cfg = b.config or {}
            op = cfg.get("op", "?")
            out = cfg.get("outName", b.id)
            expr = cfg.get("expression", "")
            note = expr or op
            lines.append(f"#   {out} = [{note}]")

    sweeps = [b for b in canvas.blocks if b.kind == "sweep"]
    for i, b in enumerate(sweeps):
        cfg = b.config or {}
        param = cfg.get("param", "")
        lo = float(cfg.get("min", 0.0))
        hi = float(cfg.get("max", 1.0))
        steps = int(cfg.get("steps", 10))
        outputs = list(cfg.get("outputs", []) or [])
        var = "sweep" if len(sweeps) == 1 else f"sweep_{i + 1}"
        if param:
            lines.append("")
            lines.append(
                f'{var} = sys.sweep({param!r}, np.linspace({lo!r}, {hi!r}, {steps}))'
            )
            if outputs:
                lines.append(f"{var}.summary(outputs={outputs!r})")
            else:
                lines.append(f"{var}.summary()")

    meta = {
        "version": 1,
        "positions": {
            **{q.name: q.pos for q in canvas.quantities},
            **{r.name: r.pos for r in canvas.relations},
        },
        "blocks": [b.model_dump() for b in canvas.blocks],
        "renames": {r.name: r.renames for r in canvas.relations if r.renames},
        "description": desc,
    }
    lines.append("")
    lines.append(_META_MARKER)
    lines.append("# " + json.dumps(meta, separators=(",", ":")))
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Parser: script -> CanvasGraph (+warnings). AST ONLY -- never executes code.
# --------------------------------------------------------------------------- #

def _unit_si(value: float, unit: str) -> Optional[float]:
    """SI value of ``value unit`` via the anvil unit engine.

    Safe for foreign scripts: only ever called with already-resolved numeric
    literals and literal unit strings — never with script code.
    """
    if not unit:
        return float(value)
    try:
        import anvil

        return float(anvil.Quantity(float(value), unit).si)
    except Exception:  # noqa: BLE001 - unknown unit etc.
        return None


def _q_call(node: ast.AST) -> Optional[Tuple[ast.AST, str]]:
    """Match ``Q(v[, "unit"])`` / ``anvil.Q(...)`` / ``Quantity(...)``.

    Returns (value_node, unit_string) or None.
    """
    if not isinstance(node, ast.Call):
        return None
    f = node.func
    fname = None
    if isinstance(f, ast.Name):
        fname = f.id
    elif (
        isinstance(f, ast.Attribute)
        and isinstance(f.value, ast.Name)
        and f.value.id == "anvil"
    ):
        fname = f.attr
    if fname not in ("Q", "Quantity") or not node.args:
        return None
    unit = _str_const(node.args[1]) if len(node.args) > 1 else ""
    return node.args[0], unit or ""


# A binding is {"value": float, "unit": str, "si": float|None} for a script-level
# ``name = <literal expr>`` assignment (unit "" for plain numbers).
_Bindings = Dict[str, Dict[str, Any]]


def _const_eval(node: ast.AST, bindings: _Bindings) -> Optional[float]:
    """Safely evaluate a numeric-literal expression. Returns None if not constant."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _const_eval(node.operand, bindings)
        if v is None:
            return None
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp) and isinstance(
        node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
    ):
        a = _const_eval(node.left, bindings)
        b = _const_eval(node.right, bindings)
        if a is None or b is None:
            return None
        try:
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Div):
                return a / b
            return a ** b
        except Exception:  # noqa: BLE001 - div by zero etc.
            return None
    if isinstance(node, ast.Name):
        b = bindings.get(node.id)
        if b is None:
            return None
        # Plain numbers evaluate directly; united quantities contribute their
        # SI value (so arithmetic like b*h**3/12 over Q() bindings stays right).
        return b["value"] if not b["unit"] else b["si"]
    # X.si / Q(...).si -> SI value
    if isinstance(node, ast.Attribute) and node.attr == "si":
        if isinstance(node.value, ast.Name):
            b = bindings.get(node.value.id)
            return b["si"] if b is not None else None
        q = _q_call(node.value)
        if q is not None:
            v = _const_eval(q[0], bindings)
            if v is not None:
                return _unit_si(v, q[1])
        return None
    # Bare Q(v, "unit") in arithmetic position -> SI value
    q = _q_call(node)
    if q is not None:
        v = _const_eval(q[0], bindings)
        if v is not None:
            return _unit_si(v, q[1])
    return None


def _value_unit(
    node: ast.AST, bindings: _Bindings
) -> Optional[Tuple[float, str]]:
    """Resolve an add()/set() value expression to (value, display_unit).

    Handles Q(v, "u") literals, names bound to Q literals (keeps their unit),
    ``X.si`` (SI value, no display unit), and plain numeric expressions.
    """
    q = _q_call(node)
    if q is not None:
        v = _const_eval(q[0], bindings)
        return (v, q[1]) if v is not None else None
    if isinstance(node, ast.Name):
        b = bindings.get(node.id)
        if b is not None:
            return (b["value"], b["unit"])
        return None
    v = _const_eval(node, bindings)
    if v is not None:
        return (v, "")
    return None


def _str_const(node: ast.AST, bindings: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Literal string, or (with bindings) an f-string whose holes are constant.

    f-string support lets unrolled loops produce real names: with i bound to 2,
    ``f"q_{i}"`` resolves to ``"q_2"``.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr) and bindings is not None:
        parts: List[str] = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            elif isinstance(v, ast.FormattedValue):
                val = _const_eval(v.value, bindings)
                if val is None:
                    s = _str_const(v.value, bindings)
                    if s is None:
                        return None
                    parts.append(s)
                else:
                    f = float(val)
                    parts.append(str(int(f)) if f.is_integer() else str(f))
            else:
                return None
        return "".join(parts)
    return None


def _extract_meta(script: str) -> Optional[Dict[str, Any]]:
    idx = script.find(_META_MARKER)
    if idx < 0:
        return None
    for line in script[idx + len(_META_MARKER):].splitlines():
        line = line.strip()
        if line.startswith("#"):
            payload = line.lstrip("#").strip()
            if payload.startswith("{"):
                try:
                    return json.loads(payload)
                except Exception:  # noqa: BLE001
                    return None
    return None


def parse_script(script: str) -> Tuple[CanvasGraph, List[str]]:
    """Parse python source into a CanvasGraph. AST-only; never executes code."""
    warnings: List[str] = []
    try:
        tree = ast.parse(script)
    except SyntaxError as exc:
        raise ValueError(f"not valid Python: {exc}")

    name = "canvas"
    description = ""
    doc = ast.get_docstring(tree) or ""
    if doc:
        first, *rest = doc.splitlines()
        m = re.match(r"Anvil canvas:\s*(.+)", first.strip())
        if m:
            name = m.group(1).strip()
            description = "\n".join(rest).strip()
        else:
            description = doc.strip()

    sys_vars: set = set()
    system_names: List[str] = []
    quantities: List[CanvasQuantity] = []
    relations: List[CanvasRelation] = []
    sweep_blocks: List[CanvasBlock] = []
    sweep_vars: Dict[str, CanvasBlock] = {}
    sweep_call_blocks: Dict[int, CanvasBlock] = {}
    bindings: _Bindings = {}
    seen_q: set = set()
    seen_r: set = set()

    def is_sys_call(call: ast.Call, method: str) -> bool:
        f = call.func
        return (
            isinstance(f, ast.Attribute)
            and f.attr == method
            and isinstance(f.value, ast.Name)
            and f.value.id in sys_vars
        )

    def _system_ctor_name(call: ast.Call) -> Optional[str]:
        """Match anvil.system("x") / anvil.System("x") / System("x")."""
        f = call.func
        ok = (
            isinstance(f, ast.Attribute)
            and f.attr in ("system", "System")
            and isinstance(f.value, ast.Name)
            and f.value.id == "anvil"
        ) or (isinstance(f, ast.Name) and f.id == "System")
        if not ok:
            return None
        n = _str_const(call.args[0]) if call.args else None
        return n or "canvas"

    def _registry_system_ref(node: ast.AST) -> Optional[str]:
        """Match anvil.S.<name> with optional trailing .copy()."""
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "copy"
        ):
            node = node.func.value
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "S"
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "anvil"
        ):
            return node.attr
        return None

    def _add_quantity(qname: str, node: ast.AST, lineno: int, unit_override: str = ""):
        if not qname or qname in seen_q:
            return
        vu = _value_unit(node, bindings)
        if vu is None or vu[0] is None:
            warnings.append(
                f"line {lineno}: could not resolve value for "
                f"quantity '{qname}' (skipped)"
            )
            return
        value, unit = vu
        if unit_override:
            unit = unit_override
        seen_q.add(qname)
        quantities.append(CanvasQuantity(name=qname, value=value, unit=unit or ""))

    # ---- pass 1: system variables + literal bindings ------------------------
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if isinstance(node.value, ast.Call):
            ctor = _system_ctor_name(node.value)
            if ctor is not None:
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        sys_vars.add(t.id)
                system_names.append(ctor)
                if len(system_names) == 1 and ctor != "canvas":
                    name = ctor
                continue
        ref = _registry_system_ref(node.value)
        if ref is not None:
            # x = anvil.S.rocket_nozzle.copy() -> the prebuilt System IS the node
            for t in node.targets:
                if isinstance(t, ast.Name):
                    sys_vars.add(t.id)
            system_names.append(ref)
            if ref not in seen_r:
                seen_r.add(ref)
                relations.append(CanvasRelation(name=ref))
            if len(system_names) == 1:
                name = ref
            continue
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            vu = _value_unit(node.value, bindings)
            if vu is not None and vu[0] is not None:
                v, u = vu
                bindings[node.targets[0].id] = {
                    "value": float(v),
                    "unit": u or "",
                    "si": _unit_si(v, u or ""),
                }

    if len(system_names) > 1:
        warnings.append(
            f"script builds {len(system_names)} systems "
            f"({', '.join(system_names)}); they were merged onto one canvas"
        )

    # ---- pass 2: source-order statement walk with loop unrolling -------------
    MAX_UNROLL = 500
    unrolled = {"count": 0}
    rel_by_name: Dict[str, CanvasRelation] = {}

    def _registry_has(fname: str) -> bool:
        """Is there a registry / project RSQ with this name? (read-only lookup)."""
        try:
            from . import executor

            return executor.get_record(fname) is not None
        except Exception:  # noqa: BLE001 - outside server context
            return False

    def _has_sys_call(st: ast.AST) -> bool:
        for n in ast.walk(st):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id in sys_vars
            ):
                return True
        return False

    def _iter_values(node: ast.AST) -> Optional[List[float]]:
        """Constant loop iterable: range / [..] / (..) / np.linspace / np.array."""
        if isinstance(node, (ast.List, ast.Tuple)):
            vals = [_const_eval(e, bindings) for e in node.elts]
            if vals and all(v is not None for v in vals):
                return [float(v) for v in vals]  # type: ignore[arg-type]
            return None
        if not isinstance(node, ast.Call):
            return None
        f = node.func
        if isinstance(f, ast.Name) and f.id == "range":
            args = [_const_eval(a, bindings) for a in node.args]
            if args and all(a is not None for a in args) and len(args) <= 3:
                try:
                    return [float(v) for v in range(*(int(a) for a in args))]  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    return None
            return None
        if isinstance(f, ast.Attribute) and f.attr == "linspace" and len(node.args) >= 3:
            a = [_const_eval(x, bindings) for x in node.args[:3]]
            if all(v is not None for v in a):
                n = int(a[2])  # type: ignore[arg-type]
                if n == 1:
                    return [float(a[0])]  # type: ignore[arg-type]
                if n > 1:
                    lo, hi = float(a[0]), float(a[1])  # type: ignore[arg-type]
                    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]
            return None
        if (
            isinstance(f, ast.Attribute)
            and f.attr == "array"
            and node.args
            and isinstance(node.args[0], (ast.List, ast.Tuple))
        ):
            vals = [_const_eval(e, bindings) for e in node.args[0].elts]
            if vals and all(v is not None for v in vals):
                return [float(v) for v in vals]  # type: ignore[arg-type]
        return None

    def _process_call(node: ast.Call) -> None:
        if is_sys_call(node, "add"):
            if node.args:
                qname = _str_const(node.args[0], bindings)
                if qname is None:
                    return
                unit = _str_const(node.args[2]) if len(node.args) > 2 else ""
                if not unit:
                    for kw in node.keywords:
                        if kw.arg == "unit":
                            unit = _str_const(kw.value) or ""
                if len(node.args) > 1:
                    _add_quantity(qname, node.args[1], node.lineno, unit or "")
            else:
                # kwargs style: sys.add(T0=3500, P0=Q(1, "atm"))
                for kw in node.keywords:
                    if kw.arg is None or kw.arg in ("desc", "bounds", "role", "unit"):
                        continue
                    _add_quantity(kw.arg, kw.value, node.lineno)
        elif is_sys_call(node, "set"):
            # set() overrides prebuilt-System defaults -> canvas input quantities
            for kw in node.keywords:
                if kw.arg is None:
                    continue
                _add_quantity(kw.arg, kw.value, node.lineno)
        elif is_sys_call(node, "use") and node.args:
            rname = _str_const(node.args[0], bindings)
            if rname is None and isinstance(node.args[0], ast.Name):
                # sys.use(local_fn): importable when the function was pushed to
                # the registry / project DB under the same name.
                fname = node.args[0].id
                if _registry_has(fname):
                    rname = fname
                else:
                    warnings.append(
                        f"line {node.lineno}: custom function "
                        f"'{fname}' is not in the registry — push it "
                        f"(anvil.push / proj.push) and re-import to get it "
                        f"on the canvas"
                    )
                    return
            if rname is None:
                warnings.append(
                    f"line {node.lineno}: sys.use(<non-literal>) skipped"
                )
                return
            renames: Dict[str, str] = {}
            for kw in node.keywords:
                if kw.arg == "map" and isinstance(kw.value, ast.Dict):
                    for kn, vn in zip(kw.value.keys, kw.value.values):
                        k, v = _str_const(kn), _str_const(vn, bindings)
                        if k and v:
                            renames[k] = v
            if rname not in seen_r:
                seen_r.add(rname)
                rel = CanvasRelation(name=rname, renames=renames)
                rel_by_name[rname] = rel
                relations.append(rel)
            elif renames and rel_by_name.get(rname) is not None and (
                rel_by_name[rname].renames != renames
            ):
                warnings.append(
                    f"line {node.lineno}: duplicate sys.use('{rname}') with a "
                    f"different map skipped (one node per relation)"
                )
        elif is_sys_call(node, "sweep") and node.args:
            param = _str_const(node.args[0], bindings)
            cfg: Dict[str, Any] = {"param": param or "", "outputs": []}
            if len(node.args) > 1:
                vals = _iter_values(node.args[1])
                if vals:
                    cfg["min"], cfg["max"], cfg["steps"] = (
                        min(vals),
                        max(vals),
                        len(vals),
                    )
            if param and id(node) not in sweep_call_blocks:
                block = CanvasBlock(
                    id=f"sweep_{len(sweep_blocks) + 1}",
                    kind="sweep",
                    config=cfg,
                )
                sweep_blocks.append(block)
                sweep_call_blocks[id(node)] = block

    def _process_stmts(stmts: List[ast.stmt]) -> None:
        for st in stmts:
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue  # not executed at import; sys.use(fn) resolves via registry
            if isinstance(st, ast.For):
                vals = _iter_values(st.iter)
                if (
                    vals is not None
                    and isinstance(st.target, ast.Name)
                    and unrolled["count"] + len(vals) <= MAX_UNROLL
                ):
                    saved = bindings.get(st.target.id)
                    for v in vals:
                        unrolled["count"] += 1
                        bindings[st.target.id] = {
                            "value": float(v),
                            "unit": "",
                            "si": float(v),
                        }
                        _process_stmts(st.body)
                    if saved is None:
                        bindings.pop(st.target.id, None)
                    else:
                        bindings[st.target.id] = saved
                elif _has_sys_call(st):
                    warnings.append(
                        f"line {st.lineno}: for-loop could not be unrolled "
                        f"(non-constant iterable) — its sys.* calls were skipped"
                    )
                continue
            if isinstance(st, ast.While):
                if _has_sys_call(st):
                    warnings.append(
                        f"line {st.lineno}: while-loop cannot be unrolled — "
                        f"its sys.* calls were skipped"
                    )
                continue
            if isinstance(st, ast.If):
                _process_stmts(st.body)
                _process_stmts(st.orelse)
                continue
            if isinstance(st, (ast.With, ast.AsyncWith)):
                _process_stmts(st.body)
                continue
            if isinstance(st, ast.Try):
                _process_stmts(st.body)
                for h in st.handlers:
                    _process_stmts(h.body)
                _process_stmts(st.orelse)
                _process_stmts(st.finalbody)
                continue
            # Plain statement: process its calls, then refresh bindings so
            # values computed inside unrolled loop bodies stay per-iteration.
            for c in ast.walk(st):
                if isinstance(c, ast.Call):
                    _process_call(c)
            if (
                isinstance(st, ast.Assign)
                and len(st.targets) == 1
                and isinstance(st.targets[0], ast.Name)
            ):
                vu = _value_unit(st.value, bindings)
                if vu is not None and vu[0] is not None:
                    v, u = vu
                    bindings[st.targets[0].id] = {
                        "value": float(v),
                        "unit": u or "",
                        "si": _unit_si(v, u or ""),
                    }

    _process_stmts(tree.body)

    # ---- pass 3: sweep vars + their summary(outputs=[...]) -------------------
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and id(node.value) in sweep_call_blocks
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            sweep_vars[node.targets[0].id] = sweep_call_blocks[id(node.value)]
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        f = node.func
        if (
            f.attr == "summary"
            and isinstance(f.value, ast.Name)
            and f.value.id in sweep_vars
        ):
            for kw in node.keywords:
                if kw.arg == "outputs" and isinstance(kw.value, (ast.List, ast.Tuple)):
                    outs = [_str_const(e) for e in kw.value.elts]
                    sweep_vars[f.value.id].config["outputs"] = [
                        o for o in outs if o
                    ]

    blocks: List[CanvasBlock] = list(sweep_blocks)
    meta = _extract_meta(script)
    if meta:
        description = meta.get("description", description) or description
        positions = meta.get("positions", {}) or {}
        renames = meta.get("renames", {}) or {}
        for q in quantities:
            if q.name in positions:
                q.pos = positions[q.name]
        for r in relations:
            if r.name in positions:
                r.pos = positions[r.name]
            if r.name in renames:
                r.renames = renames[r.name]
        meta_blocks = []
        for raw in meta.get("blocks", []) or []:
            try:
                meta_blocks.append(CanvasBlock(**raw))
            except Exception:  # noqa: BLE001
                warnings.append("malformed block in canvas metadata (skipped)")
        if meta_blocks:
            blocks = meta_blocks  # meta carries full fidelity (incl. sweeps)
    else:
        # Auto-layout foreign scripts in a simple grid.
        for i, q in enumerate(quantities):
            q.pos = {"x": 60.0, "y": 60.0 + 110.0 * i}
        for i, r in enumerate(relations):
            r.pos = {"x": 380.0, "y": 80.0 + 150.0 * i}
        for i, b in enumerate(blocks):
            b.pos = {"x": 700.0, "y": 80.0 + 150.0 * i}

    graph = CanvasGraph(
        name=name,
        description=description,
        quantities=quantities,
        relations=relations,
        blocks=blocks,
    )
    if not quantities and not relations:
        warnings.append("no sys.add / sys.use calls found — empty canvas")
    return graph, warnings


# --------------------------------------------------------------------------- #
# File helpers
# --------------------------------------------------------------------------- #

def _safe_canvas_path(name: str) -> Path:
    if not _SAFE_NAME.match(name):
        raise HTTPException(
            status_code=400,
            detail="canvas name must be 1-80 chars of letters/digits/_/- only",
        )
    return CANVAS_DIR / f"{name}.py"


def _first_doc_line(script: str) -> str:
    try:
        doc = ast.get_docstring(ast.parse(script)) or ""
    except SyntaxError:
        return ""
    return doc.splitlines()[0].strip() if doc else ""


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

@router.get("/api/canvases")
async def list_canvases() -> Dict[str, Any]:
    CANVAS_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for p in sorted(CANVAS_DIR.glob("*.py")):
        try:
            script = p.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        desc = _first_doc_line(script)
        desc = re.sub(r"^Anvil canvas:\s*", "", desc)
        items.append(
            {
                "name": p.stem,
                "description": desc,
                "modified": datetime.fromtimestamp(
                    p.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
            }
        )
    return {"items": items}


@router.get("/api/canvases/{name}")
async def get_canvas(name: str) -> Dict[str, Any]:
    path = _safe_canvas_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"canvas '{name}' not found")
    script = path.read_text(encoding="utf-8")
    try:
        graph, warnings = parse_script(script)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "name": name,
        "script": script,
        "canvas": graph.model_dump(),
        "warnings": warnings,
    }


@router.put("/api/canvases/{name}")
async def put_canvas(name: str, req: SaveRequest) -> Dict[str, Any]:
    path = _safe_canvas_path(name)
    canvas = req.canvas
    canvas.name = name
    script = serialize_canvas(canvas)
    CANVAS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(script, encoding="utf-8")
    return {"script": script, "path": str(path)}


@router.delete("/api/canvases/{name}")
async def delete_canvas(name: str) -> Dict[str, Any]:
    path = _safe_canvas_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"canvas '{name}' not found")
    path.unlink()
    return {"deleted": name}


@router.post("/api/canvases/parse")
async def parse_canvas(req: ParseRequest) -> Dict[str, Any]:
    try:
        graph, warnings = parse_script(req.script)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"canvas": graph.model_dump(), "warnings": warnings}


# Cache for the example-script listing: {path: (mtime, entry_or_None)}.
# An entry of None means the script parsed to an empty canvas (nothing to
# show), so it is left out of the menu instead of loading a blank page.
_EXAMPLE_CACHE: Dict[str, Any] = {}


def _example_entry(p: Path) -> Optional[Dict[str, str]]:
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return None
    cached = _EXAMPLE_CACHE.get(str(p))
    if cached is not None and cached[0] == mtime:
        return cached[1]

    entry: Optional[Dict[str, str]] = None
    try:
        script = p.read_text(encoding="utf-8")
        graph, _warnings = parse_script(script)
        # Only list scripts that convert into a *solvable* canvas: at least
        # one relation wired to at least one quantity. Quantity-only parses
        # (e.g. adapter demos whose relations are adapter objects the parser
        # cannot resolve) load as inert canvases and are omitted.
        if graph.relations and graph.quantities:
            entry = {"id": p.name, "title": _first_doc_line(script) or p.name}
    except Exception:  # noqa: BLE001 - unparseable script -> omit from menu
        entry = None

    _EXAMPLE_CACHE[str(p)] = (mtime, entry)
    return entry


@router.get("/api/example-scripts")
async def list_example_scripts() -> Dict[str, Any]:
    items = []
    if EXAMPLES_DIR.is_dir():
        for p in sorted(EXAMPLES_DIR.glob("*.py")):
            if p.name.startswith("test_"):
                continue  # dev scratch scripts, not curated examples
            entry = _example_entry(p)
            if entry is not None:
                items.append(entry)
    return {"items": items}


@router.get("/api/example-scripts/{fname}")
async def get_example_script(fname: str) -> Dict[str, Any]:
    if EXAMPLES_DIR.is_dir():
        allowed = {p.name for p in EXAMPLES_DIR.glob("*.py")}
    else:
        allowed = set()
    if fname not in allowed:  # also blocks any path traversal
        raise HTTPException(status_code=404, detail=f"example '{fname}' not found")
    script = (EXAMPLES_DIR / fname).read_text(encoding="utf-8")
    try:
        graph, warnings = parse_script(script)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"script": script, "canvas": graph.model_dump(), "warnings": warnings}
