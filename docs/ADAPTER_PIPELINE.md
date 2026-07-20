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
REAL ONLY — NO MOCK MODE: a missing tool raises a clear error naming the
dependency and the exact install command.
"""
from anvil import Adapter, Q
import math, shutil, subprocess   # NO module-level import of the external tool

# 1) Availability gate — locate the tool or raise with install instructions.
def _require_tool():
    exe = shutil.which("xfoil") or shutil.which("xfoil.exe")
    if exe is None:
        raise RuntimeError(
            "XFOIL binary not found on PATH. Install it first:\n"
            "  Linux/WSL:  sudo apt install xfoil\n"
            "  Windows:    https://web.mit.edu/drela/Public/web/xfoil/"
        )
    return exe

def is_available() -> bool:
    """True when the tool is installed (never raises)."""
    return (shutil.which("xfoil") or shutil.which("xfoil.exe")) is not None

# 2) Real-tool invocation — write inputs, run, parse outputs.
def _run_tool(exe, ...):
    # subprocess.run(..., timeout=T), parse output files
    return (CL, CD, CM)

# 3) Wrapper — Anvil passes inputs as SI floats; return a dict of outputs.
#    The availability check happens at CALL time, never at import time, so
#    `import anvil` always succeeds even with zero adapter deps installed.
def _polar_call(airfoil, Re, alpha_deg, Mach=0.0):
    exe = _require_tool()                      # raises if tool missing
    res = _run_tool(exe, airfoil, Re, alpha_deg, Mach)
    if res is None:
        raise RuntimeError("XFOIL run failed or did not converge ...")
    CL, CD, CM = res
    return {"CL": CL, "CD": CD, "CM": CM, "source": "xfoil"}

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
        "source": {"desc": "always 'xfoil' (real run; no mock fallback)"},
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
- **REAL ONLY — no mock fallbacks.** Adapters never substitute analytical stand-in results for the
  real tool. A missing dependency raises `ImportError` (Python package) or `RuntimeError` (binary /
  missing files) whose message names the dependency and the exact install command. Mock physics
  output can be mistaken for real results — that failure mode is banned. Include a module-level
  `is_available() -> bool` so callers can probe without triggering the error. Every adapter still
  returns a `"source"` output naming the real tool that produced the result.
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
`tests/test_fixes_v05.py`). Two paths must be covered — the real run when the dependency is
installed, and the **clear not-installed error** when it is absent (the error path is testable on
every machine; skip the real run when the tool is missing):

```python
if is_available():
    r = xfoil_polar(Re=1e6, alpha_deg=5.0)
    assert math.isfinite(float(r["CL"])) and r["source"] == "xfoil"
else:
    try:
        xfoil_polar(Re=1e6, alpha_deg=5.0)
        assert False, "expected a not-installed error"
    except (ImportError, RuntimeError) as e:
        assert "xfoil" in str(e).lower() and "install" in str(e).lower()
```

Note: `anvil.check()` is **not** expected to report `ok=True` for a dependency-requiring adapter on
a machine without the dependency — its dummy test run calls the adapter, which now raises. That is
the intended behaviour.

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
- [ ] REAL ONLY: no mock fallback; missing dependency raises a clear error naming the install
      command; `is_available()` provided; `"source"` output names the real tool.
- [ ] All inputs/outputs declare units.
- [ ] `register()` pushes to a sensible `domain`.
- [ ] `examples/ex_<tool>_adapter.py` runs (and prints a clear "requires X, install with Y,
      skipping" message when the tool is absent).
- [ ] Correctness test in `tests/`: real path when installed, not-installed error path otherwise.
- [ ] README + wiki updated.
