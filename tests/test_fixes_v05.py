"""
Regression tests for the v0.5 fixes:
  1. System.copy() isolates per-relation caches (deep-copy contract).
  2. Result records the solver method actually used.
  3. Store search/domain filters escape LIKE wildcards ('_' is literal).
  4. anvil.push(overwrite=True) suppresses the overwrite warning.

Script-style (run directly): `python tests/test_fixes_v05.py`.
"""
import sys
import warnings
import tempfile
import os

import anvil
from anvil import Q
from anvil.registry.store import Store

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


# --- 1. copy() isolation ---------------------------------------------------
def f_force(m, a):
    return {"F": m * a}

base = anvil.system("copytest")
base.add("m", 10.0, "kg")
base.add("a", 3.0, "m/s^2")
base.use(f_force)

clone = base.copy()
# relations must be distinct objects after copy()
check("copy() clones relation objects",
      clone._relations[0] is not base._relations[0])
# solving the clone must not mutate the base relation's cache
clone.solve_forward()
check("clone solve leaves base relation cache untouched",
      getattr(base._relations[0], "_qty_compatible", None) is None)
r_clone = clone.solve_forward()
check("clone solves correctly (F=30 N)", abs(float(r_clone["F"].value) - 30.0) < 1e-9)


# --- 2. Result records method ---------------------------------------------
r_fwd = base.copy().solve_forward()
check("Result.method == 'forward'", r_fwd.method == "forward")


# --- 3. LIKE wildcard escaping --------------------------------------------
tmpdir = tempfile.mkdtemp()
db = os.path.join(tmpdir, "t.db")
st = Store(db_path=db)
st.put(name="tx_one", rsq_type="R", source="export = lambda: {}", domain="d")
st.put(name="txzone", rsq_type="R", source="export = lambda: {}", domain="d")
hits = {r["name"] for r in st.search("tx_one")}
check("search('tx_one') matches only literal name (escaped '_')",
      hits == {"tx_one"})
st.close()


# --- 4. push(overwrite=) wiring -------------------------------------------
def _ov_demo(x):
    return {"y": x}

try:
    anvil.push(_ov_demo, name="_ov_demo_tmp", domain="test")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        anvil.push(_ov_demo, name="_ov_demo_tmp", domain="test", overwrite=True)
        overwrite_warned = any("already exists" in str(x.message) for x in w)
    check("push(overwrite=True) suppresses overwrite warning", not overwrite_warned)
finally:
    try:
        anvil.registry.remove("_ov_demo_tmp")
    except Exception:
        pass


# --- 5. string outputs survive a System solve (adapter "source" field) ------
def f_with_source(x):
    return {"y": x * 2.0, "source": "mock"}

ssys = anvil.system("strtest")
ssys.add("x", 3.0)
ssys.use(f_with_source)
try:
    rs = ssys.solve_forward()
    str_ok = (abs(float(rs["y"].value) - 6.0) < 1e-9) and (rs["source"] == "mock")
except Exception as e:
    str_ok = False
    print(f"  (string-output solve raised: {type(e).__name__}: {e})")
check("string output ('source') passes through System solve", str_ok)


print("\n" + "=" * 50)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 50)
if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
