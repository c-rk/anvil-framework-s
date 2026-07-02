"""
WS-residuals tests: the optional per-iteration ``on_iter`` callback on
System.solve() that powers live residual streaming.

Script-style (run directly): `python tests/test_ws_residuals.py`.

Covers:
  1. A COUPLED System (gauss_seidel) calls on_iter at least twice, with finite,
     generally-decreasing residuals and iter indices counting up from 0.
  2. A plain FORWARD solve with on_iter set still returns correct results and
     never fires the callback (full backward compatibility).
"""
import math
import sys

import anvil


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


# --- module-level relations forming a coupled cycle -------------------------
# x and y are mutually dependent: x = 1 + 0.5*y, y = 2 + 0.3*x.
# This is a contraction (|0.5*0.3| < 1) so gauss_seidel converges, and because
# x feeds y and y feeds x the dependency graph has a cycle -> iterative solve.
def rel_x(y):
    return {"x": 1.0 + 0.5 * y}


def rel_y(x):
    return {"y": 2.0 + 0.3 * x}


def _coupled_system():
    s = anvil.system("coupled")
    # Non-zero initial guesses so the first residual is meaningful and the
    # solver takes several iterations to converge (zeros would make the very
    # first relative-change residual 0 and "converge" in one step).
    s.add("x", 1.0, "")
    s.add("y", 1.0, "")
    s.use(rel_x)
    s.use(rel_y)
    return s


# --- module-level forward (acyclic) relation --------------------------------
def rel_force(m, a):
    return {"F": m * a}


def _forward_system():
    s = anvil.system("forward")
    s.add("m", 10.0, "kg")
    s.add("a", 3.0, "m/s^2")
    s.use(rel_force)
    return s


def run():
    # 1. Coupled system: callback fires repeatedly with decreasing residuals.
    s = _coupled_system()
    s.validate()
    check("coupled system is iterative (has_cycles)", s._has_cycles)

    iters = []
    res = s.solve(on_iter=lambda info: iters.append(info))

    check("on_iter fired >= 2 times", len(iters) >= 2)

    residuals = [it["residual"] for it in iters]
    check("all residuals finite", all(math.isfinite(r) for r in residuals))

    indices = [it["iter"] for it in iters]
    check("iter indices count up from 0",
          indices == list(range(len(indices))))

    # Generally decreasing: the final residual is below the first, and the
    # majority of step-to-step changes are non-increasing.
    decreasing_steps = sum(
        1 for a, b in zip(residuals, residuals[1:]) if b <= a
    )
    check("residuals generally decreasing",
          residuals[-1] < residuals[0]
          and decreasing_steps >= (len(residuals) - 1) // 2)

    # Each frame carries the live variable snapshot.
    check("iteration carries variable snapshot",
          all("x" in it["variables"] and "y" in it["variables"] for it in iters))

    # Solution is correct: solve x = 1 + 0.5y, y = 2 + 0.3x  ->  x≈2.4706, y≈2.7412
    x_exact = (1.0 + 0.5 * 2.0) / (1.0 - 0.5 * 0.3)
    y_exact = 2.0 + 0.3 * x_exact
    check("coupled solution x correct",
          abs(float(res["x"].value) - x_exact) < 1e-4)
    check("coupled solution y correct",
          abs(float(res["y"].value) - y_exact) < 1e-4)

    # 2. Forward solve with on_iter set: callback never fires, result correct.
    fwd_iters = []
    f = _forward_system()
    fres = f.solve(on_iter=lambda info: fwd_iters.append(info))
    check("forward solve does not fire on_iter", len(fwd_iters) == 0)
    check("forward solve method is 'forward'", fres.method == "forward")
    check("forward result correct (F = m*a = 30)",
          abs(float(fres["F"].value) - 30.0) < 1e-9)

    # 3. Backward compatibility: solve() with no on_iter still works on coupled.
    s2 = _coupled_system()
    r2 = s2.solve()
    check("solve() without on_iter still converges",
          abs(float(r2["x"].value) - x_exact) < 1e-4)

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
