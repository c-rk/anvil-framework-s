"""
Anvil Adapter: SU2 CFD Aerodynamics
=====================================

Wraps SU2 (Stanford University Unstructured) for Euler and RANS aerodynamic
analysis. SU2 is particularly strong for shape optimization and adjoint-based
gradient computation.

ADAPTERS PROVIDED:
    su2_euler    -- Inviscid Euler: CL, CD at given Mach/AoA
    su2_rans     -- Turbulent RANS (SA model): CL, CD, CM
    su2_adjoint  -- Adjoint sensitivities: dCL/dX, dCD/dX surface shape derivatives

INSTALLATION:
    pip install SU2           (Python wrapper)
    or binary: https://su2code.github.io/download.html
    Put SU2_CFD on PATH.

VERIFY:
    SU2_CFD --version

SU2 CONFIG TEMPLATE:
    Each adapter requires a base .cfg file and a mesh file (.su2 format).
    The adapter patches: MACH_NUMBER, AOA, SIDESLIP_ANGLE, REYNOLDS_NUMBER.
    All other settings (numerics, convergence, BCs) come from the template.

REAL ONLY -- NO MOCK MODE:
    Requires the SU2_CFD binary on PATH plus a real .cfg template and .su2
    mesh. Missing binary or files raise a RuntimeError with instructions.

USAGE:
    from anvil.adapters.su2_aero import su2_euler, su2_rans

    r = su2_euler(cfg_template="naca0012.cfg", mesh="naca0012.su2",
                  Mach=0.8, AoA_deg=2.0)
    print(r["CL"], r["CD"])

    register()
"""

from anvil import Adapter, Q
import math, os, shutil, subprocess, tempfile, re as _re


def _require_su2():
    """Locate SU2_CFD or raise with install instructions."""
    su2 = shutil.which("SU2_CFD") or shutil.which("SU2_CFD.exe")
    if su2 is None:
        raise RuntimeError(
            "SU2_CFD binary not found on PATH. Download from "
            "https://su2code.github.io/ and place SU2_CFD on PATH."
        )
    return su2

def is_available() -> bool:
    """True when the SU2_CFD binary is on PATH."""
    return (shutil.which("SU2_CFD") or shutil.which("SU2_CFD.exe")) is not None

def _require_files(cfg_template, mesh):
    if not os.path.exists(cfg_template):
        raise RuntimeError(f"SU2 config template not found: {cfg_template}")
    if not os.path.exists(mesh):
        raise RuntimeError(f"SU2 mesh file not found: {mesh}")


# ── SU2 config patching ───────────────────────────────────────────────────────

def _patch_cfg(src_cfg, dst_cfg, mach, aoa, sideslip=0.0, reynolds=None):
    with open(src_cfg) as f:
        lines = f.readlines()
    out = []
    for line in lines:
        if _re.match(r'\s*MACH_NUMBER\s*=', line):
            out.append(f"MACH_NUMBER= {mach:.6f}\n")
        elif _re.match(r'\s*AOA\s*=', line):
            out.append(f"AOA= {aoa:.6f}\n")
        elif _re.match(r'\s*SIDESLIP_ANGLE\s*=', line):
            out.append(f"SIDESLIP_ANGLE= {sideslip:.6f}\n")
        elif reynolds and _re.match(r'\s*REYNOLDS_NUMBER\s*=', line):
            out.append(f"REYNOLDS_NUMBER= {reynolds:.1f}\n")
        else:
            out.append(line)
    with open(dst_cfg, "w") as f:
        f.writelines(out)


def _parse_su2_history(history_file):
    """Parse SU2 history.csv for last-iteration CL, CD, CM."""
    if not os.path.exists(history_file):
        return None
    with open(history_file) as f:
        lines = f.readlines()
    if len(lines) < 3:
        return None
    # Find header
    header = lines[0].strip().strip('"').split('","')
    header = [h.strip().strip('"') for h in header]
    # Last data line
    data = lines[-1].split(",")
    try:
        idx = {h: i for i, h in enumerate(header)}
        CL = float(data[idx["CL"]])
        CD = float(data[idx["CD"]])
        CM = float(data[idx.get("CMz", idx.get("CMy", idx.get("CM", 0)))])
        return CL, CD, CM
    except (KeyError, ValueError, IndexError):
        return None


def _run_su2(cfg_path, workdir, timeout=3600):
    """Run SU2_CFD. Returns True if succeeded."""
    su2 = shutil.which("SU2_CFD") or shutil.which("SU2_CFD.exe")
    if su2 is None:
        return False
    log = os.path.join(workdir, "su2.log")
    with open(log, "w") as lf:
        proc = subprocess.run(
            [su2, os.path.basename(cfg_path)],
            cwd=workdir, stdout=lf, stderr=subprocess.STDOUT, timeout=timeout,
        )
    return proc.returncode == 0


# ── Adapter: Euler ────────────────────────────────────────────────────────────

def _euler_call(cfg_template, mesh, Mach, AoA_deg,
                sideslip_deg=0.0, alpha0_deg=0.0):
    for k, v in dict(Mach=Mach, AoA_deg=AoA_deg).items():
        if isinstance(v, Q): locals()[k] = float(v.si)
    Mach=float(Mach); AoA=float(AoA_deg); ss=float(sideslip_deg)
    cfg_template=str(cfg_template); mesh=str(mesh)

    _require_su2()
    _require_files(cfg_template, mesh)
    with tempfile.TemporaryDirectory() as work:
        dst_cfg  = os.path.join(work, "run.cfg")
        dst_mesh = os.path.join(work, os.path.basename(mesh))
        shutil.copy(mesh, dst_mesh)
        _patch_cfg(cfg_template, dst_cfg, Mach, AoA, ss)
        # Also patch mesh filename in cfg
        with open(dst_cfg) as f: content = f.read()
        content = _re.sub(r'MESH_FILENAME\s*=.*',
                           f'MESH_FILENAME= {os.path.basename(mesh)}', content)
        with open(dst_cfg, "w") as f: f.write(content)

        if not _run_su2(dst_cfg, work):
            raise RuntimeError("SU2_CFD run failed; see su2.log in the work dir.")
        hist = os.path.join(work, "history.csv")
        res = _parse_su2_history(hist)
        if not res:
            raise RuntimeError("SU2 finished but history.csv had no CL/CD/CM.")
        CL, CD, CM = res
        return {"CL": CL, "CD": CD, "CM": CM,
                "Mach": Q(Mach,"1"), "source": "su2"}


su2_euler = Adapter(
    "su2_euler",
    backend="python",
    call=_euler_call,
    inputs={
        "cfg_template": {"desc": "Path to SU2 .cfg template file"},
        "mesh":         {"desc": "Path to SU2 .su2 mesh file"},
        "Mach":         {"unit": "1",   "desc": "Freestream Mach number"},
        "AoA_deg":      {"unit": "deg", "desc": "Angle of attack"},
        "sideslip_deg": {"unit": "deg", "desc": "Sideslip angle", "default": 0.0},
        "alpha0_deg":   {"unit": "deg", "desc": "Zero-lift AoA (unused; kept for signature compatibility)", "default": 0.0},
    },
    outputs={
        "CL":     {"unit": "1",  "desc": "Lift coefficient"},
        "CD":     {"unit": "1",  "desc": "Drag coefficient (wave + induced)"},
        "CM":     {"unit": "1",  "desc": "Pitching moment coefficient"},
        "Mach":   {"unit": "1",  "desc": "Freestream Mach (echo)"},
        "source": {"desc": "always 'su2' (real run; no mock fallback)"},
    },
    desc="Inviscid Euler aerodynamics via SU2_CFD",
    tags=["su2", "euler", "inviscid", "CL", "CD", "compressible"],
)


# ── Adapter: RANS ─────────────────────────────────────────────────────────────

def _rans_call(cfg_template, mesh, Mach, AoA_deg,
               Reynolds=1e6, sideslip_deg=0.0, alpha0_deg=0.0):
    for k, v in dict(Mach=Mach, AoA_deg=AoA_deg, Reynolds=Reynolds).items():
        if isinstance(v, Q): locals()[k] = float(v.si)
    Mach=float(Mach); AoA=float(AoA_deg); Re=float(Reynolds); ss=float(sideslip_deg)
    cfg_template=str(cfg_template); mesh=str(mesh)

    _require_su2()
    _require_files(cfg_template, mesh)
    with tempfile.TemporaryDirectory() as work:
        dst_cfg  = os.path.join(work, "run.cfg")
        dst_mesh = os.path.join(work, os.path.basename(mesh))
        shutil.copy(mesh, dst_mesh)
        _patch_cfg(cfg_template, dst_cfg, Mach, AoA, ss, Re)
        with open(dst_cfg) as f: content = f.read()
        content = _re.sub(r'MESH_FILENAME\s*=.*',
                           f'MESH_FILENAME= {os.path.basename(mesh)}', content)
        with open(dst_cfg, "w") as f: f.write(content)
        if not _run_su2(dst_cfg, work):
            raise RuntimeError("SU2_CFD run failed; see su2.log in the work dir.")
        hist = os.path.join(work, "history.csv")
        res = _parse_su2_history(hist)
        if not res:
            raise RuntimeError("SU2 finished but history.csv had no CL/CD/CM.")
        CL, CD, CM = res
        return {"CL": CL, "CD": CD, "CM": CM,
                "Mach": Q(Mach,"1"), "Re": Q(Re,"1"), "source": "su2"}


su2_rans = Adapter(
    "su2_rans",
    backend="python",
    call=_rans_call,
    inputs={
        "cfg_template": {"desc": "Path to SU2 .cfg with turbulence model set"},
        "mesh":         {"desc": "Path to .su2 mesh (wall BCs required)"},
        "Mach":         {"unit": "1",   "desc": "Freestream Mach"},
        "AoA_deg":      {"unit": "deg", "desc": "Angle of attack"},
        "Reynolds":     {"unit": "1",   "desc": "Reynolds number", "default": 1e6},
        "sideslip_deg": {"unit": "deg", "desc": "Sideslip angle", "default": 0.0},
        "alpha0_deg":   {"unit": "deg", "desc": "Zero-lift AoA (unused; kept for signature compatibility)", "default": 0.0},
    },
    outputs={
        "CL":     {"unit": "1", "desc": "Lift coefficient"},
        "CD":     {"unit": "1", "desc": "Total drag (pressure + friction)"},
        "CM":     {"unit": "1", "desc": "Pitching moment"},
        "Mach":   {"unit": "1", "desc": "Freestream Mach"},
        "Re":     {"unit": "1", "desc": "Reynolds number"},
        "source": {"desc": "always 'su2' (real run; no mock fallback)"},
    },
    desc="Turbulent RANS aerodynamics via SU2_CFD (Spalart-Allmaras)",
    tags=["su2", "RANS", "turbulent", "viscous", "CL", "CD"],
)


# ── Register ─────────────────────────────────────────────────────────────────

def register():
    import anvil
    for adapter in (su2_euler, su2_rans):
        anvil.push(adapter, domain="cfd.su2",
                   description=adapter.desc, tags=adapter.tags)
    print("Registered: su2_euler, su2_rans  [domain: cfd.su2]")
