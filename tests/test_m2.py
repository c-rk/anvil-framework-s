"""
M2 tests: parallel sweep executor + Design-of-Experiments (DOE) module.

Script-style (run directly): `python tests/test_m2.py`.

Covers:
  1. latin_hypercube / sobol produce exactly n samples within bounds.
  2. full_factorial size == product of level counts.
  3. A parallel sweep (parallel=2) matches the serial sweep exactly.
  4. run_doe returns the expected number of rows (serial and parallel).
  5. set_backend / get_backend round-trip and validation.
  6. Unpicklable System falls back to threads (no crash) under process backend.

Module-level relation functions are used so System copies are picklable for
the default ProcessPoolExecutor backend (required under Windows 'spawn').
"""
import sys
import warnings

import numpy as np
import anvil
from anvil import doe


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


# --- module-level (picklable) relations ------------------------------------
def f_force(m, a):
    return {"F": m * a}


def f_power(F, v):
    return {"P": F * v}


def _make_system():
    s = anvil.system("m2_sys")
    s.add("m", 10.0, "kg")
    s.add("a", 3.0, "m/s^2")
    s.add("v", 2.0, "m/s")
    s.use(f_force)
    s.use(f_power)
    return s


def run():
    warnings.simplefilter("ignore")

    # --- 1. LHS / Sobol sample count + bounds ------------------------------
    bounds = {"m": (1.0, 20.0), "a": (0.5, 5.0)}

    lhs = doe.latin_hypercube(bounds, n=16, seed=0)
    check("LHS returns n=16 samples", len(lhs) == 16)
    check("LHS samples have the right keys",
          all(set(s.keys()) == {"m", "a"} for s in lhs))
    check("LHS samples within bounds",
          all(1.0 <= s["m"] <= 20.0 and 0.5 <= s["a"] <= 5.0 for s in lhs))
    # reproducible with same seed
    lhs2 = doe.latin_hypercube(bounds, n=16, seed=0)
    check("LHS reproducible with seed",
          all(abs(a["m"] - b["m"]) < 1e-12 and abs(a["a"] - b["a"]) < 1e-12
              for a, b in zip(lhs, lhs2)))

    sob = doe.sobol(bounds, n=8, seed=1)
    check("Sobol returns n=8 samples", len(sob) == 8)
    check("Sobol samples within bounds",
          all(1.0 <= s["m"] <= 20.0 and 0.5 <= s["a"] <= 5.0 for s in sob))

    # --- 2. full_factorial size --------------------------------------------
    levels = {"m": [1.0, 2.0, 3.0], "a": [0.5, 1.0], "v": [10.0, 20.0, 30.0, 40.0]}
    ff = doe.full_factorial(levels)
    check("full_factorial size == product of level counts (3*2*4=24)",
          len(ff) == 24)
    check("full_factorial covers all combos (unique rows)",
          len({(r["m"], r["a"], r["v"]) for r in ff}) == 24)

    # --- 3. parallel sweep == serial sweep ---------------------------------
    s_serial = _make_system()
    sweep_vals = np.linspace(1.0, 10.0, 6)
    res_serial = s_serial.sweep("m", sweep_vals)

    s_par = _make_system()
    res_par = s_par.sweep("m", sweep_vals, parallel=2)

    F_serial = res_serial["F"]
    F_par = res_par["F"]
    P_serial = res_serial["P"]
    P_par = res_par["P"]
    check("parallel sweep F matches serial",
          np.allclose(F_serial, F_par, rtol=1e-12, atol=1e-12))
    check("parallel sweep P matches serial",
          np.allclose(P_serial, P_par, rtol=1e-12, atol=1e-12))
    check("parallel sweep preserves param order",
          np.allclose(res_serial["m"], res_par["m"]))

    # --- 4. run_doe row counts ---------------------------------------------
    sysd = _make_system()
    samples = doe.latin_hypercube({"m": (1.0, 20.0), "a": (0.5, 5.0)},
                                  n=10, seed=2)
    dres = doe.run_doe(sysd, samples, outputs=["F", "P"], parallel=1)
    check("run_doe (serial) returns 10 rows", len(dres) == 10)
    check("run_doe collects requested outputs", set(dres.outputs) == {"F", "P"})
    check("run_doe F column has 10 entries", len(dres["F"]) == 10)
    # F = m * a (in SI); spot-check first row
    check("run_doe F == m*a (row 0)",
          abs(dres["F"][0] - samples[0]["m"] * samples[0]["a"]) < 1e-9)

    sysd2 = _make_system()
    dres_par = doe.run_doe(sysd2, samples, outputs=["F", "P"], parallel=2)
    check("run_doe (parallel) returns 10 rows", len(dres_par) == 10)
    check("run_doe parallel F matches serial",
          np.allclose(dres["F"], dres_par["F"], rtol=1e-12, atol=1e-12))

    ff_doe = doe.run_doe(_make_system(), ff, outputs=["F"])
    check("run_doe over full_factorial returns 24 rows", len(ff_doe) == 24)

    # --- 5. backend helpers ------------------------------------------------
    orig = anvil.get_backend()
    anvil.set_backend("thread")
    check("set_backend('thread') round-trips", anvil.get_backend() == "thread")
    anvil.set_backend("serial")
    check("set_backend('serial') round-trips", anvil.get_backend() == "serial")
    try:
        anvil.set_backend("bogus")
        bad = False
    except ValueError:
        bad = True
    check("set_backend rejects unknown backend", bad)
    anvil.set_backend(orig)

    # --- 6. unpicklable system falls back to threads (no crash) ------------
    def local_relation(x):  # closure/local -> not picklable
        return {"y": x * 2.0}

    sloc = anvil.system("local_sys")
    sloc.add("x", 1.0, "")
    sloc.use(local_relation)
    try:
        # default backend is 'process'; this must NOT crash, falling back to threads
        anvil.set_backend("process")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res_loc = sloc.sweep("x", [1.0, 2.0, 3.0, 4.0], parallel=2)
        ok = np.allclose(res_loc["y"], [2.0, 4.0, 6.0, 8.0])
    except Exception:
        ok = False
    finally:
        anvil.set_backend(orig)
    check("unpicklable system: parallel sweep falls back gracefully", ok)

    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
