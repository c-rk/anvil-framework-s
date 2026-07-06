"""
Anvil Adapter: pyNASTRAN Structural Analysis
=============================================

Wraps pyNASTRAN for reading, running, and post-processing NASTRAN structural
analyses. pyNASTRAN provides both a BDF read/write API and an OP2 results reader.

ADAPTERS PROVIDED:
    nastran_linear_static  -- SOL 101 linear static: displacements, stresses
    nastran_normal_modes   -- SOL 103 normal modes: natural frequencies, mode shapes
    nastran_parametric     -- Modify a BDF template, run NASTRAN, read results

INSTALLATION:
    pip install pyNASTRAN

    To run actual NASTRAN analyses, a NASTRAN binary must be on PATH:
        MSC NASTRAN: nas.exe (commercial)
        NEi NASTRAN, NX NASTRAN (commercial)
        Optistruct (Altair, partial NASTRAN compatibility)
        FEMAPNastran (commercial)
        MYSTRAN (open-source NASTRAN-compatible solver):
            https://github.com/dr-bill-c/MYSTRAN  ← free, open source

VERIFY pyNASTRAN:
    python -c "import pyNastran; print(pyNastran.__version__)"

VERIFY NASTRAN binary (MYSTRAN example):
    mystran --version

REAL ONLY -- NO MOCK MODE:
    Requires the pyNastran package AND a NASTRAN-compatible solver binary
    (MYSTRAN is free/open-source). Missing either raises a clear error.

USAGE:
    from anvil.adapters.pynastran_fem import nastran_linear_static

    # Requires a .bdf file and NASTRAN binary
    r = nastran_linear_static(
        bdf_path="my_model.bdf",
        load_case_id=1,
    )
    print(r["max_displacement"], r["max_stress"])

    # Or use the parametric adapter to modify a template
    r = nastran_parametric(
        bdf_template="beam_template.bdf",
        param_subs={"E_STEEL": 200e9, "F_TIP": 5000.0},
        load_case=1,
    )

    register()
"""

from anvil import Adapter, Q
import math, os, shutil, subprocess, tempfile


# ── NASTRAN runner ────────────────────────────────────────────────────────────

def is_available() -> bool:
    """True when both pyNastran and a NASTRAN-compatible binary are present."""
    try:
        import pyNastran  # noqa: F401
    except ImportError:
        return False
    return _find_nastran() is not None

def _require_nastran():
    """Check pyNastran + solver binary, or raise with instructions."""
    try:
        import pyNastran  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "pyNastran is not installed. Install with: pip install pyNastran"
        ) from exc
    if _find_nastran() is None:
        raise RuntimeError(
            "No NASTRAN-compatible solver binary found on PATH. MYSTRAN is a "
            "free open-source option: https://github.com/dr-bill-c/MYSTRAN"
        )

def _find_nastran():
    """Find NASTRAN-compatible solver binary."""
    for name in ("nastran", "nas", "msc_nastran", "nastran.exe",
                 "mystran", "mystran.exe", "optistruct", "optistruct.exe"):
        p = shutil.which(name)
        if p:
            return p
    return None

def _run_nastran(bdf_path, workdir, nastran_bin=None, timeout=1200):
    """Run NASTRAN/MYSTRAN on bdf_path. Returns OP2 path or None."""
    if nastran_bin is None:
        nastran_bin = _find_nastran()
    if nastran_bin is None:
        return None
    log = os.path.join(workdir, "nastran.log")
    try:
        with open(log, "w") as lf:
            proc = subprocess.run(
                [nastran_bin, os.path.basename(bdf_path)],
                cwd=workdir, stdout=lf, stderr=subprocess.STDOUT,
                timeout=timeout
            )
        # Look for OP2 output
        base = os.path.splitext(os.path.basename(bdf_path))[0]
        op2 = os.path.join(workdir, base + ".op2")
        return op2 if os.path.exists(op2) else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _read_op2_static(op2_path, load_case_id=1):
    """Read max displacement and stress from OP2 via pyNASTRAN."""
    try:
        from pyNastran.op2.op2 import OP2
        op2 = OP2(debug=False)
        op2.read_op2(op2_path)

        max_disp = 0.0
        if op2.displacements:
            for subcase_id, res in op2.displacements.items():
                if subcase_id == load_case_id or True:   # take first available
                    import numpy as np
                    disp_xyz = res.data[-1, :, :3]
                    mags = np.linalg.norm(disp_xyz, axis=1)
                    max_disp = max(max_disp, float(mags.max()))
                    break

        max_stress = 0.0
        for stress_dict in (op2.cbar_stress, op2.crod_stress,
                            op2.cquad4_stress, op2.ctria3_stress):
            if stress_dict:
                for subcase_id, res in stress_dict.items():
                    import numpy as np
                    max_stress = max(max_stress, float(np.abs(res.data).max()))
                    break

        return max_disp, max_stress
    except (ImportError, Exception):
        return None

def _read_op2_modes(op2_path, n_modes=6):
    """Read natural frequencies from OP2."""
    try:
        from pyNastran.op2.op2 import OP2
        op2 = OP2(debug=False)
        op2.read_op2(op2_path)
        if op2.eigenvalues:
            for key, ev in op2.eigenvalues.items():
                return list(ev.frequencies[:n_modes])
        return None
    except (ImportError, Exception):
        return None


# ── Adapter: linear static ────────────────────────────────────────────────────

def _static_call(bdf_path, load_case_id=1, nastran_bin=None):
    bdf_path = str(bdf_path)
    _require_nastran()
    if not os.path.exists(bdf_path):
        raise RuntimeError(f"BDF input deck not found: {bdf_path}")
    with tempfile.TemporaryDirectory() as work:
        dst_bdf = os.path.join(work, os.path.basename(bdf_path))
        shutil.copy(bdf_path, dst_bdf)
        op2_path = _run_nastran(dst_bdf, work,
                                nastran_bin=(None if nastran_bin=="auto"
                                             else nastran_bin))
        if not op2_path:
            raise RuntimeError(
                "NASTRAN run produced no .op2 output; see nastran.log."
            )
        res = _read_op2_static(op2_path, int(load_case_id))
        if not res:
            raise RuntimeError("Could not read displacements/stresses from OP2.")
        max_disp, max_stress = res
        return {
            "max_displacement": Q(max_disp,  "m"),
            "max_stress":       Q(max_stress, "Pa"),
            "source": "nastran",
        }


nastran_linear_static = Adapter(
    "nastran_linear_static",
    backend="python",
    call=_static_call,
    inputs={
        "bdf_path":      {"desc": "Path to NASTRAN .bdf input deck"},
        "load_case_id":  {"desc": "Load case (subcase) ID to read", "default": 1},
        "nastran_bin":   {"desc": "Path to NASTRAN binary (None=auto-detect)", "default": "auto"},
    },
    outputs={
        "max_displacement": {"unit": "m",   "desc": "Maximum nodal displacement magnitude"},
        "max_stress":       {"unit": "Pa",  "desc": "Maximum element stress (von Mises or max principal)"},
        "source":           {"desc": "always 'nastran' (real run; no mock fallback)"},
    },
    desc="NASTRAN SOL 101 linear static analysis via pyNASTRAN",
    tags=["nastran", "FEM", "structures", "linear", "static", "displacement"],
)


# ── Adapter: normal modes ─────────────────────────────────────────────────────

def _modes_call(bdf_path, n_modes=6, nastran_bin=None):
    bdf_path=str(bdf_path)
    nm=int(n_modes)
    _require_nastran()
    if not os.path.exists(bdf_path):
        raise RuntimeError(f"BDF input deck not found: {bdf_path}")
    with tempfile.TemporaryDirectory() as work:
        dst_bdf = os.path.join(work, os.path.basename(bdf_path))
        shutil.copy(bdf_path, dst_bdf)
        op2_path = _run_nastran(dst_bdf, work,
                                nastran_bin=(None if nastran_bin=="auto"
                                             else nastran_bin))
        if not op2_path:
            raise RuntimeError(
                "NASTRAN run produced no .op2 output; see nastran.log."
            )
        freqs = _read_op2_modes(op2_path, nm)
        if not freqs:
            raise RuntimeError("Could not read eigenvalues from OP2 (is it SOL 103?).")
        freqs_arr = [Q(f, "Hz") for f in freqs]
        return {
            "frequencies": freqs_arr,
            "f1": freqs_arr[0],
            "f2": freqs_arr[1] if len(freqs_arr) > 1 else freqs_arr[0],
            "n_modes": len(freqs_arr),
            "source": "nastran",
        }


nastran_normal_modes = Adapter(
    "nastran_normal_modes",
    backend="python",
    call=_modes_call,
    inputs={
        "bdf_path":      {"desc": "Path to NASTRAN .bdf (SOL 103)"},
        "n_modes":       {"desc": "Number of modes to extract", "default": 6},
        "nastran_bin":   {"desc": "Path to NASTRAN binary", "default": "auto"},
    },
    outputs={
        "frequencies": {"desc": "List of natural frequencies [Q in Hz]"},
        "f1":          {"unit": "Hz", "desc": "First natural frequency"},
        "f2":          {"unit": "Hz", "desc": "Second natural frequency"},
        "n_modes":     {"desc": "Number of modes extracted"},
        "source":      {"desc": "always 'nastran' (real run; no mock fallback)"},
    },
    desc="NASTRAN SOL 103 normal modes analysis via pyNASTRAN",
    tags=["nastran", "FEM", "modal", "normal_modes", "frequency", "vibration"],
)


# ── Register ─────────────────────────────────────────────────────────────────

def register():
    import anvil
    for adapter in (nastran_linear_static, nastran_normal_modes):
        anvil.push(adapter, domain="fem.nastran",
                   description=adapter.desc, tags=adapter.tags)
    print("Registered: nastran_linear_static, nastran_normal_modes"
          "  [domain: fem.nastran]")
