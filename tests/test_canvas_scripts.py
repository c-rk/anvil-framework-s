"""Tests for the canvas <-> python-script bridge (anvil_server/app/canvas_routes.py).

Script-style: `python tests/test_canvas_scripts.py`.
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from anvil_server.app.canvas_routes import (  # noqa: E402
    CanvasBlock,
    CanvasGraph,
    CanvasQuantity,
    CanvasRelation,
    parse_script,
    serialize_canvas,
)
from anvil_server.app.builder_routes import BuilderError, build_system  # noqa: E402

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


# --- 1. round-trip ----------------------------------------------------------
graph = CanvasGraph(
    name="rt_test",
    description="round-trip test canvas",
    quantities=[
        CanvasQuantity(name="mach_in", value=3.0, unit="", pos={"x": 80, "y": 80}),
        CanvasQuantity(name="gamma", value=1.4, unit="", pos={"x": 80, "y": 200}),
    ],
    relations=[
        CanvasRelation(name="normal_shock", pos={"x": 380, "y": 100},
                       renames={"M1": "mach_in"}),
    ],
    blocks=[
        CanvasBlock(id="a1", kind="arith", pos={"x": 600, "y": 80},
                    config={"op": "multiply", "outName": "M1_x2",
                            "portSources": {}, "a": 1.0, "b": 1.0,
                            "expression": ""}),
        CanvasBlock(id="sweep_1", kind="sweep", pos={"x": 600, "y": 240},
                    config={"param": "mach_in", "min": 1.5, "max": 4.0, "steps": 12,
                            "outputs": ["M2", "P2_P1"]}),
    ],
)

script = serialize_canvas(graph)
check("serializer emits marker", "# %% anvil-canvas v1" in script)
check("serializer emits meta", "# %% anvil-canvas-meta" in script)
check("serializer emits sweep code", "sys.sweep('mach_in', np.linspace(" in script)
check("serializer emits map renames", "map={'M1': 'mach_in'}" in script)

g2, warns = parse_script(script)
check("round-trip name", g2.name == "rt_test")
check("round-trip quantities", {q.name for q in g2.quantities} == {"mach_in", "gamma"})
check("round-trip values", abs(g2.quantities[0].value - 3.0) < 1e-12)
check("round-trip relations", [r.name for r in g2.relations] == ["normal_shock"])
check("round-trip renames", g2.relations[0].renames == {"M1": "mach_in"})
check("round-trip positions", g2.quantities[0].pos == {"x": 80, "y": 80})
check("round-trip blocks", {b.id for b in g2.blocks} == {"a1", "sweep_1"})
sw = next(b for b in g2.blocks if b.kind == "sweep")
check("round-trip sweep config", sw.config["steps"] == 12 and sw.config["outputs"] == ["M2", "P2_P1"])
check("round-trip no warnings", warns == [])

# --- 2. generated script runs standalone ------------------------------------
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, "rt_test.py")
    with open(p, "w", encoding="utf-8") as f:
        f.write(script)
    r = subprocess.run([sys.executable, p], capture_output=True, text=True,
                       timeout=180)
    if r.returncode != 0:
        print("  stderr:", r.stderr[-400:])
    check("generated script runs standalone (exit 0)", r.returncode == 0)

# --- 3. parse of real example scripts (canvas-ready ones import fully) -------
root = os.path.join(os.path.dirname(__file__), "..", "examples")
# fname -> (min quantities, min relations)
expectations = {
    "ex01_rocket_nozzle.py": (7, 1),   # anvil.S.x.copy() + .set(kwargs)
    "ex02_heat_exchanger.py": (9, 4),  # coupled, registry relations
    "ex03_orbital_transfer.py": (5, 2),
    "ex04_beam_analysis.py": (4, 1),   # Q() arithmetic bindings (I = b*h^3/12)
    "ex05_wind_tunnel.py": (7, 10),    # map= renames everywhere
}
for fname, (min_q, min_r) in expectations.items():
    path = os.path.join(root, fname)
    if not os.path.exists(path):
        check(f"example {fname} exists", False)
        continue
    with open(path, encoding="utf-8") as f:
        src = f.read()
    try:
        g, w = parse_script(src)
        ok = len(g.quantities) >= min_q and len(g.relations) >= min_r
        check(f"parse {fname} ({len(g.quantities)}q/{len(g.relations)}r)", ok)
        if not ok:
            for x in w:
                print("        warn:", x)
    except ValueError:
        check(f"parse {fname}", False)

# map= renames survive example import
with open(os.path.join(root, "ex05_wind_tunnel.py"), encoding="utf-8") as f:
    g5, _ = parse_script(f.read())
ns = next(r for r in g5.relations if r.name == "normal_shock")
check("ex05 map= renames imported", ns.renames == {"M1": "M_test"})

# --- 4. security: parsing never executes code --------------------------------
with tempfile.TemporaryDirectory() as td:
    sentinel = os.path.join(td, "pwned.txt")
    evil = (
        "import os\n"
        f"os.system('echo x > {sentinel}')\n"
        f"open({sentinel!r}, 'w').write('x')\n"
        "sys = __import__('anvil').system('evil')\n"
    )
    try:
        g, w = parse_script(evil)
        parsed_ok = True
    except ValueError:
        parsed_ok = True  # rejecting is fine too; executing is not
    check("malicious script parsed without execution",
          parsed_ok and not os.path.exists(sentinel))

# --- 5. type-S Systems are first-class canvas nodes --------------------------
from anvil_server.app.builder_routes import solve_system  # noqa: E402

try:
    out = solve_system({
        "name": "t",
        "quantities": [
            {"name": "P0", "value": 20e6, "unit": "Pa"},
            {"name": "T0", "value": 3500, "unit": "K"},
            {"name": "gamma", "value": 1.2},
            {"name": "R_gas", "value": 520},
            {"name": "A_throat", "value": 0.005, "unit": "m^2"},
            {"name": "A_exit", "value": 0.08, "unit": "m^2"},
            {"name": "P_amb", "value": 0, "unit": "Pa"},
        ],
        "relations": ["rocket_nozzle"],
    })
    thrust = out["results"]["thrust"]["value"]
    check("type-S system solves on canvas", abs(thrust - 179708) < 500)
except Exception as e:  # noqa: BLE001
    print("  error:", e)
    check("type-S system solves on canvas", False)

# stored Quantities still rejected with a clean error
try:
    build_system({"name": "t", "quantities": [], "relations": ["g0"]})
    check("type-Q relation rejected", False)
except BuilderError as e:
    check("type-Q relation rejected", "stored Quantity" in str(e))
except Exception:
    check("type-Q relation rejected", False)

# --- 6. per-relation map= renames in the solve request -----------------------
try:
    out = solve_system({
        "quantities": [{"name": "M_test", "value": 2.5}, {"name": "gamma", "value": 1.4}],
        "relations": [{"name": "normal_shock", "map": {"M1": "M_test"}}],
    })
    check("map renames solve", abs(out["results"]["M2"]["value"] - 0.513) < 0.01)
except Exception as e:  # noqa: BLE001
    print("  error:", e)
    check("map renames solve", False)

# --- 7. coupled system imported from example solves iteratively --------------
try:
    with open(os.path.join(root, "ex02_heat_exchanger.py"), encoding="utf-8") as f:
        gx, _ = parse_script(f.read())
    out = solve_system({
        "quantities": [q.model_dump(exclude={"pos"}) for q in gx.quantities],
        "relations": [{"name": r.name, "map": r.renames} for r in gx.relations],
    })
    ok = (out["method"] == "gauss_seidel"
          and abs(out["results"]["effectiveness"]["value"] - 0.8056) < 0.01)
    check("coupled ex02 canvas solve (gauss_seidel)", ok)
except Exception as e:  # noqa: BLE001
    print("  error:", e)
    check("coupled ex02 canvas solve (gauss_seidel)", False)


# --- 8. loop unrolling, f-string names, warning relevance --------------------
loop_script = """
import anvil
sys = anvil.system("loopy")
for i in range(3):
    sys.add(f"m_{i}", i * 10.0 + 5)
for g in [1.2, 1.4]:
    sys.add(f"gamma_{g}", g)
sys.use("normal_shock", map={"M1": "m_0"})
for msg in compute_report():
    print(msg)
result = sys.solve()
"""
gl, wl = parse_script(loop_script)
check("loop unrolled to quantities",
      {q.name for q in gl.quantities} >= {"m_0", "m_1", "m_2"})
check("f-string names resolved",
      any(q.name == "gamma_1.2" for q in gl.quantities))
check("unrolled values correct",
      next(q for q in gl.quantities if q.name == "m_2").value == 25.0)
check("irrelevant loops are silent", wl == [])

unrollable = """
import anvil
sys = anvil.system("x")
for fname in load_files():
    sys.add(fname, 1.0)
"""
gu, wu = parse_script(unrollable)
check("non-constant sys loop warns",
      any("could not be unrolled" in w for w in wu))

print("\n" + "=" * 50)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 50)
if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
