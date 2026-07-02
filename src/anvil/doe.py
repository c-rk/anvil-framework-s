"""
Design of Experiments (DOE) for Anvil systems.

Generate parameter samples and evaluate a System across them.

    from anvil import doe

    bounds = {"P0": (3e6, 10e6), "A_exit": (0.05, 0.25)}
    samples = doe.latin_hypercube(bounds, n=32, seed=0)
    results = doe.run_doe(nozzle, samples, outputs=["thrust", "Isp"], parallel=4)

Samplers
--------
    latin_hypercube(bounds, n, seed=None)   -- space-filling LHS (scipy.qmc)
    sobol(bounds, n, seed=None)             -- low-discrepancy Sobol sequence
    full_factorial(levels)                  -- grid over explicit level lists

Each sampler returns a list of ``dict`` samples ``{param: value}`` ready to
feed System evaluation. ``run_doe`` evaluates a System over such a list and
returns a :class:`DOEResult` (a simple tabular structure).

Pure Python + numpy + scipy only (Tier-B eligible).
"""

from __future__ import annotations
import itertools
import numpy as np
from scipy.stats import qmc

from anvil.quantity import Quantity
from anvil.system import Result, _run_parallel
from anvil import units as _u


__all__ = [
    "latin_hypercube", "sobol", "full_factorial", "run_doe", "DOEResult",
]


def _check_bounds(bounds):
    if not bounds:
        raise ValueError("bounds must be a non-empty dict {param: (lo, hi)}.")
    names = list(bounds.keys())
    lo = np.array([float(bounds[k][0]) for k in names], dtype=float)
    hi = np.array([float(bounds[k][1]) for k in names], dtype=float)
    if np.any(hi < lo):
        bad = [k for k in names if float(bounds[k][1]) < float(bounds[k][0])]
        raise ValueError(f"bounds have hi < lo for: {bad}")
    return names, lo, hi


def _scaled_to_samples(unit_samples, names, lo, hi):
    """Map a (n, d) array in the unit cube to a list of param->value dicts."""
    scaled = qmc.scale(unit_samples, lo, hi)
    return [{names[j]: float(row[j]) for j in range(len(names))}
            for row in scaled]


def latin_hypercube(bounds, n, seed=None):
    """
    Latin Hypercube sampling over ``bounds``.

    Parameters
    ----------
    bounds : dict[str, (lo, hi)]
        Parameter ranges in each parameter's declared unit.
    n : int
        Number of samples.
    seed : int or None
        RNG seed for reproducibility.

    Returns
    -------
    list[dict]
        ``n`` samples, each mapping param name -> value.
    """
    names, lo, hi = _check_bounds(bounds)
    n = int(n)
    if n < 1:
        raise ValueError("n must be >= 1.")
    sampler = qmc.LatinHypercube(d=len(names), seed=seed)
    unit = sampler.random(n)
    return _scaled_to_samples(unit, names, lo, hi)


def sobol(bounds, n, seed=None):
    """
    Sobol low-discrepancy sampling over ``bounds``.

    ``n`` is honoured exactly. Sobol sequences are most uniform when ``n`` is a
    power of two; a warning is emitted otherwise (via scipy), but any ``n`` is
    accepted.

    Parameters
    ----------
    bounds : dict[str, (lo, hi)]
        Parameter ranges in each parameter's declared unit.
    n : int
        Number of samples.
    seed : int or None
        RNG seed for reproducibility.

    Returns
    -------
    list[dict]
        ``n`` samples, each mapping param name -> value.
    """
    names, lo, hi = _check_bounds(bounds)
    n = int(n)
    if n < 1:
        raise ValueError("n must be >= 1.")
    sampler = qmc.Sobol(d=len(names), seed=seed)
    # sampler.random(n) accepts arbitrary n (warns if not a power of two).
    import warnings as _w
    with _w.catch_warnings():
        _w.simplefilter("ignore")
        unit = sampler.random(n)
    return _scaled_to_samples(unit, names, lo, hi)


def full_factorial(levels):
    """
    Full-factorial design: the Cartesian product of explicit level lists.

    Parameters
    ----------
    levels : dict[str, list]
        ``{param: [v1, v2, ...]}``. The design has ``prod(len(values))`` rows.

    Returns
    -------
    list[dict]
        One sample per grid point, mapping param name -> value.
    """
    if not levels:
        raise ValueError("levels must be a non-empty dict {param: [values...]}.")
    names = list(levels.keys())
    value_lists = [list(levels[k]) for k in names]
    for k, vals in zip(names, value_lists):
        if len(vals) == 0:
            raise ValueError(f"levels['{k}'] is empty.")
    samples = []
    for combo in itertools.product(*value_lists):
        samples.append({names[j]: combo[j] for j in range(len(names))})
    return samples


class DOEResult:
    """
    Tabular results from a Design of Experiments run.

    Attributes
    ----------
    samples : list[dict]
        The input samples evaluated.
    results : list[Result | None]
        Per-sample solve Result (None if that point failed and skip_errors).
    outputs : list[str]
        Output keys collected into the table (excludes the swept inputs).
    """

    def __init__(self, samples, results, outputs=None, system_name=""):
        self.samples = list(samples)
        self.results = list(results)
        self._system_name = system_name
        self._param_names = list(samples[0].keys()) if samples else []
        if outputs is not None:
            self.outputs = list(outputs)
        else:
            valid = [r for r in self.results if r is not None]
            if valid:
                self.outputs = [k for k in valid[0].keys()
                                if k not in self._param_names]
            else:
                self.outputs = []

    def __len__(self):
        return len(self.results)

    def __getitem__(self, key):
        """Column access: returns an array over all rows for input or output ``key``."""
        if key in self._param_names:
            return np.array([float(s[key]) for s in self.samples])
        col = []
        for r in self.results:
            if r is None or key not in r:
                col.append(np.nan)
            else:
                v = r[key]
                col.append(float(v._si_value) if isinstance(v, Quantity)
                           else float(v))
        return np.array(col)

    def to_dict(self, si=False):
        """Export as a dict of column arrays (inputs + outputs)."""
        out = {}
        for p in self._param_names:
            out[p] = np.array([float(s[p]) for s in self.samples])
        for key in self.outputs:
            col = []
            for r in self.results:
                if r is None or key not in r:
                    col.append(np.nan)
                else:
                    v = r[key]
                    if isinstance(v, Quantity):
                        col.append(float(v._si_value) if si else float(v.value))
                    else:
                        col.append(float(v))
            out[key] = np.array(col)
        return out

    def to_rows(self, si=False):
        """Export as a list of flat dict rows (input + output values)."""
        d = self.to_dict(si=si)
        cols = self._param_names + self.outputs
        rows = []
        for i in range(len(self.results)):
            rows.append({c: float(d[c][i]) for c in cols if c in d})
        return rows

    def to_csv(self, path, si=False):
        """Write the design table to a CSV file."""
        d = self.to_dict(si=si)
        cols = self._param_names + self.outputs
        with open(path, "w") as f:
            f.write(",".join(cols) + "\n")
            for i in range(len(self.results)):
                f.write(",".join(str(d[c][i]) for c in cols) + "\n")

    def summary(self, max_rows=12):
        n = len(self.results)
        n_ok = sum(1 for r in self.results if r is not None)
        cols = self._param_names + self.outputs[:6]
        w = 13
        print(f"\n{'-' * (w * len(cols) + 2)}")
        title = f"{self._system_name} -- DOE" if self._system_name else "DOE"
        print(f"  {title}  ({n_ok}/{n} succeeded)")
        print(f"{'-' * (w * len(cols) + 2)}")
        print("  " + "".join(f"{c:>{w}s}" for c in cols))
        print("  " + "-" * (w * len(cols)))
        d = self.to_dict()
        shown = min(n, max_rows)
        for i in range(shown):
            row = "  "
            for c in cols:
                v = d[c][i] if c in d else float("nan")
                row += f"{v:>{w}.4g}"
            print(row)
        if n > shown:
            print(f"  ... ({n - shown} more rows)")
        print(f"{'-' * (w * len(cols) + 2)}")

    def __repr__(self):
        return (f"DOEResult({len(self.results)} samples, "
                f"{len(self.outputs)} outputs)")


def run_doe(system, samples, outputs=None, parallel=1, skip_errors=False,
            backend=None, **solve_kwargs):
    """
    Evaluate a System over a list of DOE samples.

    Parameters
    ----------
    system : System
        The system to evaluate. It is not mutated; one independent copy is made
        per sample via ``System.copy()``.
    samples : list[dict]
        Samples from ``latin_hypercube`` / ``sobol`` / ``full_factorial`` (or
        any list of ``{param: value}`` dicts). Each param must already exist in
        the system (added via ``.add()``).
    outputs : list[str] or None
        Output keys to collect. Default: all computed outputs.
    parallel : int
        Number of workers. >1 uses the pluggable parallel executor from
        ``system.py`` (process pool by default, thread fallback if unpicklable).
    skip_errors : bool
        If True, failed samples are recorded as None rather than raising.
    backend : {"process", "thread", "serial"} or None
        Override the default parallel backend for this run.
    **solve_kwargs
        Passed to ``System.solve()`` for every sample.

    Returns
    -------
    DOEResult
        Tabular results aligned with ``samples``.
    """
    samples = list(samples)
    if not samples:
        return DOEResult([], [], outputs=outputs, system_name=system.name)

    # Validate parameter names against the system once, with a clear message.
    unknown = set()
    for s in samples:
        for k in s:
            if k not in system._quantities:
                unknown.add(k)
    if unknown:
        raise KeyError(
            f"DOE sample parameter(s) not in system '{system.name}': "
            f"{sorted(unknown)}.\n"
            f"  Available: {', '.join(system._quantities.keys())}\n"
            f"  Hint: add them with system.add(name, value, unit) first."
        )

    def _build(sample):
        sc = system.copy()
        for name, val in sample.items():
            q = sc._quantities[name]
            scale = 1.0
            if q._unit_hint and q._unit_hint in _u.db._forward:
                scale = _u.db._forward[q._unit_hint][0]
            sc._quantities[name] = Quantity._raw(
                float(val) * scale, q._dim, name=name, unit_hint=q._unit_hint)
            sc._quantities[name].role = q.role
        sc._validated = False
        return sc

    labels = [str(s) for s in samples]

    if parallel <= 1:
        results = []
        for i, s in enumerate(samples):
            sc = _build(s)
            try:
                results.append(sc.solve(**solve_kwargs))
            except Exception as e:
                if skip_errors:
                    import warnings as _w
                    _w.warn(f"DOE sample {labels[i]} failed: {e}", stacklevel=2)
                    results.append(None)
                else:
                    raise RuntimeError(
                        f"DOE failed at sample {labels[i]}.\n  {e}") from e
    else:
        systems = [_build(s) for s in samples]
        results = _run_parallel(
            systems, solve_kwargs, parallel, backend=backend,
            skip_errors=skip_errors, labels=labels,
        )

    return DOEResult(samples, results, outputs=outputs, system_name=system.name)
