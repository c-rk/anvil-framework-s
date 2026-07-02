"""
Anvil Adapter: Uncertainty Quantification via Monte Carlo + Surrogate
=====================================================================

Propagates input uncertainty through a response model by Monte Carlo
sampling and reports the output mean, standard deviation and quantiles.
Optionally fits a polynomial-regression surrogate; the optional surrogate
backend can require scikit-learn.

ADAPTERS PROVIDED:
    uq_montecarlo  -- MC mean/std/quantiles over a built-in response model
                      with two normally-distributed inputs.

NATIVE vs OPTIONAL DEPENDENCY:
    The Monte Carlo propagation itself is GENUINELY native numpy and always
    runs (mean/std/quantiles), with a native numpy least-squares quadratic
    surrogate R^2 -- this is NOT a mock. It requires only numpy.

    Only the OPTIONAL scikit-learn regression surrogate requires sklearn:
    pass surrogate="sklearn" to use it. If sklearn is requested but not
    installed, the adapter raises a clear ImportError naming the package.
    With surrogate="numpy" (the default) or "none", the pure-numpy MC path
    runs without any extra packages.

INSTALLATION:
    (pure numpy -- the MC path needs nothing extra)
    pip install scikit-learn    # only for surrogate="sklearn"

VERIFY:
    python -c "import numpy; print(numpy.__version__)"
    python -c "import sklearn; print(sklearn.__version__)"

RESPONSE MODELS (model=...):
    "sum"      f = a + b
    "product"  f = a * b
    "ratio"    f = a / b
    "quadratic" f = a^2 + b^2
    "rosenbrock" f = (1-a)^2 + 100*(b-a^2)^2

USAGE:
    from anvil.adapters.uq_surrogate import uq_montecarlo, register

    r = uq_montecarlo(model="product",
                      a_mean=10.0, a_std=1.0,
                      b_mean=5.0,  b_std=0.5,
                      n_samples=20000, seed=0)
    print(r["mean"], r["std"], r["p05"], r["p95"], r["surrogate_r2"], r["source"])

    register()   # push to anvil registry under "uq.montecarlo"
"""

from anvil import Adapter, Q


def uq_montecarlo_call(model="product", a_mean=10.0, a_std=1.0,
                       b_mean=5.0, b_std=0.5, n_samples=10000, seed=0,
                       surrogate="numpy"):
    """
    Monte Carlo uncertainty propagation through a built-in response model.

    Two independent normal inputs a ~ N(a_mean, a_std), b ~ N(b_mean, b_std)
    are sampled n_samples times and pushed through the selected response
    model. Returns output mean/std/quantiles and a regression surrogate R^2.
    Inputs arrive as raw SI floats or Q.

    The MC statistics are genuinely native numpy and always run. The
    surrogate backend is selected by ``surrogate``:
        "numpy"  (default) -- native numpy least-squares quadratic R^2
        "none"             -- skip the surrogate (surrogate_r2 = 0.0)
        "sklearn"          -- scikit-learn LinearRegression R^2; raises a
                              clear ImportError if scikit-learn is absent.
    """
    import numpy as np
    from anvil import Q

    if hasattr(model, "value"):
        model = str(model.value)
    model = str(model)
    if hasattr(surrogate, "value"):
        surrogate = str(surrogate.value)
    surrogate = str(surrogate).strip().lower()
    a_mean = float(a_mean.si) if hasattr(a_mean, "si") else float(a_mean)
    a_std = float(a_std.si) if hasattr(a_std, "si") else float(a_std)
    b_mean = float(b_mean.si) if hasattr(b_mean, "si") else float(b_mean)
    b_std = float(b_std.si) if hasattr(b_std, "si") else float(b_std)
    n_samples = int(n_samples.si) if hasattr(n_samples, "si") else int(n_samples)
    seed = int(seed.si) if hasattr(seed, "si") else int(seed)
    n_samples = max(n_samples, 16)

    rng = np.random.default_rng(seed)
    a = rng.normal(a_mean, a_std, n_samples)
    b = rng.normal(b_mean, b_std, n_samples)

    m = model.strip().lower()
    if m == "sum":
        y = a + b
    elif m == "product":
        y = a * b
    elif m == "ratio":
        denom = np.where(np.abs(b) < 1e-9, 1e-9, b)
        y = a / denom
    elif m == "quadratic":
        y = a ** 2 + b ** 2
    elif m == "rosenbrock":
        y = (1.0 - a) ** 2 + 100.0 * (b - a ** 2) ** 2
    else:
        y = a * b  # default

    y = np.asarray(y, dtype=float)
    finite = y[np.isfinite(y)]
    if finite.size == 0:
        finite = np.array([0.0])

    # --- Native numpy MC statistics (always run) ----------------------------
    mean = float(np.mean(finite))
    std = float(np.std(finite))
    p05 = float(np.percentile(finite, 5))
    p50 = float(np.percentile(finite, 50))
    p95 = float(np.percentile(finite, 95))

    # --- Regression surrogate: quadratic features of (a, b) -----------------
    X = np.column_stack([a, a ** 2, b, b ** 2, a * b])
    r2 = 0.0
    source = "montecarlo"

    if surrogate == "none":
        source = "montecarlo"
    elif surrogate == "sklearn":
        try:
            from sklearn.linear_model import LinearRegression
            from sklearn.metrics import r2_score
        except ImportError as e:
            raise ImportError(
                "uq_montecarlo surrogate='sklearn' requires the "
                "'scikit-learn' package; install with: "
                "pip install scikit-learn"
            ) from e
        reg = LinearRegression().fit(X, y)
        r2 = float(r2_score(y, reg.predict(X)))
        source = "montecarlo+sklearn"
    else:
        # Default: native numpy least-squares quadratic fit (genuinely native)
        A = np.column_stack([np.ones(len(y)), X])
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        y_hat = A @ coef
        ss_res = float(np.sum((y - y_hat) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
        source = "montecarlo+numpy"

    return {
        "mean":         mean,
        "std":          std,
        "p05":          p05,
        "p50":          p50,
        "p95":          p95,
        "surrogate_r2": r2,
        "source":       source,
    }


uq_montecarlo = Adapter(
    "uq_montecarlo",
    backend="python",
    call=uq_montecarlo_call,
    inputs={
        "model":     {"desc": "Response model: sum|product|ratio|quadratic|rosenbrock",
                      "default": "product"},
        "a_mean":    {"unit": "1", "desc": "Mean of input a", "default": 10.0},
        "a_std":     {"unit": "1", "desc": "Std-dev of input a", "default": 1.0},
        "b_mean":    {"unit": "1", "desc": "Mean of input b", "default": 5.0},
        "b_std":     {"unit": "1", "desc": "Std-dev of input b", "default": 0.5},
        "n_samples": {"unit": "1", "desc": "Number of MC samples", "default": 10000},
        "seed":      {"unit": "1", "desc": "RNG seed", "default": 0},
        "surrogate": {"desc": "Surrogate backend: numpy|none|sklearn",
                      "default": "numpy"},
    },
    outputs={
        "mean":         {"unit": "1", "desc": "Output mean"},
        "std":          {"unit": "1", "desc": "Output standard deviation"},
        "p05":          {"unit": "1", "desc": "5th percentile"},
        "p50":          {"unit": "1", "desc": "Median (50th percentile)"},
        "p95":          {"unit": "1", "desc": "95th percentile"},
        "surrogate_r2": {"unit": "1", "desc": "Quadratic regression surrogate R^2"},
        "source":       {"desc": "montecarlo+numpy (native) or montecarlo+sklearn"},
    },
    desc="Monte Carlo UQ (mean/std/quantiles) + regression surrogate over a response model",
    tags=["uq", "montecarlo", "surrogate", "regression", "sklearn", "tierB"],
)


def register():
    """Push the UQ adapter to the global Anvil registry."""
    import anvil
    anvil.push(uq_montecarlo_call, name="uq_montecarlo",
               domain="uq.montecarlo",
               description=uq_montecarlo.desc,
               tags=uq_montecarlo.tags, overwrite=True)
    print("Registered: uq_montecarlo  [domain: uq.montecarlo]")


if __name__ == "__main__":
    r = uq_montecarlo(model="product", a_mean=10.0, a_std=1.0,
                      b_mean=5.0, b_std=0.5, n_samples=20000, seed=0)
    for k, v in r.items():
        print(f"  {k}: {v}")
