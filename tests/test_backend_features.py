"""Backend feature tests for the web-UI enhancements (script-style).

Run directly: `python tests/test_backend_features.py`.

Exercises the executor / route helper FUNCTIONS directly (no HTTP) for:

  1. ARRAY / TIME-SERIES inputs: fft_spectrum + signal_statistics solve with a
     numpy/list signal; scalar outputs finite, array outputs serialized as lists.
  2. CALCULATOR-ONLY classification: calculator_ok / array_input / adapter flags.
  3. SWEEP with FIXED (non-swept) inputs.
  4. LIVE registry freshness: a pushed RSQ becomes visible + solvable after
     refresh_registry(), without restart.
  5. CSV parsing.
  6. EXAMPLE canvases: list non-empty; each example well-formed AND solvable.
  7. Scalar solves still work (no regression).
"""
import math
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, _ROOT)

import anvil  # noqa: E402

from anvil_server.app import examples_data, executor  # noqa: E402
from anvil_server.app.builder_routes import solve_system, BuilderError  # noqa: E402


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


def _is_number(x):
    return isinstance(x, (int, float)) and math.isfinite(x)


# --- a temp relation used for the live-freshness test ---------------------- #
def _bf_live_rel(a, b):
    """Temp relation registered AFTER import to test live freshness."""
    return {"c_live": a + 2.0 * b}


def _run_tests():
    # === 1. Array / time-series inputs ==================================== #
    n, fs = 1024, 1024.0
    dt = 1.0 / fs
    signal = [math.sin(2 * math.pi * 50 * i * dt)
              + 0.3 * math.sin(2 * math.pi * 150 * i * dt) for i in range(n)]

    res = executor.solve(
        "fft_spectrum",
        {"signal": signal, "dt": {"value": dt, "unit": "s"}, "window": "hann"},
    )
    check("fft_spectrum solves via direct path", res["method"] == "direct")
    dom = res["results"]["dominant_freq"]["value"]
    check("fft dominant_freq finite", _is_number(dom))
    check("fft dominant_freq ~ 50 Hz", abs(dom - 50.0) < 1.0)
    power = res["results"]["power"]["value"]
    check("fft array output serialized as list", isinstance(power, list))
    check("fft array output non-empty + finite",
          len(power) > 0 and all(p is None or _is_number(p) for p in power))
    check("fft 'signal' input echoed", "signal" in res["results"])

    # signal_statistics: array IN, all scalar OUT.
    rs = executor.solve("signal_statistics", {"signal": signal, "dt": dt})
    rms = rs["results"]["rms"]["value"]
    check("signal_statistics rms finite", _is_number(rms))
    check("signal_statistics rms ~ 0.74", abs(rms - 0.7385) < 0.05)

    # === 2. Classification: calculator_ok / array_input / adapter ========= #
    reg = {x["name"]: x for x in executor.list_registry()}
    check("isentropic_ratios calculator_ok=True",
          reg["isentropic_ratios"]["calculator_ok"] is True)
    check("fft_spectrum array_input=True", reg["fft_spectrum"]["array_input"] is True)
    check("fft_spectrum calculator_ok=False",
          reg["fft_spectrum"]["calculator_ok"] is False)
    # An adapter (coolprop if present, else any tagged adapter) -> calc_ok False.
    adapter_name = "coolprop_props" if "coolprop_props" in reg else next(
        (n for n, e in reg.items() if e["adapter"]), None
    )
    check("found an adapter RSQ to test", adapter_name is not None)
    if adapter_name:
        check(f"adapter '{adapter_name}' calculator_ok=False",
              reg[adapter_name]["calculator_ok"] is False)
        check(f"adapter '{adapter_name}' adapter=True",
              reg[adapter_name]["adapter"] is True)

    calc_items = executor.list_registry(calc_only=True)
    check("calc filter returns a non-empty subset",
          0 < len(calc_items) < len(reg))
    check("calc filter excludes all adapters",
          not any(x["adapter"] for x in calc_items))
    check("calc filter excludes all array RSQs",
          not any(x["array_input"] for x in calc_items))
    check("calc filter all type R",
          all(x["type"] == "R" for x in calc_items))

    # describe() carries the same flags
    d = executor.describe("isentropic_ratios")
    check("describe carries calculator_ok", d["calculator_ok"] is True)
    df = executor.describe("fft_spectrum")
    check("describe carries array_input", df["array_input"] is True)

    # === 3. Sweep with FIXED inputs ====================================== #
    sw = executor.sweep(
        "specific_impulse", "thrust", [1000.0, 2000.0, 3000.0],
        outputs=["Isp"], inputs={"mdot": 2.0},
    )
    isp = sw["data"].get("Isp")
    check("sweep w/ fixed input produced Isp column",
          isinstance(isp, list) and len(isp) == 3)
    check("sweep Isp values finite + increasing",
          isp is not None and all(_is_number(v) for v in isp)
          and isp[0] < isp[1] < isp[2])
    # Isp = thrust / (mdot * g0); g0=9.80665 -> thrust=2000 -> ~101.97
    check("sweep Isp value correct (thrust=2000,mdot=2)",
          abs(isp[1] - 2000.0 / (2.0 * 9.80665)) < 0.5)

    # === 4. Live registry freshness ====================================== #
    try:
        anvil.registry.remove("_bf_live_rel")
    except Exception:
        pass
    # Push directly to the store (simulating a client anvil.push AFTER start).
    anvil.push(_bf_live_rel, name="_bf_live_rel", domain="misc",
               description="temp live-freshness rel", overwrite=True)
    try:
        reg_after = {x["name"]: x for x in executor.list_registry()}
        check("pushed RSQ visible in live registry", "_bf_live_rel" in reg_after)
        # Refresh + solve in-process.
        status = executor.refresh_registry()
        check("refresh_registry returns ok", status["status"] == "ok")
        live = executor.solve("_bf_live_rel", {"a": 3.0, "b": 4.0})
        check("pushed RSQ solvable after refresh",
              abs(live["results"]["c_live"]["value"] - 11.0) < 1e-6)
    finally:
        try:
            anvil.registry.remove("_bf_live_rel")
        except Exception:
            pass

    # === 5. CSV parsing ================================================== #
    csv_text = "time,voltage,label\n0,1.5,a\n1,2.5,b\n2,3.5,c\n"
    p = executor.parse_csv(csv_text)
    check("csv columns parsed", p["columns"] == ["time", "voltage", "label"])
    check("csv row count", p["rows"] == 3)
    check("csv numeric column -> numbers", p["data"]["voltage"] == [1.5, 2.5, 3.5])
    check("csv text column -> strings", p["data"]["label"] == ["a", "b", "c"])
    check("csv preview has rows", len(p["preview"]) == 3)
    # headerless numeric CSV
    p2 = executor.parse_csv("1,2,3\n4,5,6\n")
    check("headerless csv synthesizes col names",
          p2["columns"] == ["col0", "col1", "col2"] and p2["rows"] == 2)

    # === 6. Example canvases ============================================= #
    exs = examples_data.list_examples()
    check("examples list non-empty", len(exs) > 0)
    check("each example summary well-formed",
          all(e.get("id") and e.get("name") for e in exs))

    for e in exs:
        full = examples_data.get_example(e["id"])
        check(f"example '{e['id']}' has full payload", full is not None)
        if full is None:
            continue
        # Well-formed: quantities + relations present.
        wf = bool(full.get("quantities")) and bool(full.get("relations"))
        check(f"example '{e['id']}' well-formed", wf)
        # Solvable: array examples via executor.solve, others via builder.
        if full.get("array_input"):
            rel = full["relations"][0]
            inputs = {q["name"]: q["value"] for q in full["quantities"]}
            try:
                r = executor.solve(rel, inputs)
                ok = len(r["outputs"]) > 0
            except Exception as exc:  # noqa: BLE001
                ok = False
                print(f"      (array solve err: {exc})")
            check(f"example '{e['id']}' array-solvable", ok)
        else:
            payload = {
                "name": full["id"],
                "quantities": full["quantities"],
                "relations": full["relations"],
            }
            try:
                r = solve_system(payload)
                ok = len(r["outputs"]) > 0
            except BuilderError as exc:
                ok = False
                print(f"      (builder err: {exc})")
            except Exception as exc:  # noqa: BLE001
                ok = False
                print(f"      (solve err: {exc})")
            check(f"example '{e['id']}' builder-solvable", ok)

    # === 7. Scalar solve regression ===================================== #
    r2 = executor.solve("isentropic_ratios", {"M": 2.0, "gamma": 1.4})
    check("scalar solve method forward", r2["method"] == "forward")
    check("scalar solve P0_P correct",
          abs(r2["results"]["P0_P"]["value"] - 7.8244) < 0.01)
    # scalar solve with units
    r3 = executor.solve("normal_shock", {"M1": 2.0, "gamma": 1.4})
    check("scalar normal_shock M2 finite",
          _is_number(r3["results"]["M2"]["value"]))


def run():
    _run_tests()
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
