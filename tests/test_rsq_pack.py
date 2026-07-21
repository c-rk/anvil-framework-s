"""Anvil extended RSQ pack tests -- duct flow, pipe friction, heat, stress, cycles."""
import sys, os, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import anvil
from anvil.seed import seed
seed(force=True)
anvil.registry._rebuild_namespaces()
R = anvil.R

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


def close(a, b, tol=1e-3):
    if abs(float(a) - float(b)) > tol:
        raise AssertionError(f"{a} != {b} (tol={tol})")


print("\n=== Compressible duct flow ===")


@check("fanno: sonic point ratios are 1 at M=1")
def _():
    o = R.fanno_flow(M=1.0)
    close(o["T_Tstar"], 1.0); close(o["P_Pstar"], 1.0)
    close(o["fLD_max"], 0.0)


@check("fanno: 4fL*/D at M=2, gamma=1.4 matches tables (0.305)")
def _():
    close(R.fanno_flow(M=2.0)["fLD_max"], 0.305, tol=2e-3)


@check("rayleigh: T0/T0* = 1 at M=1")
def _():
    close(R.rayleigh_flow(M=1.0)["T0_T0star"], 1.0)


@check("mach angle: 30 degrees at M=2")
def _():
    close(R.mach_angle(M=2.0)["mu_deg"], 30.0)


print("\n=== Pipe friction ===")


@check("colebrook: laminar branch f = 64/Re below Re=2300")
def _():
    close(R.colebrook_friction(Re=1000.0)["f_darcy"], 0.064)


@check("colebrook and haaland agree within a few percent")
def _():
    fc = R.colebrook_friction(Re=1e5, rel_roughness=0.001)["f_darcy"]
    fh = R.haaland_friction(Re=1e5, rel_roughness=0.001)["f_darcy"]
    assert abs(fc - fh) / fc < 0.05, (fc, fh)


@check("pipe pressure drop: Darcy-Weisbach value")
def _():
    o = R.pipe_pressure_drop(f_darcy=0.02, L=100.0, D=0.1, rho=1000.0, V=2.0)
    close(float(o["dP"]), 40000.0, tol=1.0)


print("\n=== Heat transfer ===")


@check("LMTD: counter-flow log-mean of 80 and 50 is ~63.8")
def _():
    o = R.lmtd(T_hot_in=400, T_hot_out=350, T_cold_in=300, T_cold_out=320)
    close(float(o["LMTD"]), 63.83, tol=0.05)


@check("Biot: lumped assumption valid when Bi < 0.1")
def _():
    o = R.biot_number(h_conv=50.0, L_char=0.01, k_solid=200.0)
    assert o["lumped_valid"] is True
    close(o["Bi"], 0.0025)


@check("lumped capacitance: decays toward T_inf")
def _():
    o = R.lumped_capacitance(T0=500, T_inf=300, t=60, h_conv=50,
                             A_surf=0.1, rho=8000, V_vol=0.001, cp=450)
    close(float(o["tau"]), 720.0, tol=1.0)
    assert 300 < float(o["T_t"]) < 500


print("\n=== Stress ===")


@check("principal stresses: Mohr's circle values")
def _():
    o = R.principal_stresses_2d(sigma_x=100e6, sigma_y=40e6, tau_xy=30e6)
    close(float(o["sigma_1"]), 112.4264e6, tol=1e3)
    close(float(o["tau_max"]), 42.4264e6, tol=1e3)
    close(o["theta_p_deg"], 22.5, tol=0.1)


@check("von Mises: uniaxial stress recovers the axial value")
def _():
    close(float(R.von_mises_stress(sigma_x=250e6)["sigma_vm"]), 250e6, tol=1.0)


@check("torsion: solid shaft polar moment and shear")
def _():
    import numpy as np
    o = R.torsion_circular_shaft(torque=1000.0, d_outer=0.05, L=1.0, G=80e9)
    close(o["J"], np.pi * 0.05 ** 4 / 32.0, tol=1e-12)
    assert float(o["tau_max"]) > 0


print("\n=== Cycles ===")


@check("Carnot: efficiency 1 - Tc/Th")
def _():
    close(R.carnot_efficiency(T_hot=800, T_cold=300)["eta_carnot"], 0.625)


@check("Brayton: ideal efficiency 1 - rp^-((g-1)/g)")
def _():
    close(R.brayton_ideal(pressure_ratio=15)["eta_thermal"], 0.5387, tol=1e-3)


@check("skin friction: switches laminar/turbulent at Re=5e5")
def _():
    assert R.skin_friction_flat_plate(Re_L=1e4)["regime"] == "laminar"
    assert R.skin_friction_flat_plate(Re_L=1e6)["regime"] == "turbulent"


print("\n=== Curve fitting ===")


@check("linear regression: recovers slope and intercept")
def _():
    o = R.linear_regression(x_data=[1, 2, 3, 4, 5], y_data=[3, 5, 7, 9, 11])
    close(o["slope"], 2.0, tol=1e-6); close(o["intercept"], 1.0, tol=1e-6)
    close(o["r_squared"], 1.0, tol=1e-9)


@check("poly fit: recovers a quadratic exactly")
def _():
    o = R.poly_fit(x_data=[0, 1, 2, 3, 4], y_data=[1, 2, 5, 10, 17], degree=2)
    c = o["coeffs"]
    close(c[0], 1.0, tol=1e-6); close(c[2], 1.0, tol=1e-6)
    close(o["r_squared"], 1.0, tol=1e-9)


@check("power fit: y = 2 x^2")
def _():
    o = R.power_fit(x_data=[1, 2, 3, 4], y_data=[2, 8, 18, 32])
    close(o["a"], 2.0, tol=1e-6); close(o["b"], 2.0, tol=1e-6)


@check("exp fit: y = e^x")
def _():
    o = R.exp_fit(x_data=[0, 1, 2, 3], y_data=[1, 2.71828, 7.38906, 20.0855])
    close(o["a"], 1.0, tol=1e-3); close(o["b"], 1.0, tol=1e-3)


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
