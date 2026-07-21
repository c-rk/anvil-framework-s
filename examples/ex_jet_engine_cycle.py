"""
Jet Engine Cycle Analysis (GasTurb style)
=========================================

Demonstrates:
    - Full-system gas-turbine cycle analysis from native Anvil components
    - Turbojet, two-spool turbofan, afterburning turbojet and turboprop points
    - Per-station stagnation table (T0, P0)
    - Parametric sweep of compressor pressure ratio
    - Optimizing the cycle for maximum specific thrust
    - Generating T-s and h-s (Mollier) cycle diagrams

Engineering context:
    Each engine is built station-by-station (intake, compressor, combustor,
    turbine, nozzle, ...) from small Relations that pass the stagnation state
    down the flow path. The result is a solvable System you can sweep and
    optimize like any other Anvil problem.
"""

from anvil import propulsion as jet

print("=" * 60)
print("  Turbojet -- cruise design point")
print("=" * 60)

tj = jet.build_turbojet()
tj.set(M0=0.85, pi_c=12, T04=1500, mdot=25)
res = tj.solve()
res.summary(keys=["specific_thrust", "thrust", "TSFC", "far",
                  "thermal_eff", "propulsive_eff", "overall_eff", "M9"])

print("\n  Station stagnation conditions:")
print(jet.station_table(res))

print("\n" + "=" * 60)
print("  Two-spool turbofan (bypass ratio 5)")
print("=" * 60)

tf = jet.build_turbofan()
tf.set(M0=0.80, pi_f=1.6, pi_c=22, bypass=5, T04=1550, mdot=30)
rtf = tf.solve()
rtf.summary(keys=["specific_thrust", "thrust", "TSFC",
                  "thermal_eff", "propulsive_eff", "overall_eff"])
print("\n  The high-bypass fan trades specific thrust for a much lower TSFC")
print("  and higher propulsive efficiency than the bare turbojet above.")

print("\n" + "=" * 60)
print("  Sweep: compressor pressure ratio (turbojet)")
print("=" * 60)

tj2 = jet.build_turbojet()
tj2.set(M0=0.80, T04=1500)
sweep = tj2.sweep("pi_c", [6, 10, 15, 20, 25, 30, 40])
sweep.summary(outputs=["specific_thrust", "TSFC", "thermal_eff"])
print("\n  Higher pressure ratio lowers TSFC (better fuel economy), while")
print("  specific thrust peaks at a moderate pressure ratio.")

print("\n" + "=" * 60)
print("  Optimize: pressure ratio for maximum specific thrust")
print("=" * 60)

opt = jet.build_turbojet()
opt.set(M0=0.80, T04=1500)
best = opt.optimize("specific_thrust", {"pi_c": (4, 45)},
                    minimize=False, seed=1)
print(f"  Best compressor pressure ratio : {best.x['pi_c']:.2f}")
print(f"  Maximum specific thrust        : {best.fun:.1f} N per kg/s")

print("\n" + "=" * 60)
print("  Afterburning turbojet (reheat to 2000 K)")
print("=" * 60)

ab = jet.build_turbojet_ab()
ab.set(M0=0.90, pi_c=10, T04=1500, T07=2000, mdot=25)
rab = ab.solve()
rab.summary(keys=["specific_thrust", "thrust", "TSFC", "far_total",
                 "thermal_eff", "M9"])
print("\n  The afterburner adds fuel downstream of the turbine, raising")
print("  specific thrust sharply at the cost of a much higher TSFC.")

print("\n" + "=" * 60)
print("  Turboprop / turboshaft (shaft-power output)")
print("=" * 60)

tp = jet.build_turboprop()
tp.set(M0=0.50, pi_c=10, T04=1400, mdot=15)
rtp = tp.solve()
rtp.summary(keys=["shaft_power", "specific_power", "PSFC", "thermal_eff"])
print("\n  A turboprop extracts nearly all the exhaust energy as shaft power")
print("  instead of jet thrust, reported here as power-specific fuel burn.")

print("\n" + "=" * 60)
print("  Cycle diagrams (T-s and h-s / Mollier)")
print("=" * 60)

diag = jet.build_turbojet()
diag.set(M0=0.85, pi_c=12, T04=1500, mdot=25)
rdiag = diag.solve()
for kind, fname in [("Ts", "jet_cycle_Ts.png"), ("hs", "jet_cycle_hs.png")]:
    try:
        fig = jet.cycle_diagram(rdiag, kind=kind)
        fig.savefig(f"examples/{fname}", dpi=90, bbox_inches="tight")
        print(f"  Saved {kind} diagram to examples/{fname}")
    except Exception as exc:  # headless / no display: skip gracefully
        print(f"  Skipped {kind} diagram ({exc})")
