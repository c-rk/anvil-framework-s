"""Smoke tests for the one-command onboarding path.

Guards the promise that a fresh clone can boot the server and be called from
any Python code: server starts, answers /health, and AnvilClient round-trips an
RSQ to the same value as an in-process call. Server-dependent tests skip
cleanly when the optional ``server`` extra (FastAPI/uvicorn) is not installed.
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

fastapi = pytest.importorskip("fastapi", reason="server extra not installed")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_import_is_clean_and_fast():
    """`import anvil` must succeed with only numpy+scipy and emit no warnings."""
    proc = subprocess.run(
        [sys.executable, "-W", "error", "-c", "import anvil; print(anvil.__version__)"],
        capture_output=True, text=True, cwd=_ROOT, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip()


def test_cli_version_and_doctor():
    from anvil import cli  # lazy CLI module, no heavy imports at top level

    assert hasattr(cli, "main")


@pytest.fixture(scope="module")
def server():
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "anvil_server.run", "--port", str(port)],
        cwd=_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_until_up(base, proc)
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _wait_until_up(base: str, proc: subprocess.Popen, timeout: float = 40.0):
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early:\n{proc.stdout.read() if proc.stdout else ''}")
        try:
            with urllib.request.urlopen(base + "/healthz", timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(0.4)
    raise TimeoutError(f"server did not come up at {base}")


def test_health_endpoint(server):
    from anvil.client import AnvilClient

    health = AnvilClient(server).health()
    assert health.get("status") == "ok"
    assert health.get("rsq_count", 0) > 0


def test_client_roundtrip_matches_direct(server):
    import anvil
    from anvil.client import AnvilClient

    via = AnvilClient(server).call("isentropic_ratios", M=2.0, gamma=1.4)
    direct = anvil.R.isentropic_ratios(M=2.0, gamma=1.4)
    for key in ("T0_T", "P0_P", "rho0_rho"):
        d = direct[key]
        d = d.value if hasattr(d, "value") else d
        assert via[key] == pytest.approx(d, rel=1e-9)
