#!/usr/bin/env python3
"""One-command bootstrap for the Anvil workbench.

    python start_anvil.py

What it does (fresh clone, zero setup required):
  1. Checks Python >= 3.10.
  2. Creates a `.venv` next to this script (reused on later runs; skipped
     entirely if you already run it from inside an activated venv).
  3. Installs Anvil + the web server into it (`pip install -e .[server]`)
     -- skipped when everything is already importable, so reruns are fast.
  4. Starts the server (equivalent of `python -m anvil_server.run`), waits
     until it answers, then opens your browser at the workbench.

Stop with Ctrl+C.

Options:
    python start_anvil.py --port 9000 --host 0.0.0.0 --project ./my_study
    python start_anvil.py --no-browser
    python start_anvil.py --no-venv     # install into the current Python

On Debian/Ubuntu/WSL, creating a venv needs the system package first:
    sudo apt install python3-venv

Standard library only -- runs on a bare Python install.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
VENV_DIR = REPO_ROOT / ".venv"
MIN_PY = (3, 10)


def say(msg: str) -> None:
    print(f"[anvil] {msg}", flush=True)


def fail(msg: str) -> "None":
    print(f"\n[anvil] ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Step 1: interpreter checks
# --------------------------------------------------------------------------- #

def check_python() -> None:
    if sys.version_info < MIN_PY:
        fail(
            f"Anvil needs Python {MIN_PY[0]}.{MIN_PY[1]} or newer; this is "
            f"Python {sys.version_info.major}.{sys.version_info.minor}.\n"
            "Install a newer Python from https://www.python.org/downloads/ "
            "and run this script with it."
        )


def in_venv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def venv_has_pip(py: Path) -> bool:
    """True when `py -m pip` works (a venv left without pip is unusable)."""
    r = subprocess.run(
        [str(py), "-m", "pip", "--version"],
        capture_output=True, text=True,
    )
    return r.returncode == 0


# --------------------------------------------------------------------------- #
# Step 2: pick / create the target environment
# --------------------------------------------------------------------------- #

def get_target_python(no_venv: bool = False) -> Path:
    """Return the python executable to install into and run the server with."""
    if in_venv():
        say(f"Already inside a virtual environment ({sys.prefix}); using it.")
        return Path(sys.executable)

    if no_venv:
        say(f"--no-venv: installing into the current Python ({sys.executable}).")
        return Path(sys.executable)

    py = venv_python(VENV_DIR)
    if py.exists():
        if venv_has_pip(py):
            say(f"Reusing existing environment: {VENV_DIR}")
            return py
        # A previous failed run (e.g. missing python3-venv) can leave a .venv
        # that has a python but no pip. Recreating it from scratch is the fix.
        say(f"Existing {VENV_DIR} is incomplete (no pip); rebuilding it.")
        shutil.rmtree(VENV_DIR, ignore_errors=True)

    say(f"Creating virtual environment: {VENV_DIR} (one-time, ~30 s)")
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(VENV_DIR)],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not py.exists():
        pyver = f"{sys.version_info.major}.{sys.version_info.minor}"
        output = (result.stdout or "") + (result.stderr or "")
        if "ensurepip" in output or "python3-venv" in output:
            # Debian/Ubuntu/WSL split venv into a separate apt package.
            fail(
                "Your Python is missing the 'venv' module (common on "
                "Debian/Ubuntu/WSL).\n\n"
                f"  Install it:  sudo apt install python{pyver}-venv\n"
                "  Then re-run: python3 start_anvil.py\n\n"
                "Or, if you already have a working pip and would rather install into\n"
                "the current Python instead of a fresh .venv:\n"
                "               python3 start_anvil.py --no-venv"
            )
        fail(
            "Could not create the virtual environment.\n"
            f"Command output:\n{result.stdout}\n{result.stderr}\n"
            f"On Debian/Ubuntu you may need: sudo apt install python{pyver}-venv"
        )

    # Creation reported success but occasionally lands without pip; bootstrap it.
    if not venv_has_pip(py):
        subprocess.run(
            [str(py), "-m", "ensurepip", "--upgrade"],
            capture_output=True, text=True,
        )
        if not venv_has_pip(py):
            pyver = f"{sys.version_info.major}.{sys.version_info.minor}"
            fail(
                "The virtual environment was created but has no pip.\n\n"
                f"  Install:  sudo apt install python{pyver}-venv\n"
                "  Or run:   python3 start_anvil.py --no-venv"
            )
    return py


# --------------------------------------------------------------------------- #
# Step 3: install (only what's missing)
# --------------------------------------------------------------------------- #

def module_missing(py: Path, modules: str) -> bool:
    """True when `import <modules>` fails in the target python."""
    r = subprocess.run(
        [str(py), "-c", f"import {modules}"],
        capture_output=True, text=True,
    )
    return r.returncode != 0


def ensure_installed(py: Path) -> None:
    need_anvil = module_missing(py, "anvil")
    need_server = module_missing(py, "fastapi, uvicorn, anvil_server")
    if not need_anvil and not need_server:
        say("Anvil and server dependencies already installed.")
        return

    what = "anvil + server dependencies" if need_anvil else "server dependencies"
    say(f"Installing {what} (pip install -e .[server]) -- first run takes a few minutes...")
    result = subprocess.run(
        [str(py), "-m", "pip", "install", "-e", ".[server]"],
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        fail(
            "pip install failed (see output above).\n"
            "Check your internet connection, then re-run: python start_anvil.py"
        )
    # Double-check the imports actually work now.
    if module_missing(py, "anvil") or module_missing(py, "fastapi, uvicorn"):
        fail(
            "Install finished but imports still fail. Try deleting the .venv "
            "folder and re-running: python start_anvil.py"
        )
    say("Install complete.")


# --------------------------------------------------------------------------- #
# Step 4: launch server, wait, open browser
# --------------------------------------------------------------------------- #

def wait_for_server(url: str, proc: subprocess.Popen, timeout: float = 90.0) -> bool:
    """Poll `url` until it answers, the server dies, or `timeout` passes."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False  # server exited
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status < 500:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    return False


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Bootstrap and launch the Anvil workbench.",
    )
    ap.add_argument("--host", default=None, help="bind address (default 127.0.0.1)")
    ap.add_argument("--port", type=int, default=None, help="port (default 8000)")
    ap.add_argument(
        "--project", default=None,
        help="project directory / .anvil dir / project .db to mount",
    )
    ap.add_argument(
        "--no-browser", action="store_true",
        help="do not open the web browser automatically",
    )
    ap.add_argument(
        "--no-venv", action="store_true",
        help="install into the current Python instead of creating a .venv "
             "(use when you already manage your own environment)",
    )
    args = ap.parse_args()

    check_python()
    py = get_target_python(args.no_venv)
    ensure_installed(py)

    host = args.host or os.environ.get("ANVIL_HOST", "127.0.0.1")
    port = args.port or int(os.environ.get("ANVIL_PORT", "8000"))

    server_cmd = [str(py), "-m", "anvil_server.run", "--host", host, "--port", str(port)]
    if args.project:
        server_cmd += ["--project", args.project]

    say(f"Starting Anvil server on http://{host}:{port} ...")
    proc = subprocess.Popen(server_cmd, cwd=str(REPO_ROOT))

    # Browsers can't open 0.0.0.0; use loopback for the check/open URL.
    browse_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    base_url = f"http://{browse_host}:{port}"

    try:
        if wait_for_server(f"{base_url}/healthz", proc):
            say(f"Server is up: {base_url}")
            if not args.no_browser:
                say("Opening browser...")
                webbrowser.open(base_url)
            say("Press Ctrl+C to stop.")
        else:
            if proc.poll() is not None:
                fail(
                    f"Server exited early (code {proc.returncode}). "
                    "See the log above for the reason. Common cause: the port "
                    f"{port} is already in use -- try --port {port + 1}."
                )
            say(
                "Server has not answered yet (still starting?). "
                f"Try {base_url} in your browser. Press Ctrl+C to stop."
            )
        proc.wait()
    except KeyboardInterrupt:
        say("Shutting down...")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        say("Stopped.")


if __name__ == "__main__":
    main()
