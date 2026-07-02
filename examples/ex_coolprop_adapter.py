"""
Example: CoolProp Adapter -- Real-Fluid Properties in Anvil (real-only)
======================================================================

Demonstrates the CoolProp adapter (rho, h, cp, mu, a) for several fluids and
how it wires into an Anvil System that computes a pipe-flow Reynolds number.

This adapter is REAL-ONLY: there is no mock fallback. It requires the
CoolProp package (pip install CoolProp). When CoolProp is missing, *calling*
the adapter raises a clear ImportError; this example catches it, prints the
install message, and exits 0 -- so it always runs to completion.
"""

import anvil
from anvil import Q
from anvil.adapters.coolprop_props import coolprop_props, register

W = 64
print("=" * W)
print("  CoolProp Adapter Example (real-only, no mock)")
print("=" * W)

# register() never needs CoolProp; importing the module is always safe.
register()

try:
    # ── 1. Direct adapter calls over several fluids ──────────────────────────
    print("\n[1] Properties at T=300 K, P=101325 Pa")
    print(f"  {'fluid':8s}  {'rho':>10s}  {'cp':>10s}  {'a (m/s)':>9s}  {'source':>9s}")
    print(f"  {'-'*8}  {'-'*10}  {'-'*10}  {'-'*9}  {'-'*9}")
    for fluid in ("Air", "N2", "O2", "CO2", "CH4"):
        r = coolprop_props(fluid=fluid, T=300.0, P=101325.0)
        print(f"  {fluid:8s}  {r['rho'].value:10.4f}  {r['cp'].value:10.1f}  "
              f"{r['a'].value:9.1f}  {str(r['source']):>9s}")

    # ── 2. Pipeline: adapter properties feed a Reynolds-number System ────────
    print("\n[2] Pipe-flow Reynolds number using adapter rho & mu")
    props = coolprop_props(fluid="Air", T=300.0, P=5e5)
    print(f"  rho    = {props['rho']}")
    print(f"  mu     = {props['mu']}  (source: {props['source']})")

    pipe = anvil.system("pipe_flow")
    pipe.add("rho", props["rho"].value, "kg/m^3")
    pipe.add("mu", props["mu"].value, "Pa*s")
    pipe.add("D_pipe", 0.05, "m")
    pipe.add("V_flow", 10.0, "m/s")

    def reynolds(rho, mu, D_pipe, V_flow):
        Re = rho * V_flow * D_pipe / mu
        return {"Re": Q(Re, "1")}
    pipe.use(reynolds)

    res = pipe.solve_forward()
    print(f"  Re     = {res['Re'].value:.0f}")

except ImportError as e:
    print("\n  CoolProp is not installed -- cannot run this example.")
    print(f"  {e}")
    print("\n  Install CoolProp to run this example: pip install CoolProp")

print("\n" + "=" * W)
print("  Done.")
print("=" * W)
