"""
Example: SU2 CFD Adapter (real only -- requires SU2_CFD on PATH)
=================================================================
Demonstrates su2_euler and su2_rans against a real SU2 install.
There is no mock mode: if SU2_CFD or the case files are missing the
example exits with instructions.

Usage:
    python ex_su2_adapter.py <case.cfg> <mesh.su2>

Get SU2 (binaries + tutorial cases with cfg/mesh files):
    https://su2code.github.io/download.html
    Tutorial NACA0012 case: https://su2code.github.io/tutorials/Inviscid_2D_Unconstrained_NACA0012/
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import anvil
from anvil.adapters import su2_aero
from anvil.adapters.su2_aero import su2_euler, su2_rans, register

if not su2_aero.is_available():
    print("SU2_CFD binary not found on PATH -- skipping example.")
    print("Install: https://su2code.github.io/download.html")
    raise SystemExit(0)

if len(sys.argv) < 3:
    print("Usage: python ex_su2_adapter.py <case.cfg> <mesh.su2>")
    print("Grab a tutorial case (cfg + su2 mesh) from:")
    print("  https://su2code.github.io/tutorials/Inviscid_2D_Unconstrained_NACA0012/")
    raise SystemExit(0)

cfg_path, mesh_path = sys.argv[1], sys.argv[2]
for p in (cfg_path, mesh_path):
    if not os.path.exists(p):
        raise SystemExit(f"File not found: {p}")

# ── Euler (inviscid) ─────────────────────────────────────────────────────────
print("=== SU2 Euler: inviscid (M=0.5, AoA=2 deg) ===")
r = su2_euler(cfg_template=cfg_path, mesh=mesh_path, Mach=0.5, AoA_deg=2.0)
print(f"  CL = {r['CL']:.4f}   CD = {r['CD']:.5f}   CM = {r['CM']:.4f}")

# ── Mach sweep: wave drag onset ──────────────────────────────────────────────
print("\n=== Wave drag onset: CD vs Mach (AoA=2 deg, inviscid) ===")
sys_ = anvil.system("su2_mach_sweep")
sys_.add("cfg_template", cfg_path)
sys_.add("mesh",         mesh_path)
sys_.add("AoA_deg",      2.0)
sys_.add("Mach",         0.5)   # placeholder; swept below
sys_.use(su2_euler)

sweep = sys_.sweep("Mach", [0.5, 0.7, 0.8, 0.85, 0.9])
print(f"  {'Mach':>6}  {'CL':>7}  {'CD':>8}")
for i in range(len(sweep.table)):
    row = sweep.table.iloc[i]
    print(f"  {row['Mach']:6.2f}  {row['CL']:7.4f}  {row['CD']:8.5f}")
print("  (CD rises sharply past the drag-divergence Mach number)")

# ── RANS (viscous) -- needs a cfg with a turbulence model + wall BC mesh ─────
# Uncomment if your cfg/mesh pair is a RANS case:
# r2 = su2_rans(cfg_template=cfg_path, mesh=mesh_path,
#               Mach=0.3, AoA_deg=4.0, Reynolds=3e6)
# print(f"  CL = {r2['CL']:.4f}   CD = {r2['CD']:.5f} (pressure + friction)")

# ── Register ─────────────────────────────────────────────────────────────────
print("\n=== Register adapters ===")
register()
