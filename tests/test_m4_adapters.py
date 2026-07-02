"""
M4 adapter tests -- CoolProp, RocketCEA/RocketPy, meshing, UQ.

Script-style (run directly): `python tests/test_m4_adapters.py`.

These adapters are REAL-ONLY: there is no mock fallback. When the required
external package is absent, *calling* the adapter must raise an error whose
message names the package and the pip install command. This suite verifies:

  * importing the adapter modules works WITHOUT the external packages
    (lazy imports),
  * calling coolprop/rocketcea/rocketpy/mesh adapters WITHOUT their package
    raises an error naming the package + install command,
  * uq_montecarlo's native numpy Monte Carlo path returns finite
    mean/std/quantiles with numpy only (no extra packages),
  * uq_montecarlo with surrogate='sklearn' raises a clear error when
    scikit-learn is absent,
  * register() still stores every adapter in the registry.

NOTE: anvil.check() is NOT expected to report ok=True for the
dependency-requiring adapters, because check()'s dummy test run calls the
adapter and that call now raises (the package is missing). That is the
intended behaviour.
"""
import sys
import math

import anvil
from anvil import Q
from anvil.quantity import Quantity

from anvil.adapters.coolprop_props import coolprop_props
from anvil.adapters.rocket_cea import rocket_cea, rocketpy_flight
from anvil.adapters.meshing_geom import mesh_box, mesh_cylinder
from anvil.adapters import coolprop_props as m_coolprop
from anvil.adapters import rocket_cea as m_rocket
from anvil.adapters import meshing_geom as m_mesh
from anvil.adapters import uq_surrogate as m_uq
from anvil.adapters.uq_surrogate import uq_montecarlo

passed = 0
failed = 0


def check(label, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}")


def _f(v):
    """Float value of a Q or plain number."""
    return float(v.value) if isinstance(v, Quantity) else float(v)


def _finite(v):
    try:
        return math.isfinite(_f(v))
    except Exception:
        return False


def _have(pkg):
    import importlib
    try:
        importlib.import_module(pkg)
        return True
    except Exception:
        return False


def _raises_naming(callable_, pkg, install_substr, **kwargs):
    """Call callable_; expect an error mentioning the package + install hint.

    Returns (raised_ok, message). If the package IS installed and the call
    succeeds, returns (True, "<installed>") so the test still passes.
    """
    try:
        callable_(**kwargs)
        return True, "<installed: call succeeded>"
    except Exception as e:
        msg = str(e)
        ok = (pkg.lower() in msg.lower()) and (install_substr.lower() in msg.lower())
        return ok, msg


# ── 1. Modules imported cleanly without external packages ─────────────────────
print("[0] modules import without external packages")
check("coolprop module imported", m_coolprop is not None)
check("rocket module imported", m_rocket is not None)
check("mesh module imported", m_mesh is not None)
check("uq module imported", m_uq is not None)


# ── 1. CoolProp: real-only, raises without CoolProp ───────────────────────────
print("[1] coolprop_props requires CoolProp")
ok, msg = _raises_naming(coolprop_props, "CoolProp", "pip install CoolProp",
                         fluid="Air", T=300.0, P=101325.0)
check("calling without CoolProp raises naming CoolProp + install", ok)
if not _have("CoolProp"):
    check("message mentions 'pip install CoolProp'", "pip install CoolProp" in msg)


# ── 2. RocketCEA + RocketPy: real-only, raise without their package ───────────
print("[2] rocket_cea requires rocketcea")
ok, msg = _raises_naming(rocket_cea, "rocketcea", "pip install rocketcea",
                         oxidizer="LOX", fuel="RP1", OF=2.27, Pc=7e6, eps=40.0)
check("calling without rocketcea raises naming rocketcea + install", ok)
if not _have("rocketcea"):
    check("message mentions 'pip install rocketcea'", "pip install rocketcea" in msg)

print("[2b] rocketpy_flight requires rocketpy")
ok, msg = _raises_naming(rocketpy_flight, "rocketpy", "pip install rocketpy",
                         thrust=2000.0, burn_time=4.0, dry_mass=8.0,
                         prop_mass=4.0, Cd=0.5, area=0.008)
check("calling without rocketpy raises naming rocketpy + install", ok)
if not _have("rocketpy"):
    check("message mentions 'pip install rocketpy'", "pip install rocketpy" in msg)


# ── 3. Meshing: real-only, raises without gmsh ────────────────────────────────
print("[3] mesh_box requires gmsh")
ok, msg = _raises_naming(mesh_box, "gmsh", "pip install gmsh",
                         Lx=1.0, Ly=0.5, Lz=0.2, elem_size=0.05)
check("calling without gmsh raises naming gmsh + install", ok)
if not _have("gmsh"):
    check("message mentions 'pip install gmsh'", "pip install gmsh" in msg)

print("[3b] mesh_cylinder requires gmsh")
ok, msg = _raises_naming(mesh_cylinder, "gmsh", "pip install gmsh",
                         radius=0.5, height=1.0, elem_size=0.1)
check("calling without gmsh raises naming gmsh + install", ok)


# ── 4. UQ Monte Carlo: native numpy path always works ─────────────────────────
print("[4] uq_montecarlo native numpy MC")
r = uq_montecarlo(model="product", a_mean=10.0, a_std=1.0,
                  b_mean=5.0, b_std=0.5, n_samples=20000, seed=0)
check("source starts with montecarlo", str(r["source"]).startswith("montecarlo"))
check("source is native numpy (not sklearn)", r["source"] == "montecarlo+numpy")
check("mean finite ~50", _finite(r["mean"]) and abs(_f(r["mean"]) - 50.0) < 2.0)
check("std finite & positive", _finite(r["std"]) and _f(r["std"]) > 0)
check("quantile order p05 < p50 < p95",
      _f(r["p05"]) < _f(r["p50"]) < _f(r["p95"]))
check("all MC stats finite",
      all(_finite(r[k]) for k in ("mean", "std", "p05", "p50", "p95")))
check("surrogate_r2 finite in (0.9, 1.01]",
      _finite(r["surrogate_r2"]) and 0.9 < _f(r["surrogate_r2"]) <= 1.01)
# sum model: analytic mean = 15, std = sqrt(1^2+0.5^2) ~ 1.118
rs = uq_montecarlo(model="sum", a_mean=10.0, a_std=1.0,
                   b_mean=5.0, b_std=0.5, n_samples=50000, seed=1)
check("sum mean ~15", abs(_f(rs["mean"]) - 15.0) < 0.2)
check("sum std ~1.118", abs(_f(rs["std"]) - math.sqrt(1.0 + 0.25)) < 0.1)
# surrogate='none' still returns finite MC stats
rn = uq_montecarlo(model="product", surrogate="none", n_samples=5000, seed=2)
check("surrogate='none' MC stats finite",
      all(_finite(rn[k]) for k in ("mean", "std", "p05", "p50", "p95")))

print("[4b] uq_montecarlo surrogate='sklearn' requires scikit-learn")
ok, msg = _raises_naming(uq_montecarlo, "scikit-learn", "pip install scikit-learn",
                         model="product", surrogate="sklearn",
                         n_samples=2000, seed=0)
check("surrogate='sklearn' without sklearn raises naming scikit-learn", ok)


# ── 5. register() still stores every adapter ──────────────────────────────────
print("[5] register() stores adapters in the registry")
m_coolprop.register()
m_rocket.register()
m_mesh.register()
m_uq.register()

from anvil.registry import _get_store
store = _get_store()

expected = {
    "coolprop_props":  "thermo.coolprop",
    "rocket_cea":      "propulsion.cea",
    "rocketpy_flight": "propulsion.cea",
    "mesh_box":        "geometry.mesh",
    "mesh_cylinder":   "geometry.mesh",
    "uq_montecarlo":   "uq.montecarlo",
}
for name, domain in expected.items():
    rec = store.get(name)
    check(f"'{name}' registered", rec is not None)
    if rec is not None:
        check(f"'{name}' in domain {domain}", rec.get("domain") == domain)

# uq_montecarlo's native MC path passes anvil.check (no extra package needed).
rep = anvil.check("uq_montecarlo", verbose=False)
check("check('uq_montecarlo').ok (native numpy)", rep["ok"] is True)
check("uq_montecarlo produces a source output", "source" in rep["outputs"])


# ── 6. Tier tagging sanity ────────────────────────────────────────────────────
print("[6] tier tags")
check("coolprop tagged tierB (not tierA)",
      "tierB" in coolprop_props.tags and "tierA" not in coolprop_props.tags)
check("rocket_cea tagged tierA", "tierA" in rocket_cea.tags)
check("mesh_box tagged tierA/cli",
      "tierA" in mesh_box.tags and "cli" in mesh_box.tags)
check("uq tagged tierB", "tierB" in uq_montecarlo.tags)


print("\n" + "=" * 50)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 50)
if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
