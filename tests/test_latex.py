"""
Tests for typeset-math (LaTeX) metadata on Anvil's built-in RSQs.

Importing anvil triggers seeding/reseeding. seed() was updated to (a) write
metadata={"latex": ...} for every builtin and (b) reseed when latex metadata
changes, so the KaTeX strings must land in the store on import.

Script-style (run directly): `python tests/test_latex.py`.
"""
import sys

import anvil
from anvil.registry import _get_store

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


store = _get_store()


def latex_of(name):
    rec = store.get(name)
    if rec is None:
        return None
    return (rec.get("metadata") or {}).get("latex")


# --- 1. metadata dict is present and carries the latex key -----------------
rec = store.get("dynamic_pressure")
check("dynamic_pressure record has a metadata dict",
      isinstance(rec, dict) and isinstance(rec.get("metadata"), dict))
check("dynamic_pressure metadata has 'latex' key",
      "latex" in (rec.get("metadata") or {}))


# --- 2. known RSQs across domains have non-empty latex ---------------------
expect_latex = [
    "dynamic_pressure", "isentropic_ratios", "tsiolkovsky",
    "lift_force", "drag_force", "normal_shock", "prandtl_meyer",
    "speed_of_sound", "ideal_gas_density", "reynolds_number",
    "conduction_1d", "convection", "radiation",
    "hooke_stress", "axial_stress", "beam_deflection_cantilever",
    "buckling_euler", "thin_wall_hoop_stress",
    "vis_viva", "hohmann_transfer", "orbital_period",
    "specific_impulse", "rocket_thrust", "choked_mass_flow",
    "g0", "sigma_sb",
]
for name in expect_latex:
    lx = latex_of(name)
    check(f"{name} has non-empty latex", isinstance(lx, str) and len(lx) > 0)


# --- 3. at least 30 builtins carry non-empty latex ------------------------
builtins = store.get_all(origin="builtin")
n_latex = sum(
    1 for r in builtins
    if isinstance((r.get("metadata") or {}).get("latex"), str)
    and ((r.get("metadata") or {}).get("latex"))
)
print(f"  (builtins with non-empty latex: {n_latex} of {len(builtins)})")
check("at least 30 builtins have non-empty latex", n_latex >= 30)


# --- 4. an intentionally-blank solver/transform RSQ has empty latex --------
for blank in ["oblique_shock", "pod_analysis", "isa_atmosphere"]:
    lx = latex_of(blank)
    check(f"{blank} latex intentionally blank ('')", lx == "")


print("\n" + "=" * 50)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 50)
if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
