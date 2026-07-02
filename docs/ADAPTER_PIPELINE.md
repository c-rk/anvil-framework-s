# Adapter Integration Pipeline

How to take an external engineering package or CLI tool from *idea* → *tested, deployed Anvil
adapter*. An **adapter** wraps any Python library or command-line tool as a native Anvil `Relation`
so it participates in `System`, `sweep`, `sensitivity`, and `optimize` with automatic unit handling.

See also: `docs/ADAPTER_GUIDE.md` (reference), `docs/wiki/10_adapters.md`, and the live examples in
`src/anvil/adapters/` (`xfoil_airfoil.py`, `openfoam_cfd.py`, `cantera_thermo.py`, `surrogate_models.py`).

---

## 0. Decide tier eligibility first

| | **Tier A (local-first)** | **Tier B (public calculator)** |
|---|---|---|
| Allowed deps | anything (Cantera, SU2, OpenFOAM binaries, conda pkgs) | pure-Python + numpy/scipy only |
| Network/FS/subprocess | yes | **no** (sandboxed) |
| Example adapters | XFOIL, SU2, OpenFOAM, FEniCSx, NASTRAN, Cantera | CoolProp-via-pip, pure-analytical models |

If the adapter shells out to a binary or imports a heavy/optional package, it is **Tier A only**.
Mark this in the adapter's tags (e.g. `tags=["tierA", "cli"]`) so the public registry filter can
exclude it.

---

## 1. Anatomy of an adapter file

Place the file at `src/anvil/adapters/<tool>.py`. Every adapter follows this structure (canonical
reference: `src/anvil/adapters/xfoil_airfoil.py`):

```python
"""
Anvil Adapter: <TOOL> — <what it computes>.
Install: <pip/conda/binary instructions>.
Falls back to <analytical model> when <TOOL> is unavailable.
"""
from anvil import Adapter, Q
import math, shutil, subprocess   # NO module-level import of the external tool

# 1) Analytical MOCK fallback — runs when the real tool is missing.
def _mock_polar(airfoil, Re, alpha_deg, Mach=0.0):
    ...                      # simplified physics
    return CL, CD, CM

# 2) Real-tool invocation — returns None on any failure (signals fallback).
def _run_tool(...):
    try:
        exe = shutil.which("xfoil")
        # write inputs, subprocess.run(..., timeout=T), parse outputs
        return (CL, CD, CM)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None

# 3) Wrapper — Anvil passes inputs as SI floats; return a dict of outputs.
def _polar_call(airfoil, Re, alpha_deg, Mach=0.0):
    res = _run_tool(airfoil, Re, alpha_deg, Mach)
    if res is not None:
        CL, CD, CM = res
        return {"CL": CL, "CD": CD, "CM": CM, "source": "xfoil"}
    CL, CD, CM = _mock_polar(airfoil, Re, alpha_deg, Mach)
    return {"CL": CL, "CD": CD, "CM": CM, "source": "mock"}

# 4) Adapter declaration.
xfoil_polar = Adapter(
    "xfoil_polar",
    backend="python",            # or "cli"
    call=_polar_call,
    inputs={
        "Re":        {"unit": "1",   "desc": "Reynolds number", "default": 1e6},
        "alpha_deg": {"unit": "deg", "desc": "Angle of attack"},
    },
    outputs={
        "CL":     {"unit": "1", "desc": "Lift coefficient"},
        "source": {"desc": "xfoil (real) or mock (fallback)"},
    },
    desc="2D airfoil CL/CD/CM via XFOIL",
    tags=["xfoil", "airfoil", "tierA", "cli"],
)

# 5) Registration entry point.
def register():
    import anvil
    anvil.push(xfoil_polar, domain="aero.xfoil",
               description=xfoil_polar.desc, tags=xfoil_polar.tags)
```

### Key conventions (enforce these)

- **Lazy import.** Never import the external package at module top level — import it *inside* the
  wrapper/invocation function. This lets the adapter file load even when the tool is absent.
- **Mock fallback + `"source"` field.** Every adapter returns a `"source"` output (`"<tool>"` vs
  `"mock"`) so downstream users always know whether a result is real or a placeholder. Prefer a
  graceful analytical fallback over raising; raise only when no sensible fallback exists (then give
  clear install instructions in the message).
- **Units.** Declare each input/output `"unit"`. Anvil passes inputs to the wrapper as **SI floats
  divided into the declared tool unit**, and wraps declared outputs back into `Q(value, unit)`.
  Dimensionless → omit `"unit"` or use `"1"`/`""`. (Implementation: `src/anvil/adapter.py` python
  backend `_wrap_python`.)
- **CLI backend.** For `backend="cli"`, provide `command` (a template with `{placeholders}`),
  `setup` (writes config files), `parse` (reads output files), `timeout`, and `cwd`.

---

## 2. Write an example

Add `examples/ex_<tool>_adapter.py` demonstrating a real call and a `System` integration (mirror
`examples/ex_xfoil_adapter.py`). Examples double as living documentation and smoke tests.

---

## 3. Health-check + assertion tests

`anvil.check("xfoil_polar")` is a **smoke/health check** (`src/anvil/inspect.py`): it loads the RSQ,
runs it once with defaults (or dummy `1.0` inputs), and reports inputs/outputs and any `issues`
(load error, no outputs, test-run exception). It does **not** compare against expected values:

```python
import anvil
report = anvil.check("xfoil_polar", verbose=True)
assert report["ok"]            # loaded + ran cleanly
```

For *correctness* assertions, write a real test in `tests/` (script-style, like
`tests/test_fixes_v05.py`). Adapters must pass on **both paths** — real binary/package present, and
mock mode (CI typically runs mock-only):

```python
r = xfoil_polar(Re=1e6, alpha_deg=5.0)
assert math.isfinite(float(r["CL"])) and r["source"] in ("xfoil", "mock")
assert r["CL"].unit in ("", "1")      # units round-trip
```

You may also pass `tests={...}` to `anvil.push(...)`; this metadata is persisted in the registry
(`rsq.tests` column) for documentation/future use, but is not auto-asserted by `check()` today.

---

## 4. Deploy

1. `register()` is called (either by the user, or wired into `src/anvil/adapters/__init__.py` for
   auto-registration).
2. The adapter is now reachable as `anvil.R.<name>` and `anvil.R.<domain>.<name>`, and usable via
   `system.use(<name>)`.
3. For **Tier B**, confirm the `tierA`/`cli` tag is **absent** (or that the public registry filter
   excludes it) so binary-dependent adapters never reach the sandbox.
4. Document it: add a row to the adapter table in `README.md` and `docs/wiki/10_adapters.md`.

---

## Checklist

- [ ] Tier decided; tagged accordingly.
- [ ] File at `src/anvil/adapters/<tool>.py`, external import is lazy.
- [ ] Analytical mock fallback + `"source"` output field.
- [ ] All inputs/outputs declare units.
- [ ] `register()` pushes to a sensible `domain`.
- [ ] `examples/ex_<tool>_adapter.py` runs.
- [ ] `anvil.check()` reports `ok` on real **and** mock paths; correctness test in `tests/`.
- [ ] README + wiki updated.
