"""
Example: UQ Adapter -- Monte Carlo Uncertainty Propagation in Anvil
==================================================================

Demonstrates the uq_montecarlo adapter: propagate input uncertainty through
a response model and report mean/std/quantiles plus a regression surrogate
R^2, as direct calls and inside an Anvil System.

The Monte Carlo path is GENUINELY native numpy and always runs -- there is no
mock. The default surrogate (surrogate="numpy") is a native numpy
least-squares quadratic fit. Only surrogate="sklearn" requires scikit-learn;
if requested without scikit-learn installed it raises a clear ImportError,
which this example catches and reports.
"""

import anvil
from anvil import Q
from anvil.adapters.uq_surrogate import uq_montecarlo, register


def _num(v):
    """Plain float of a Q or number (uq outputs are plain floats)."""
    return float(v.value) if hasattr(v, "value") else float(v)


W = 64
print("=" * W)
print("  UQ Monte Carlo Adapter Example (native numpy MC)")
print("=" * W)

register()

# ── 1. UQ over several response models (native numpy MC, always runs) ────────
print("\n[1] a ~ N(10,1), b ~ N(5,0.5), 20000 samples (native numpy)")
print(f"  {'model':10s}  {'mean':>10s}  {'std':>9s}  {'p05':>10s}  {'p95':>10s}  {'R2':>6s}")
print(f"  {'-'*10}  {'-'*10}  {'-'*9}  {'-'*10}  {'-'*10}  {'-'*6}")
for model in ("sum", "product", "ratio", "quadratic"):
    r = uq_montecarlo(model=model, a_mean=10.0, a_std=1.0,
                      b_mean=5.0, b_std=0.5, n_samples=20000, seed=0)
    print(f"  {model:10s}  {_num(r['mean']):10.4f}  {_num(r['std']):9.4f}  "
          f"{_num(r['p05']):10.4f}  {_num(r['p95']):10.4f}  {_num(r['surrogate_r2']):6.3f}")
print(f"  (source: {r['source']})")

# ── 1b. Optional scikit-learn surrogate ──────────────────────────────────────
print("\n[1b] Optional scikit-learn surrogate (surrogate='sklearn')")
try:
    rs = uq_montecarlo(model="product", a_mean=10.0, a_std=1.0,
                       b_mean=5.0, b_std=0.5, n_samples=20000, seed=0,
                       surrogate="sklearn")
    print(f"  sklearn surrogate R^2 = {_num(rs['surrogate_r2']):.4f}  "
          f"(source: {rs['source']})")
except ImportError as e:
    print("  scikit-learn is not installed -- the optional sklearn surrogate")
    print(f"  is unavailable: {e}")
    print("  Install scikit-learn to use it: pip install scikit-learn")
    print("  (The native numpy MC above ran fine without it.)")

# ── 2. Pipeline: UQ feeding a margin calculation ─────────────────────────────
print("\n[2] System: design margin from UQ mean & std (native numpy MC)")
uq = uq_montecarlo(model="product", a_mean=100.0, a_std=5.0,
                   b_mean=2.0, b_std=0.1, n_samples=20000, seed=0)
print(f"  mean    = {_num(uq['mean']):.2f}  (source: {uq['source']})")
print(f"  std     = {_num(uq['std']):.2f}")

study = anvil.system("uq_study")
study.add("mean", _num(uq["mean"]), "1")
study.add("std", _num(uq["std"]), "1")
study.add("limit", 250.0, "1")

def margin(mean, std, limit):
    # Number of std-devs of headroom before exceeding the limit.
    n_sigma = (limit - mean) / std if std > 0 else float("inf")
    return {"n_sigma": Q(n_sigma, "1")}
study.use(margin)

res = study.solve_forward()
print(f"  n_sigma = {res['n_sigma'].value:.2f}")

print("\n" + "=" * W)
print("  Done.")
print("=" * W)
