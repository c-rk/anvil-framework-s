"""Runtime configuration for the Anvil backend.

Execution tiers
---------------
Tier A (default): in-process execution. The backend imports ``anvil`` directly
and runs RSQs inside the FastAPI worker process. Fast, no external binaries.

Tier B (NATIVE_ONLY=1): a more conservative mode intended for deployments that
must not shell out to external tooling. When enabled, the registry exposed by
``/api/registry`` and ``/api/rsq/{name}`` is filtered to RSQs that:

  * do NOT carry the ``tierA`` or ``cli`` tags (these mark RSQs that are only
    meaningful through the local CLI / interactive tier), and
  * declare no dependency on an external binary.

The current Anvil seed registry uses none of the ``tierA``/``cli`` tags and no
external-binary RSQs, so in practice Tier B currently exposes the same set as
Tier A. The filter is intentionally conservative: it is wired up and documented
so that as soon as such RSQs are added, they are excluded automatically without
a code change here.
"""

from __future__ import annotations

import os

# Tags that mark an RSQ as tier-A / CLI-only (excluded under NATIVE_ONLY).
EXCLUDED_TAGS = {"tierA", "tiera", "cli"}

# Metadata keys that, if present and truthy, indicate the RSQ needs an external
# binary to execute. Excluded under NATIVE_ONLY.
EXTERNAL_BINARY_META_KEYS = ("external_binary", "requires_binary", "binary")

# --------------------------------------------------------------------------- #
# Calculator / array classification (web UI feedback)
# --------------------------------------------------------------------------- #

# Tags that mark an RSQ as a wrapper around an EXTERNAL solver/library (an
# "adapter"). These are NOT calculator-friendly: they need a third-party package
# or external binary, so the calculator steers users to the canvas instead.
ADAPTER_TAGS = {
    "xfoil", "openfoam", "su2", "cantera", "coolprop", "rocketcea", "rocketpy",
    "gmsh", "cadquery", "nastran", "openmdao", "poliastro", "pykep", "fenics",
    "surrogate", "tierb",
}

# Domain prefixes that indicate an adapter-backed RSQ (e.g. "thermo.coolprop",
# "propulsion.cea", "uq.montecarlo", "geometry.mesh").
ADAPTER_DOMAIN_PREFIXES = (
    "thermo.coolprop", "propulsion.cea", "propulsion.combustion",
    "uq.montecarlo", "geometry.mesh",
)

# RSQs whose primary inputs are 1-D arrays / time-series (signal-processing and
# decomposition). The calculator renders an array-input widget (or steers to the
# canvas) for these, and the executor solves them via the direct relation path.
ARRAY_INPUT_RSQS = {
    "fft_spectrum", "welch_psd", "stft_spectrogram", "bandpass_filter",
    "envelope_detection", "cross_correlation", "signal_statistics",
    "pod_modes", "dmd_modes", "pca_reduce", "svd_decompose",
    # Curve fitting / regression: take (x_data, y_data) arrays.
    "linear_regression", "poly_fit", "power_fit", "exp_fit",
}

# Input names that, if present on an RSQ, indicate an array / time-series input.
ARRAY_INPUT_NAMES = {"signal", "signal_a", "signal_b", "data", "X", "matrix", "samples"}


def is_adapter(record: dict) -> bool:
    """Heuristic: is this RSQ a wrapper around an external solver/library?

    True when any of:
      * a known adapter tag is present (e.g. coolprop, cantera, rocketcea), or
      * the domain starts with an adapter-ish prefix (thermo.coolprop, ...), or
      * the metadata declares an external binary dependency.
    """
    tags = {str(t).lower() for t in (record.get("tags") or [])}
    if tags & ADAPTER_TAGS:
        return True
    domain = (record.get("domain") or "").lower()
    if any(domain == p or domain.startswith(p + ".") or domain == p
           for p in ADAPTER_DOMAIN_PREFIXES):
        return True
    if domain.startswith(tuple(ADAPTER_DOMAIN_PREFIXES)):
        return True
    meta = record.get("metadata") or {}
    for key in EXTERNAL_BINARY_META_KEYS:
        if meta.get(key):
            return True
    return False


def has_array_input(record: dict) -> bool:
    """True if this RSQ takes a 1-D array / time-series as a primary input."""
    name = record.get("name", "")
    if name in ARRAY_INPUT_RSQS:
        return True
    meta = record.get("metadata") or {}
    inputs = meta.get("inputs") or {}
    if isinstance(inputs, dict) and (set(inputs) & ARRAY_INPUT_NAMES):
        return True
    return False


def is_calculator_ok(record: dict) -> bool:
    """A plain Relation the web calculator can drive with scalar/quantity inputs.

    calculator_ok = type == "R" AND not an adapter AND not array-only.
    Systems (type S) and Quantities (type Q) are excluded; adapters are excluded
    (they need external packages); array-input RSQs are excluded (the calculator
    has no easy way to supply a long signal -- those go to the canvas).
    """
    if record.get("type") != "R":
        return False
    if is_adapter(record):
        return False
    if has_array_input(record):
        return False
    return True


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class Settings:
    """Process-wide settings, read once from the environment."""

    def __init__(self) -> None:
        # Tier B switch.
        self.native_only: bool = _env_flag("NATIVE_ONLY", False)

        # --- Sandbox (Tier B untrusted-execution) settings ----------------- #
        # When native_only is active, RSQ source is treated as untrusted remote
        # input. SANDBOX_ENABLED routes solves through a subprocess-isolated,
        # restricted-namespace executor. It defaults ON whenever native_only is
        # on (and OFF for plain Tier A), but can be overridden via env.
        self.sandbox_enabled: bool = _env_flag(
            "SANDBOX_ENABLED", default=self.native_only
        )
        # Wall-clock timeout (seconds) for a single sandboxed solve. The child
        # process is terminated if it exceeds this.
        self.sandbox_timeout_s: float = _env_float("SANDBOX_TIMEOUT_S", 10.0)
        # Memory note: Windows has no resource.setrlimit / seccomp, so we rely
        # on subprocess isolation + a wall-clock timeout rather than a hard RSS
        # cap. On POSIX a soft RLIMIT_AS could be added in the child worker.
        self.sandbox_mem_note: str = (
            "no hard memory cap on Windows; isolation via subprocess + wall-clock timeout"
        )

        # Project-local registry (ANVIL_PROJECT or --project): a project
        # directory (containing .anvil/project_*.db), a .anvil dir, or a direct
        # path to one project .db. Project RSQs are merged into the catalog
        # (shadowing global names) and are solvable like any built-in.
        self.project_path: str | None = (
            os.environ.get("ANVIL_PROJECT", "").strip() or None
        )

        # CORS origins for the Vite dev server (and anything extra via env).
        extra = os.environ.get("ANVIL_CORS_ORIGINS", "")
        self.cors_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ] + [o.strip() for o in extra.split(",") if o.strip()]

    @property
    def tier(self) -> str:
        return "B (native-only)" if self.native_only else "A (in-process)"


settings = Settings()


def record_is_native(record: dict) -> bool:
    """Return True if an RSQ record is allowed under Tier B (native-only)."""
    tags = {str(t).lower() for t in (record.get("tags") or [])}
    if tags & EXCLUDED_TAGS:
        return False
    meta = record.get("metadata") or {}
    for key in EXTERNAL_BINARY_META_KEYS:
        if meta.get(key):
            return False
    return True
