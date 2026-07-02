"""Tier-B sandbox tests (script-style): `python tests/test_sandbox.py`.

Covers:
  1. Malicious RSQ source (import os / open / __import__('os')) FAILS to load
     when sandboxed=True; a normal RSQ source loads & runs sandboxed=True.
  2. Default load_rsq (sandboxed=False) of a real builtin still works.
  3. run_sandboxed_solve on a real builtin returns correct results.
  4. A deliberately infinite RSQ hits the wall-clock timeout and raises.

Windows-safe: the multiprocessing entry is guarded by `if __name__ ==
"__main__"` and the worker (in sandbox.py) is a top-level function, so the
'spawn' start method can re-import it.

This test prefers a temporary Store / read-only access and does NOT seed or
modify the global builtins, to avoid clashing with concurrent registry writers.
For the run_sandboxed_solve cases (which use the global registry in the child),
it registers a uniquely-named throwaway RSQ and removes it afterward.
"""

import os
import sys
import tempfile

# Ensure the anvil package and the server app are importable when run script-style.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, _ROOT)


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


# A normal, benign RSQ source (what real native RSQs look like).
_GOOD_SOURCE = (
    "from anvil import Q\n"
    "import numpy as np\n"
    "def good(M, gamma=1.4):\n"
    "    T_ratio = 1 + ((gamma - 1) / 2) * M**2\n"
    "    return {\"T0_T\": float(T_ratio)}\n"
    "export = good\n"
)

# Malicious sources that must be REJECTED under sandboxed=True.
_MALICIOUS_SOURCES = {
    "import os": "import os\nexport = os\n",
    "open(...)": "f = open('x.txt', 'w')\nexport = f\n",
    "__import__('os')": "os = __import__('os')\nexport = os\n",
    "import subprocess": "import subprocess\nexport = subprocess\n",
    "eval": "x = eval('1+1')\nexport = x\n",
    "from anvil import registry": "from anvil import registry\nexport = registry\n",
}


def _rec(source, name="sbx_tmp", rsq_type="R"):
    return {
        "name": name,
        "type": rsq_type,
        "source": source,
        "depends": [],
        "metadata": {},
        "tags": [],
    }


def test_loader_sandbox_blocks_and_allows():
    from anvil.registry.loader import load_rsq

    # Benign source loads & runs fine sandboxed.
    try:
        rel = load_rsq(_rec(_GOOD_SOURCE, name="sbx_good"), sandboxed=True)
        res = rel(M=2.0, gamma=1.4)
        val = res["T0_T"] if isinstance(res, dict) else res.outputs.get("T0_T")
        # T0_T for M=2, gamma=1.4 => 1 + 0.2*4 = 1.8
        ok = abs(float(getattr(val, "value", val)) - 1.8) < 1e-9
    except Exception as exc:
        print(f"        (benign sandboxed load raised: {exc})")
        ok = False
    check("benign RSQ loads & runs under sandboxed=True", ok)

    # Each malicious source must raise under sandboxed=True.
    for label, src in _MALICIOUS_SOURCES.items():
        raised = False
        try:
            load_rsq(_rec(src, name="sbx_evil"), sandboxed=True)
        except Exception:
            raised = True
        check(f"malicious source blocked sandboxed=True: {label}", raised)

    # Sanity: with sandboxed=False, `import os` is NOT blocked (Tier A unchanged).
    unblocked = False
    try:
        load_rsq(_rec(_MALICIOUS_SOURCES["import os"], name="sbx_ta"), sandboxed=False)
        unblocked = True
    except Exception:
        unblocked = False
    check("Tier A (sandboxed=False) does NOT block import os", unblocked)


def test_default_load_unchanged():
    """Default load of a real builtin works exactly as before (read-only)."""
    from anvil import registry
    from anvil.registry.loader import load_rsq

    store = registry._get_store()
    rec = store.get("isentropic_ratios")
    ok = False
    if rec is not None:
        rel = load_rsq(rec, store)  # sandboxed defaults False
        out = rel(M=2.0, gamma=1.4)
        d = out if isinstance(out, dict) else out.outputs
        ok = abs(float(getattr(d["T0_T"], "value", d["T0_T"])) - 1.8) < 1e-9
    else:
        print("        (isentropic_ratios not in registry; skipping)")
        ok = True
    check("default load_rsq of builtin isentropic_ratios unchanged", ok)


def test_run_sandboxed_solve_correct():
    from anvil_server.app.sandbox import run_sandboxed_solve

    out = run_sandboxed_solve("isentropic_ratios", {"M": 2.0, "gamma": 1.4},
                              timeout_s=30.0, si=True)
    results = out.get("results", {})
    t0t = results.get("T0_T", {}).get("value")
    p0p = results.get("P0_P", {}).get("value")
    ok = (
        out["name"] == "isentropic_ratios"
        and t0t is not None and abs(float(t0t) - 1.8) < 1e-6
        and p0p is not None and abs(float(p0p) - 1.8 ** (1.4 / 0.4)) < 1e-3
    )
    check("run_sandboxed_solve(isentropic_ratios) returns correct results", ok)


def test_timeout():
    from anvil import registry
    from anvil_server.app.sandbox import run_sandboxed_solve, SandboxTimeout

    store = registry._get_store()
    slow_name = "sbx_infinite_loop_tmp"
    slow_source = (
        "def sbx_infinite_loop_tmp(x=1.0):\n"
        "    s = 0.0\n"
        "    while True:\n"
        "        s += x\n"
        "    return {\"y\": s}\n"
        "export = sbx_infinite_loop_tmp\n"
    )
    # Register a throwaway slow RSQ (origin 'local'), exercise timeout, remove.
    store.put(name=slow_name, rsq_type="R", source=slow_source, origin="local")
    try:
        raised = False
        try:
            run_sandboxed_solve(slow_name, {"x": 1.0}, timeout_s=2.0)
        except SandboxTimeout:
            raised = True
        check("infinite RSQ hits wall-clock timeout (SandboxTimeout)", raised)
    finally:
        store.remove(slow_name, origin="local")


def run():
    test_loader_sandbox_blocks_and_allows()
    test_default_load_unchanged()
    test_run_sandboxed_solve_correct()
    test_timeout()
    print(f"\nResults: {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    run()
