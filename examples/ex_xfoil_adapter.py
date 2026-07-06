"""
Example: XFOIL 2D Airfoil Adapter (real only -- requires XFOIL on PATH)
========================================================================
Demonstrates xfoil_polar and xfoil_alpha_sweep against a real XFOIL binary.
There is no mock mode: if XFOIL is not installed the example exits with
install instructions.

Get XFOIL: https://web.mit.edu/drela/Public/web/xfoil/
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import anvil
from anvil.adapters import xfoil_airfoil
from anvil.adapters.xfoil_airfoil import xfoil_polar, xfoil_alpha_sweep, register

if not xfoil_airfoil.is_available():
    print("XFOIL binary not found on PATH -- skipping example.")
    print("Install: https://web.mit.edu/drela/Public/web/xfoil/")
    print("(put xfoil.exe / xfoil on your PATH, then re-run)")
    raise SystemExit(0)

# ── Single operating point ────────────────────────────────────────────────────
print("=== NACA2412: single point (alpha = 4 deg, Re = 1e6) ===")
r = xfoil_polar(airfoil="NACA2412", Re=1e6, alpha_deg=4.0, Mach=0.1)
print(f"  CL   = {r['CL']:.4f}")
print(f"  CD   = {r['CD']:.5f}")
print(f"  CM   = {r['CM']:.4f}")
print(f"  L/D  = {r['CL']/r['CD']:.1f}")
print(f"  transition (top/bot): {r['xtr_top']:.3f} / {r['xtr_bot']:.3f}")

# ── Polar sweep ───────────────────────────────────────────────────────────────
print("\n=== Alpha sweep (-4 to 12 deg, Re = 1.5e6) ===")
r = xfoil_alpha_sweep(airfoil="NACA2412", Re=1.5e6,
                      alpha_min=-4.0, alpha_max=12.0, alpha_step=2.0,
                      Mach=0.15)
print(f"  Converged points: {r['n_converged']}")
print(f"  CL range: [{r['CL_array'].min():.3f}, {r['CL_array'].max():.3f}]")
best = (r['CL_array'] / r['CD_array']).argmax()
print(f"  Best L/D = {r['LD_max']:.1f} at alpha = {r['alpha_array'][best]:.1f} deg")
print(f"  CL_max   = {r['CL_max']:.3f}")

# ── Reynolds sweep with an Anvil System ──────────────────────────────────────
print("\n=== Reynolds effect on drag (alpha = 4 deg) ===")
sys_ = anvil.system("xfoil_re_study")
sys_.add("airfoil",   "NACA2412")
sys_.add("alpha_deg", 4.0)
sys_.add("Mach",      0.1)
sys_.add("Re",        1e6)   # placeholder; swept below
sys_.use(xfoil_polar)

sweep = sys_.sweep("Re", [2e5, 5e5, 1e6, 2e6, 5e6])
print(f"  {'Re':>10}  {'CL':>7}  {'CD':>8}")
for i in range(len(sweep.table)):
    row = sweep.table.iloc[i]
    print(f"  {row['Re']:10.1e}  {row['CL']:7.4f}  {row['CD']:8.5f}")
print("  (CD drops with Re: thinner boundary layer, later transition)")

# ── Register in project ───────────────────────────────────────────────────────
print("\n=== Register in global registry ===")
register()
print("  xfoil_polar, xfoil_alpha_sweep -> domain aero.xfoil")
