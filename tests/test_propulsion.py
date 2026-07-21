"""Anvil gas-turbine cycle tests -- components, engines, sweeps, invariants."""
import sys, os, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from anvil import propulsion as jet

passed = failed = skipped = 0
errors = []


def check(name, skip=False):
    def dec(fn):
        global passed, failed, skipped
        if skip:
            print(f"  SKIP  {name}"); skipped += 1; return
        try:
            fn(); print(f"  PASS  {name}"); passed += 1
        except Exception as e:
            print(f"  FAIL  {name}: {e}"); traceback.print_exc()
            failed += 1; errors.append((name, e))
    return dec


def sif(q):
    """SI float of a Quantity or plain number."""
    return float(q._si_value) if hasattr(q, "_si_value") else float(q)


print("\n=== Components ===")


@check("compressor: work matches enthalpy rise")
def _():
    out = jet.compressor(T02=300.0, P02=101325.0, pi_c=10.0,
                         eta_c=0.87, cp_c=1004.5)
    T03 = sif(out["T03"]); w_c = sif(out["w_c"])
    close = abs(w_c - 1004.5 * (T03 - 300.0))
    assert close < 1e-6, close
    assert sif(out["P03"]) == 101325.0 * 10.0


@check("combustor: fuel-air ratio in a sane range")
def _():
    out = jet.combustor(T03=650.0, P03=1.0e6, T04=1500.0)
    far = float(out["far"])
    assert 0.01 < far < 0.05, far


@check("turbine: work balance drives the compressor")
def _():
    out = jet.turbine(T04=1500.0, P04=1.0e6, w_c=3.0e5, far=0.025,
                      eta_t=0.89, eta_m=0.99, cp_h=1148.0)
    w_t = sif(out["w_t"])
    # turbine work per unit turbine mass * (1+far) * eta_m == compressor work
    assert abs(w_t * 0.99 * 1.025 - 3.0e5) < 1e-3


@check("nozzle: chokes at high pressure ratio")
def _():
    out = jet.nozzle(T05=1100.0, P05=4.0e5, P_amb=1.0e5)
    assert out["choked"] is True
    assert abs(float(out["M9"]) - 1.0) < 1e-9


@check("nozzle: unchoked at low pressure ratio")
def _():
    out = jet.nozzle(T05=1100.0, P05=1.2e5, P_amb=1.0e5)
    assert out["choked"] is False
    assert float(out["M9"]) < 1.0


print("\n=== Turbojet ===")


@check("turbojet solves and gives sane cruise numbers")
def _():
    r = jet.build_turbojet()
    r.set(M0=0.85, pi_c=12, T04=1500, mdot=25)
    res = r.solve()
    Fs = sif(res["specific_thrust"]); tsfc = float(res["TSFC"])
    assert 300 < Fs < 1200, Fs
    assert 1e-5 < tsfc < 6e-5, tsfc


@check("turbojet: efficiencies are bounded in [0, 1]")
def _():
    res = jet.build_turbojet().solve()  # static, M0=0
    for k in ("thermal_eff", "propulsive_eff", "overall_eff"):
        v = float(res[k])
        assert 0.0 <= v <= 1.0, (k, v)
    # overall == thermal * propulsive
    assert abs(float(res["overall_eff"])
               - float(res["thermal_eff"]) * float(res["propulsive_eff"])) < 1e-9


@check("turbojet: TSFC falls as pressure ratio rises")
def _():
    tj = jet.build_turbojet(); tj.set(M0=0.8, T04=1500)
    sw = tj.sweep("pi_c", [8, 16, 32])
    tsfc = sw["TSFC"]
    assert tsfc[0] > tsfc[1] > tsfc[2], list(tsfc)


@check("turbojet: optimum pressure ratio maximizes specific thrust")
def _():
    tj = jet.build_turbojet(); tj.set(M0=0.8, T04=1500)
    opt = tj.optimize("specific_thrust", {"pi_c": (4, 45)},
                      minimize=False, seed=1)
    assert opt.success
    assert 5 < opt.x["pi_c"] < 15, opt.x


print("\n=== Turbofan / afterburner / turboprop ===")


@check("turbofan: higher propulsive efficiency than turbojet")
def _():
    tj = jet.build_turbojet(); tj.set(M0=0.8, T04=1500)
    tf = jet.build_turbofan(); tf.set(M0=0.8, T04=1500, bypass=5)
    ep_tj = float(tj.solve()["propulsive_eff"])
    ep_tf = float(tf.solve()["propulsive_eff"])
    assert ep_tf > ep_tj, (ep_tf, ep_tj)


@check("afterburner: adds fuel and raises specific thrust")
def _():
    dry = jet.build_turbojet(); dry.set(M0=0.9, pi_c=10, T04=1400)
    wet = jet.build_turbojet_ab(); wet.set(M0=0.9, pi_c=10, T04=1400, T07=2000)
    rd = dry.solve(); rw = wet.solve()
    assert float(rw["far_total"]) > float(rd["far"])
    assert sif(rw["specific_thrust"]) > sif(rd["specific_thrust"])


@check("turboprop: delivers positive shaft power and thermal efficiency")
def _():
    r = jet.build_turboprop(); r.set(M0=0.5)
    res = r.solve()
    assert sif(res["shaft_power"]) > 0
    assert 0.0 < float(res["thermal_eff"]) < 1.0


print("\n=== Post-processing ===")


@check("station table lists the expected stations")
def _():
    res = jet.build_turbojet().solve()
    rows = jet.station_table(res, as_text=False)
    stations = {r["station"] for r in rows}
    assert {"0", "2", "3", "4", "5", "9"} <= stations, stations


@check("cycle diagram builds a figure (matplotlib)", skip=False)
def _():
    try:
        import matplotlib
        matplotlib.use("Agg")
    except ImportError:
        print("    (matplotlib not installed -- skipping figure assertion)")
        return
    res = jet.build_turbojet().solve()
    fig = jet.cycle_diagram(res, kind="Ts")
    assert fig is not None
    fig2 = jet.cycle_diagram(res, kind="hs")
    assert fig2 is not None


# ============================================================
print(f"\n{'=' * 50}")
print(f"Results: {passed} passed, {failed} failed" + (f", {skipped} skipped" if skipped else ""))
if errors:
    print("\nFailed:")
    for n, e in errors:
        print(f"  {n}: {e}")
print(f"{'=' * 50}")
if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
