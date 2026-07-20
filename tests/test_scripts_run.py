"""Pytest bridge for Anvil's script-style test files.

Most test files in this directory are runnable scripts that print
``Results: N passed, M failed`` and exit non-zero on failure, rather than
exposing ``def test_*`` functions. Plain ``pytest`` would silently skip them.

This module runs each such script in a subprocess and asserts it finished
cleanly (exit 0 and no reported failures), so a single ``pytest`` invocation
-- and therefore CI -- exercises the whole suite.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).parent

# Script-style suites (each prints a "Results:" line). Pytest-native files and
# this bridge itself are intentionally excluded to avoid double-running.
_EXCLUDE = {"test_scripts_run.py", "test_smoke_onboarding.py"}
_SCRIPTS = sorted(
    p.name
    for p in _HERE.glob("test_*.py")
    if p.name not in _EXCLUDE
)

_FAIL_RE = re.compile(r"Results:\s*\d+\s+passed,\s*(\d+)\s+failed")


@pytest.mark.parametrize("script", _SCRIPTS)
def test_script_suite_passes(script: str) -> None:
    proc = subprocess.run(
        [sys.executable, str(_HERE / script)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    output = proc.stdout + proc.stderr

    # Surface the child's own summary in pytest's failure report.
    m = _FAIL_RE.search(output)
    reported_failures = int(m.group(1)) if m else None

    if proc.returncode != 0 or (reported_failures or 0) > 0:
        tail = "\n".join(output.splitlines()[-40:])
        pytest.fail(
            f"{script} failed (exit {proc.returncode}, "
            f"reported_failures={reported_failures}):\n{tail}"
        )
