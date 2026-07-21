"""Anvil fundamental-physics RSQ tests -- mechanics, EM, optics, waves, relativity, quantum.

Values checked against textbook / first-principles results. These RSQs were authored via
docs/RSQ_AUTHORING_PROMPT.md and validated before seeding.
"""
import sys, os, math, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import anvil
from anvil.seed import seed
seed(force=True)
anvil.registry._rebuild_namespaces()
R = anvil.R

passed = failed = skipped = 0
errors = []

C_LIGHT = 2.99792458e8


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


def rel(a, b, rtol=1e-3):
    if abs(float(a) - float(b)) > abs(float(b)) * rtol:
        raise AssertionError(f"{a} != {b} (rtol={rtol})")


print("\n=== Mechanics ===")


@check("kinetic_energy: 0.5 m v^2")
def _():
    close(R.kinetic_energy(m=2, v=3)["KE"], 9.0)


@check("newton_gravitation: unit masses at 1 m give G")
def _():
    rel(R.newton_gravitation(m1=1, m2=1, r=1)["F_grav"], 6.674e-11)


@check("projectile_range: 45 deg maximises range")
def _():
    o = R.projectile_range(v0=10, angle_deg=45)
    rel(o["range"], 10.0**2 / 9.81)  # sin(90)=1


@check("pendulum_period: 1 m pendulum ~2.006 s")
def _():
    rel(R.pendulum_period(L=1)["period"], 2.0 * math.pi * math.sqrt(1 / 9.81))


print("\n=== Electromagnetism ===")


@check("coulomb_force: two 1 uC at 0.1 m")
def _():
    rel(R.coulomb_force(q1=1e-6, q2=1e-6, r=0.1)["F_coulomb"], 0.898755)


@check("parallel_plate_capacitor_energy: 0.5 C V^2")
def _():
    eps0 = 8.8541878128e-12
    expect = 0.5 * (eps0 * 1.0 / 1e-3) * 100 ** 2
    rel(R.parallel_plate_capacitor_energy(A=1, d=1e-3, V=100)["U_stored"], expect)


@check("lorentz_force_magnitude: F = qvB at 90 deg")
def _():
    q = 1.602176634e-19
    rel(R.lorentz_force_magnitude(q=q, v=1e6, B=0.5)["F_lorentz"], q * 1e6 * 0.5)


print("\n=== Optics ===")


@check("snell_refraction_angle: 30 deg air into n=1.5 glass")
def _():
    o = R.snell_refraction_angle(n1=1, n2=1.5, theta1_deg=30)
    close(o["theta2_deg"], 19.4712, tol=1e-3)
    close(o["total_internal_reflection"], 0.0)


@check("snell_refraction_angle: TIR flagged past critical angle")
def _():
    o = R.snell_refraction_angle(n1=1.5, n2=1.0, theta1_deg=60)
    close(o["total_internal_reflection"], 1.0)


@check("thin_lens_image_distance: f=0.1, d_o=0.3 -> 0.15")
def _():
    close(R.thin_lens_image_distance(f=0.1, d_o=0.3)["d_i"], 0.15)


@check("thin_lens_image_distance: d_o=f gives image at infinity (no crash)")
def _():
    d_i = float(R.thin_lens_image_distance(f=0.1, d_o=0.1)["d_i"])
    assert math.isinf(d_i), f"expected inf, got {d_i}"


@check("photon_energy_frequency: E = h f")
def _():
    rel(R.photon_energy_frequency(f=5e14)["E_photon"], 6.62607015e-34 * 5e14)


print("\n=== Waves ===")


@check("wave_speed: v = f lambda -> 340 m/s")
def _():
    close(R.wave_speed(frequency=100, wavelength=3.4)["speed"], 340.0)


@check("relativistic_doppler_shift: approach at 0.1c blueshifts")
def _():
    o = R.relativistic_doppler_shift(f_src=1e9, v_radial=0.1 * C_LIGHT)
    rel(o["f_obs"], 1e9 * math.sqrt((1 + 0.1) / (1 - 0.1)))


print("\n=== Relativity ===")


@check("lorentz_factor: 0.6c -> gamma 1.25")
def _():
    close(R.lorentz_factor(v=0.6 * C_LIGHT)["gamma"], 1.25)


@check("mass_energy_equivalence: 1 kg -> c^2 joules")
def _():
    rel(R.mass_energy_equivalence(m=1)["E_rest"], C_LIGHT ** 2)


print("\n=== Quantum ===")


@check("de_broglie_wavelength: lambda = h/p")
def _():
    rel(R.de_broglie_wavelength(p=1e-24)["wavelength"], 6.62607015e-34 / 1e-24)


@check("wien_peak_wavelength: sun ~5778 K peaks near 500 nm")
def _():
    o = R.wien_peak_wavelength(T=5778)["lambda_peak"]
    rel(o, 2.897771955e-3 / 5778)
    assert 4.5e-7 < float(o) < 5.5e-7, "solar peak should be in visible"


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
