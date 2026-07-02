"""
Example: RocketCEA + RocketPy Adapter -- Engine & Flight (real-only)
===================================================================

Demonstrates the rocket_cea combustion adapter (Tc, c*, Isp, gamma) and the
rocketpy_flight flight adapter (apogee, v_max), and how rocket_cea wires
into an Anvil System that sizes mass flow from c*.

These adapters are REAL-ONLY: there is no mock fallback. rocket_cea requires
the rocketcea package (pip install rocketcea); rocketpy_flight requires the
rocketpy package (pip install rocketpy). When a package is missing, *calling*
the adapter raises a clear ImportError; this example catches it, prints the
install message, and exits 0 -- so it always runs to completion.
"""

import anvil
from anvil import Q
from anvil.adapters.rocket_cea import rocket_cea, rocketpy_flight, register

W = 64
print("=" * W)
print("  RocketCEA / RocketPy Adapter Example (real-only, no mock)")
print("=" * W)

# register() never needs the external packages; importing is always safe.
register()

# ── 1. Combustion performance over propellant combos ─────────────────────────
print("\n[1] Combustion performance at Pc = 7 MPa, eps = 40 (rocket_cea)")
try:
    print(f"  {'ox/fuel':12s}  {'OF':>5s}  {'Tc (K)':>8s}  {'c* (m/s)':>9s}  {'Isp (s)':>8s}")
    print(f"  {'-'*12}  {'-'*5}  {'-'*8}  {'-'*9}  {'-'*8}")
    for ox, fuel, of in (("LOX", "RP1", 2.27), ("LOX", "LH2", 6.0), ("LOX", "CH4", 3.5)):
        r = rocket_cea(oxidizer=ox, fuel=fuel, OF=of, Pc=7e6, eps=40.0)
        print(f"  {ox+'/'+fuel:12s}  {of:5.2f}  {r['Tc'].value:8.0f}  "
              f"{r['cstar'].value:9.1f}  {r['Isp'].value:8.1f}")

    # ── 3. Pipeline: chamber c* drives required throat-area mass flow ────────
    print("\n  System: mass flow from c* and throat area")
    cea = rocket_cea(oxidizer="LOX", fuel="RP1", OF=2.27, Pc=7e6, eps=40.0)
    eng = anvil.system("engine_point")
    eng.add("Pc", 7e6, "Pa")
    eng.add("cstar", cea["cstar"].value, "m/s")
    eng.add("A_throat", 0.01, "m^2")

    def mass_flow(Pc, A_throat, cstar):
        mdot = Pc * A_throat / cstar
        return {"mdot": Q(mdot, "kg/s")}
    eng.use(mass_flow)
    res = eng.solve_forward()
    print(f"  mdot   = {res['mdot']}")
except ImportError as e:
    print("\n  RocketCEA is not installed -- cannot run the combustion part.")
    print(f"  {e}")
    print("  Install RocketCEA to run this part: pip install rocketcea")

# ── 2. Flight: apogee of a simple sounding rocket ────────────────────────────
print("\n[2] Flight estimate (rocketpy_flight)")
try:
    f = rocketpy_flight(thrust=2000.0, burn_time=4.0, dry_mass=8.0,
                        prop_mass=4.0, Cd=0.5, area=0.008)
    print(f"  apogee    = {f['apogee']}")
    print(f"  v_max     = {f['v_max']}")
    print(f"  v_burnout = {f['v_burnout']}  (source: {f['source']})")
except ImportError as e:
    print("  RocketPy is not installed -- cannot run the flight part.")
    print(f"  {e}")
    print("  Install RocketPy to run this part: pip install rocketpy")

print("\n" + "=" * W)
print("  Done.")
print("=" * W)
