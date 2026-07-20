"""Anvil command-line interface.

    anvil version            print the installed Anvil version
    anvil doctor             report environment health (deps, adapters, server)
    anvil serve [...]        start the web workbench server

Design note: this module must stay import-light. Nothing heavier than the
standard library is imported at module level, so `anvil version` is instant
even in environments where numpy/scipy/fastapi are missing or slow to load.
"""

from __future__ import annotations

import argparse
import sys


# --------------------------------------------------------------------------- #
# version
# --------------------------------------------------------------------------- #

def get_version() -> str:
    try:
        from importlib.metadata import version
        return version("anvil-framework")
    except Exception:
        try:
            import anvil
            return anvil.__version__
        except Exception:
            return "unknown"


def cmd_version(_args: argparse.Namespace) -> int:
    print(f"anvil {get_version()}")
    return 0


# --------------------------------------------------------------------------- #
# doctor
# --------------------------------------------------------------------------- #

# Python-package-backed adapters. Entries:
#   (adapter functions, import name checked, install hint)
# This list mirrors the real modules in src/anvil/adapters/ -- update both
# together when adapters are added.
_PACKAGE_ADAPTERS = [
    ("coolprop_props",                        "CoolProp",  "pip install CoolProp"),
    ("cea_rocket, equilibrium_flame",         "cantera",   "pip install cantera  (or: conda install -c cantera cantera)"),
    ("cea_detonation",                        "cea",       "pip install cea"),
    ("rocket_cea",                            "rocketcea", "pip install rocketcea"),
    ("rocketpy_flight",                       "rocketpy",  "pip install rocketpy"),
    ("mesh_box, mesh_cylinder",               "gmsh",      "pip install gmsh"),
    ("surrogate adapters (GP/poly/RBF)",      "sklearn",   "pip install scikit-learn"),
    ("pynastran_fem (SOL 101/103)",           "pyNastran", "pip install pyNastran"),
    ("openmdao wrapper (Sellar, beam)",       "openmdao",  "pip install openmdao"),
    ("poliastro_orbit / hohmann / propagate", "poliastro", "pip install poliastro astropy"),
    ("pykep_lambert / propagate / planet",    "pykep",     "pip install pykep"),
    ("fenics_fem (elasticity, heat)",         "dolfinx",   "conda install -c conda-forge fenics-dolfinx mpi4py petsc4py"),
]

# Binary-backed adapters: (adapter, [binary names tried], install hint)
_BINARY_ADAPTERS = [
    ("xfoil_airfoil (2D polars)", ["xfoil"],
     "install XFOIL and put xfoil(.exe) on PATH (https://web.mit.edu/drela/Public/web/xfoil/)"),
    ("su2_aero (Euler/RANS)", ["SU2_CFD"],
     "download SU2 from https://su2code.github.io/download.html and add SU2_CFD to PATH"),
    ("openfoam_cfd (simpleFoam)", ["simpleFoam"],
     "install OpenFOAM (OS package / docker; https://openfoam.org) so simpleFoam is on PATH"),
    ("pynastran_fem solver binary",
     ["nastran", "nas", "msc_nastran", "mystran", "optistruct"],
     "install MYSTRAN (https://www.mystran.com) or another NASTRAN-compatible solver on PATH"),
]


def _find_spec(name: str) -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _dist_version(import_name: str) -> str:
    """Best-effort version string for an importable package."""
    dist = "scikit-learn" if import_name == "sklearn" else import_name
    try:
        import importlib.metadata as md
        try:
            return md.version(dist)
        except md.PackageNotFoundError:
            mod = __import__(import_name)
            return getattr(mod, "__version__", "?")
    except Exception:
        return "?"


def cmd_doctor(_args: argparse.Namespace) -> int:
    import platform
    import shutil
    from pathlib import Path

    ok = "AVAILABLE"
    miss = "MISSING  "

    print("Anvil doctor")
    print("=" * 72)

    # --- core ------------------------------------------------------------- #
    print(f"python      {platform.python_version()}  ({sys.executable})")
    print(f"anvil       {get_version()}")
    for pkg in ("numpy", "scipy"):
        if _find_spec(pkg):
            print(f"{pkg:<11} {_dist_version(pkg)}")
        else:
            print(f"{pkg:<11} MISSING -- core dependency! pip install -e .")

    # --- adapters (python packages) --------------------------------------- #
    print()
    print("Adapters (python packages)")
    print("-" * 72)
    for adapter, module, hint in _PACKAGE_ADAPTERS:
        if _find_spec(module):
            print(f"  {ok} {adapter}  [{module} {_dist_version(module)}]")
        else:
            print(f"  {miss}{adapter}\n            -> {hint}")

    # --- adapters (external binaries) ------------------------------------- #
    print()
    print("Adapters (external binaries)")
    print("-" * 72)
    for adapter, names, hint in _BINARY_ADAPTERS:
        path = next((p for n in names if (p := shutil.which(n))), None)
        if path:
            print(f"  {ok} {adapter}  [{path}]")
        else:
            print(f"  {miss}{adapter}\n            -> {hint}")

    # --- web workbench ----------------------------------------------------- #
    print()
    print("Web workbench")
    print("-" * 72)
    server_ok = True
    for pkg in ("fastapi", "uvicorn"):
        if _find_spec(pkg):
            print(f"  {ok} {pkg} {_dist_version(pkg)}")
        else:
            server_ok = False
            print(f"  {miss}{pkg}\n            -> pip install -e .[server]  (or run start_anvil.py)")

    repo_root = Path(__file__).resolve().parents[2]
    dist_index = repo_root / "anvil_web" / "dist" / "index.html"
    if dist_index.is_file():
        print(f"  {ok} workbench UI built  [{dist_index}]")
    else:
        print(f"  {miss}workbench UI not built (anvil_web/dist/index.html missing)")
        print("            -> cd anvil_web && npm install && npm run build")
        print("            (the API still works without it; / will 404)")

    print()
    if server_ok:
        print("Start the workbench with:  anvil serve   (or python start_anvil.py)")
    else:
        print("Install server deps, then start with:  anvil serve")
    return 0


# --------------------------------------------------------------------------- #
# serve
# --------------------------------------------------------------------------- #

def cmd_serve(args: argparse.Namespace) -> int:
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        print(
            "anvil serve: server dependencies are not installed.\n"
            "  Install them with:  pip install -e .[server]\n"
            "  Or just run:        python start_anvil.py   (sets up everything)",
            file=sys.stderr,
        )
        return 1
    try:
        from anvil_server.run import main as run_main
    except ImportError:
        print(
            "anvil serve: the anvil_server package is not importable.\n"
            "  It lives at the repo root; install the repo in editable mode:\n"
            "      pip install -e .[server]\n"
            "  Or run from the repo root:  python start_anvil.py",
            file=sys.stderr,
        )
        return 1

    # anvil_server.run.main() parses sys.argv itself -- rebuild it.
    argv = ["anvil-serve"]
    if args.project:
        argv += ["--project", args.project]
    if args.host:
        argv += ["--host", args.host]
    if args.port is not None:
        argv += ["--port", str(args.port)]
    sys.argv = argv
    run_main()
    return 0


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="anvil",
        description="Anvil framework command-line interface.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="print the installed Anvil version")
    sub.add_parser("doctor", help="report environment health and adapter availability")

    p_serve = sub.add_parser("serve", help="start the web workbench server")
    p_serve.add_argument("--project", default=None,
                         help="project dir / .anvil dir / project .db to mount")
    p_serve.add_argument("--host", default=None, help="bind address (default 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=None, help="port (default 8000)")

    args = parser.parse_args(argv)
    if args.command == "version":
        return cmd_version(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "serve":
        return cmd_serve(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
