"""
Anvil Adapter: Surrogate / Metamodel Wrappers
==============================================

Wraps scikit-learn and GPy surrogate models as Anvil Adapters.
Enables data-driven surrogates to participate in Systems, sweeps,
and sensitivity analyses on equal footing with physics-based RSQs.

ADAPTERS PROVIDED:
    gaussian_process_1d   -- 1-input Gaussian Process regression (sklearn)
    polynomial_chaos_1d   -- 1-input polynomial chaos expansion (numpy)
    rbf_surrogate         -- Radial-basis-function interpolation (scipy)
    make_gp_adapter       -- Factory: build a GP surrogate from (X, y) training data

INSTALLATION:
    pip install scikit-learn       # for gaussian_process_1d
    pip install scipy              # for rbf_surrogate (bundled with Anvil deps)
    pip install GPy                # optional: advanced GP kernels

VERIFY:
    python -c "import sklearn; print(sklearn.__version__)"
    python -c "import GPy; print(GPy.__version__)"

REAL ONLY -- NO MOCK MODE:
    GP adapters require scikit-learn; a missing package raises ImportError.
    polynomial_chaos_1d (numpy polyfit) and rbf_surrogate (scipy RBF) are
    real methods implemented directly on Anvil's core dependencies.

USAGE:
    from anvil.adapters.surrogate_models import make_gp_adapter

    import numpy as np
    X_train = np.linspace(0, 10, 15).reshape(-1, 1)
    y_train = np.sin(X_train.ravel()) + 0.02 * np.random.randn(15)

    gp = make_gp_adapter(
        X_train, y_train,
        x_name="x", y_name="y_pred",
        x_unit="m", y_unit="1",
        name="sin_gp",
    )
    r = gp(x=3.14)
    print(r["y_pred"], r["y_std"])   # prediction + uncertainty

    register()
"""

from anvil import Adapter, Q
import math
import numpy as np


def _require_sklearn():
    """Import scikit-learn or raise with install instructions."""
    try:
        import sklearn  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "scikit-learn is not installed (needed for GP surrogates). "
            "Install with: pip install scikit-learn"
        ) from exc


def is_available() -> bool:
    """True when scikit-learn can be imported (GP surrogates usable)."""
    try:
        import sklearn  # noqa: F401
        return True
    except ImportError:
        return False


def _polyfit_predict(x_train, y_train, x_new, deg):
    """Polynomial fallback."""
    coeffs = np.polyfit(x_train, y_train, deg)
    y = float(np.polyval(coeffs, x_new))
    resid = y_train - np.polyval(coeffs, x_train)
    return y, float(np.std(resid))


# ── Adapter: 1-input Gaussian Process ────────────────────────────────────────

def _gp_1d_call(x, _X_train, _y_train, _gp_model=None, _x_scale=1.0, _y_scale=1.0):
    """Predict from a fitted GP surrogate."""
    x_val = float(x)
    X_new = np.array([[x_val / _x_scale]])

    if _gp_model is None:
        _require_sklearn()
        raise RuntimeError("GP model was not fitted; rebuild via make_gp_adapter().")
    y_pred, y_std = _gp_model.predict(X_new, return_std=True)
    return {
        "y_pred": float(y_pred[0]) * _y_scale,
        "y_std":  float(y_std[0]) * _y_scale,
        "source": "sklearn_gp",
    }


# ── Factory: GP surrogate from training data ──────────────────────────────────

def make_gp_adapter(X_train, y_train,
                    x_name="x", y_name="y_pred",
                    x_unit="1", y_unit="1",
                    name="gp_surrogate",
                    desc=None,
                    kernel=None,
                    normalize_y=True):
    """
    Build an Anvil Adapter from a GP fitted to (X_train, y_train).

    Parameters
    ----------
    X_train : array (n, 1)
        Training inputs (1-D only; shape (n,) or (n,1)).
    y_train : array (n,)
        Training targets.
    x_name, y_name : str
        Adapter input/output variable names.
    x_unit, y_unit : str
        Anvil unit strings for input/output.
    name : str
        Adapter name (appears in registry and System outputs).
    kernel : sklearn kernel or None
        Custom sklearn kernel. Default: RBF + WhiteKernel.
    normalize_y : bool
        Whether to normalize targets (recommended for GP stability).
    """
    X = np.asarray(X_train).reshape(-1, 1)
    y = np.asarray(y_train).ravel()
    x_scale = float(np.ptp(X)) if np.ptp(X) > 0 else 1.0
    y_scale = float(np.std(y)) if np.std(y) > 0 else 1.0
    X_n = X / x_scale
    y_n = y / y_scale

    _require_sklearn()
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import RBF, WhiteKernel, ConstantKernel
    if kernel is None:
        kernel = ConstantKernel(1.0) * RBF(1.0) + WhiteKernel(1e-2)
    gp_model = GaussianProcessRegressor(kernel=kernel, normalize_y=normalize_y,
                                        n_restarts_optimizer=5)
    gp_model.fit(X_n, y_n if not normalize_y else y)
    if not normalize_y:
        gp_model._y_scale = y_scale

    def _call(**kwargs):
        x_val = float(kwargs.get(x_name, 0.0))
        if isinstance(kwargs.get(x_name), Q):
            x_val = float(kwargs[x_name].si)

        X_new = np.array([[x_val / x_scale]])
        yp, ys = gp_model.predict(X_new, return_std=True)
        y_pred = float(yp[0]) * y_scale
        y_std  = float(ys[0]) * y_scale
        return {
            y_name:          Q(y_pred, y_unit) if y_unit != "1" else y_pred,
            y_name + "_std": Q(y_std, y_unit) if y_unit != "1" else y_std,
            "source": "sklearn_gp",
        }

    desc = desc or f"GP surrogate: {y_name} = f({x_name})"
    return Adapter(
        name, backend="python", call=_call,
        inputs={x_name:           {"unit": x_unit, "desc": "Surrogate input"}},
        outputs={
            y_name:          {"unit": y_unit, "desc": "GP mean prediction"},
            y_name + "_std": {"unit": y_unit, "desc": "GP predictive standard deviation"},
            "source":        {"desc": "always sklearn_gp (real fit; no mock fallback)"},
        },
        desc=desc,
        tags=["surrogate", "GP", "regression", "sklearn"],
    )


# ── Adapter: polynomial chaos / polyfit ──────────────────────────────────────

def _poly_chaos_call(x, _X_train, _y_train, _degree=4):
    x_val = float(x) if not isinstance(x, Q) else float(x.si)
    y, y_std = _polyfit_predict(
        np.asarray(_X_train).ravel(),
        np.asarray(_y_train).ravel(),
        x_val, _degree
    )
    return {"y_pred": y, "y_std": y_std, "source": "polyfit_pce"}


def make_poly_adapter(X_train, y_train,
                      x_name="x", y_name="y_pred",
                      x_unit="1", y_unit="1",
                      degree=4,
                      name="poly_surrogate",
                      desc=None):
    """
    Build a polynomial chaos / polyfit surrogate as Anvil Adapter.

    Parameters
    ----------
    degree : int
        Polynomial degree (2–6 recommended; higher may overfit).
    """
    X = np.asarray(X_train).ravel()
    y = np.asarray(y_train).ravel()
    coeffs = np.polyfit(X, y, degree)

    def _call(**kwargs):
        x_val = float(kwargs.get(x_name, 0.0))
        if isinstance(kwargs.get(x_name), Q):
            x_val = float(kwargs[x_name].si)
        yp = float(np.polyval(coeffs, x_val))
        resid = y - np.polyval(coeffs, X)
        ys = float(np.std(resid))
        return {
            y_name:          Q(yp, y_unit) if y_unit != "1" else yp,
            y_name + "_std": Q(ys, y_unit) if y_unit != "1" else ys,
            "source": "polyfit_pce",
        }

    desc = desc or f"Polynomial (degree {degree}) surrogate: {y_name} = f({x_name})"
    return Adapter(
        name, backend="python", call=_call,
        inputs={x_name: {"unit": x_unit, "desc": "Surrogate input"}},
        outputs={
            y_name:          {"unit": y_unit, "desc": "Polynomial prediction"},
            y_name + "_std": {"unit": y_unit, "desc": "Residual standard deviation"},
            "source":        {"desc": "polyfit_pce"},
        },
        desc=desc,
        tags=["surrogate", "polynomial", "PCE", "regression"],
    )


# ── Adapter: RBF interpolation (multi-input capable) ─────────────────────────

def make_rbf_adapter(X_train, y_train,
                     input_names=None, y_name="y_pred",
                     input_units=None, y_unit="1",
                     function="multiquadric",
                     name="rbf_surrogate",
                     desc=None):
    """
    Build an RBF interpolation surrogate (scipy) for n-dimensional inputs.

    Parameters
    ----------
    X_train : array (n_samples, n_features)
        Training inputs.
    y_train : array (n_samples,)
        Training targets.
    input_names : list[str] or None
        Names for each input dimension. Default: ["x0", "x1", ...].
    input_units : list[str] or None
        Anvil unit string for each input. Default: all "1".
    function : str
        RBF kernel: "multiquadric", "gaussian", "linear", "cubic", "thin_plate".
    """
    from scipy.interpolate import RBFInterpolator
    X = np.asarray(X_train, dtype=float)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    y = np.asarray(y_train, dtype=float).ravel()
    n_feat = X.shape[1]

    if input_names is None:
        input_names = [f"x{i}" for i in range(n_feat)]
    if input_units is None:
        input_units = ["1"] * n_feat

    # Fit RBF (scipy >= 1.7). Scale-dependent kernels need an epsilon; use
    # the mean nearest-neighbour spacing of the training points.
    kernel = {"thin_plate": "thin_plate_spline"}.get(function, function)
    if kernel in ("multiquadric", "inverse_multiquadric",
                  "inverse_quadratic", "gaussian"):
        from scipy.spatial.distance import pdist
        d = pdist(X)
        eps = float(np.mean(d)) if d.size else 1.0
        rbf = RBFInterpolator(X, y, kernel=kernel, epsilon=eps)
    else:
        rbf = RBFInterpolator(X, y, kernel=kernel)

    def _call(**kwargs):
        x_vals = []
        for name_i, unit_i in zip(input_names, input_units):
            v = kwargs.get(name_i, 0.0)
            if isinstance(v, Q):
                v = float(v.si)
            else:
                v = float(v)
            x_vals.append(v)

        X_new = np.array(x_vals).reshape(1, -1)
        yp = float(rbf(X_new)[0])

        return {
            y_name:  Q(yp, y_unit) if y_unit != "1" else yp,
            "source": "rbf_scipy",
        }

    inputs_spec = {
        nm: {"unit": ut, "desc": f"Input dimension {i}"}
        for i, (nm, ut) in enumerate(zip(input_names, input_units))
    }
    desc = desc or f"RBF ({function}) surrogate with {n_feat} inputs"
    return Adapter(
        name, backend="python", call=_call,
        inputs=inputs_spec,
        outputs={
            y_name: {"unit": y_unit, "desc": "RBF interpolated prediction"},
            "source": {"desc": "rbf_scipy"},
        },
        desc=desc,
        tags=["surrogate", "RBF", "interpolation", "scipy"],
    )


# ── Demo adapter: pre-built GP on noisy sine data ─────────────────────────────

def _demo_gp_call(x):
    """Demo GP surrogate trained on noisy sin(x) data."""
    x_val = float(x) if not isinstance(x, Q) else float(x.si)

    # Training data (fixed seed for reproducibility)
    rng = np.random.default_rng(42)
    X_tr = np.sort(rng.uniform(0, 2 * math.pi, 20))
    y_tr = np.sin(X_tr) + 0.05 * rng.standard_normal(20)

    _require_sklearn()
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import RBF, WhiteKernel, ConstantKernel
    kernel = ConstantKernel(1.0) * RBF(1.0) + WhiteKernel(1e-2)
    gp = GaussianProcessRegressor(kernel=kernel, normalize_y=True,
                                  n_restarts_optimizer=3)
    gp.fit(X_tr.reshape(-1, 1), y_tr)
    yp, ys = gp.predict([[x_val]], return_std=True)
    return {"y_pred": float(yp[0]), "y_std": float(ys[0]),
            "y_exact": math.sin(x_val), "source": "sklearn_gp"}


gp_demo = Adapter(
    "gp_demo_sine",
    backend="python",
    call=_demo_gp_call,
    inputs={"x": {"unit": "1", "desc": "Input (0 to 2π)", "default": 1.5}},
    outputs={
        "y_pred":  {"unit": "1", "desc": "GP mean prediction"},
        "y_std":   {"unit": "1", "desc": "GP predictive std"},
        "y_exact": {"unit": "1", "desc": "Exact sin(x) for comparison"},
        "source":  {"desc": "always sklearn_gp (real fit; no mock fallback)"},
    },
    desc="Demo GP surrogate: noisy sin(x) training data (requires sklearn)",
    tags=["surrogate", "GP", "demo", "sklearn"],
)


# ── Register ─────────────────────────────────────────────────────────────────

def register():
    import anvil
    anvil.push(gp_demo, domain="surrogate.demo",
               description=gp_demo.desc, tags=gp_demo.tags)
    print("Registered: gp_demo_sine  [domain: surrogate.demo]")
    print("Factories available: make_gp_adapter, make_poly_adapter, make_rbf_adapter")
