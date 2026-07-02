"""
System-builder backend tests (script-style): `python tests/test_system_builder.py`.

Exercises anvil_server.app.builder_routes.solve_system directly (no HTTP), the
function the POST + WS endpoints both call. Covers:

  1. A COUPLED 2-relation system that requires gauss_seidel: asserts the chosen
     method, history length >= 2, finite & generally-decreasing residuals, and
     correct converged values.
  2. A simple FORWARD system (one relation, all inputs provided): solves with an
     empty history and correct results.
  3. An unknown relation name -> a clean BuilderError (not a crash / 500).

Temp RSQs are registered in the registry (so sys.use(name) can find them) and
removed again in a finally block so the registry is left clean.
"""
import math
import os
import sys

# Ensure the anvil package and the server app are importable when run script-style.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, _ROOT)

import anvil

from anvil_server.app.builder_routes import solve_system, BuilderError


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


# --- temp relations -------------------------------------------------------- #
# Coupled cycle: x = 1 + 0.5*y, y = 2 + 0.3*x  (contraction -> gauss_seidel).
def _sb_rel_x(y):
    return {"x": 1.0 + 0.5 * y}


def _sb_rel_y(x):
    return {"y": 2.0 + 0.3 * x}


# Forward (acyclic): F = m * a.
def _sb_rel_force(m, a):
    return {"F": m * a}


TEMP_NAMES = ["_sb_rel_x", "_sb_rel_y", "_sb_rel_force"]


def _register_temps():
    anvil.registry.register(_sb_rel_x, name="_sb_rel_x",
                            _suppress_overwrite_warning=True)
    anvil.registry.register(_sb_rel_y, name="_sb_rel_y",
                            _suppress_overwrite_warning=True)
    anvil.registry.register(_sb_rel_force, name="_sb_rel_force",
                            _suppress_overwrite_warning=True)


def _cleanup_temps():
    for name in TEMP_NAMES:
        try:
            anvil.registry.remove(name)
        except Exception:
            pass


def run():
    _register_temps()
    try:
        _run_tests()
    finally:
        _cleanup_temps()

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed


def _run_tests():
    # 1. Coupled system requiring gauss_seidel ----------------------------- #
    coupled_req = {
        "name": "coupled_web",
        "quantities": [
            {"name": "x", "value": 1.0},
            {"name": "y", "value": 1.0},
        ],
        "relations": ["_sb_rel_x", "_sb_rel_y"],
    }
    resp = solve_system(coupled_req)

    check("coupled method is gauss_seidel", resp["method"] == "gauss_seidel")

    hist = resp["history"]
    check("coupled history length >= 2", len(hist) >= 2)

    residuals = [h["residual"] for h in hist]
    check("coupled residuals finite", all(math.isfinite(r) for r in residuals))

    indices = [h["iter"] for h in hist]
    check("coupled iter indices count up from 0",
          indices == list(range(len(indices))))

    decreasing_steps = sum(1 for a, b in zip(residuals, residuals[1:]) if b <= a)
    check("coupled residuals generally decreasing",
          residuals[-1] < residuals[0]
          and decreasing_steps >= (len(residuals) - 1) // 2)

    # Exact solution of x = 1 + 0.5y, y = 2 + 0.3x.
    x_exact = (1.0 + 0.5 * 2.0) / (1.0 - 0.5 * 0.3)
    y_exact = 2.0 + 0.3 * x_exact
    check("coupled x value correct",
          abs(resp["results"]["x"]["value"] - x_exact) < 1e-4)
    check("coupled y value correct",
          abs(resp["results"]["y"]["value"] - y_exact) < 1e-4)
    check("coupled x role is output", resp["results"]["x"]["role"] == "output")
    check("coupled y role is output", resp["results"]["y"]["role"] == "output")
    check("coupled outputs list", resp["outputs"] == ["x", "y"])

    # 2. Forward system ---------------------------------------------------- #
    fwd_req = {
        "name": "forward_web",
        "quantities": [
            {"name": "m", "value": 10.0, "unit": "kg"},
            {"name": "a", "value": 3.0, "unit": "m/s^2"},
        ],
        "relations": ["_sb_rel_force"],
    }
    fresp = solve_system(fwd_req)
    check("forward method is forward", fresp["method"] == "forward")
    check("forward history empty", fresp["history"] == [])
    check("forward F value correct (m*a=30)",
          abs(fresp["results"]["F"]["value"] - 30.0) < 1e-9)
    check("forward F role is output", fresp["results"]["F"]["role"] == "output")
    check("forward m role is input", fresp["results"]["m"]["role"] == "input")
    check("forward inputs are m,a", fresp["inputs"] == ["a", "m"])

    # 3. Unknown relation -> clean BuilderError ---------------------------- #
    crashed = False
    clean = False
    try:
        solve_system({
            "name": "bad",
            "quantities": [{"name": "x", "value": 1.0}],
            "relations": ["_does_not_exist_rsq_"],
        })
    except BuilderError as exc:
        clean = True
        check("unknown relation message mentions name",
              "_does_not_exist_rsq_" in str(exc))
    except Exception:
        crashed = True
    check("unknown relation -> clean BuilderError (no crash)",
          clean and not crashed)


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
