"""AnvilClient -- talk to a running Anvil workbench server over HTTP.

Standard library only (urllib + json): usable from any Python, no extra
dependencies. Start a server first (``python start_anvil.py`` or
``anvil serve``), then:

    from anvil.client import AnvilClient        # or: from anvil import AnvilClient

    c = AnvilClient()                           # http://127.0.0.1:8000
    c.health()                                  # server status + RSQ count
    c.list_rsqs()                               # registry entries (list of dicts)
    c.rsq("isentropic_ratios")                  # full RSQ detail
    c.call("isentropic_ratios", M=2.0, gamma=1.4)
    # -> {'T0_T': 1.8, 'P0_P': 7.824..., 'rho0_rho': 4.346...}

    c.sweep("isentropic_ratios", param="M", values=[1.5, 2.0, 2.5])
    c.solve_system(
        quantities=[{"name": "M", "value": 2.0}, {"name": "gamma", "value": 1.4}],
        relations=["isentropic_ratios"],
    )

Endpoints used (see ``anvil_server/app/main.py`` / ``builder_routes.py``):
    GET  /healthz             POST /api/solve
    GET  /api/registry        POST /api/sweep
    GET  /api/rsq/{name}      POST /api/system/solve
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Sequence

__all__ = ["AnvilClient", "AnvilServerError"]


class AnvilServerError(RuntimeError):
    """The server answered, but with an error (bad input, unknown RSQ, ...)."""

    def __init__(self, status: int, detail: str):
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


class AnvilClient:
    """Minimal HTTP client for the Anvil workbench server.

    Parameters
    ----------
    base_url : str
        Server origin, default ``http://127.0.0.1:8000``.
    timeout : float
        Per-request timeout in seconds (default 60; solves of heavy adapter
        RSQs may need more).
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    # plumbing
    # ------------------------------------------------------------------ #

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        url = self.base_url + path
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # FastAPI errors carry {"detail": "..."} JSON bodies.
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("detail", str(exc))
            except Exception:
                detail = str(exc)
            raise AnvilServerError(exc.code, detail) from None
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise ConnectionError(
                f"Could not reach the Anvil server at {self.base_url} ({exc}). "
                "Is it running? Start it with: python start_anvil.py "
                "(or: anvil serve)"
            ) from None

    def _get(self, path: str) -> Any:
        return self._request("GET", path)

    def _post(self, path: str, body: dict) -> Any:
        return self._request("POST", path, body)

    # ------------------------------------------------------------------ #
    # health
    # ------------------------------------------------------------------ #

    def health(self) -> Dict[str, Any]:
        """GET /healthz -- status, anvil version, tier, RSQ count."""
        return self._get("/healthz")

    def ping(self) -> bool:
        """True when the server is reachable and healthy."""
        try:
            return self.health().get("status") == "ok"
        except ConnectionError:
            return False

    # ------------------------------------------------------------------ #
    # registry
    # ------------------------------------------------------------------ #

    def list_rsqs(self, calc_only: bool = False) -> List[Dict[str, Any]]:
        """GET /api/registry -- registry entries (name, type, domain, ...).

        ``calc_only=True`` returns only RSQs the web calculator can drive.
        """
        qs = "?calc=1" if calc_only else ""
        return self._get(f"/api/registry{qs}")["items"]

    def rsq(self, name: str) -> Dict[str, Any]:
        """GET /api/rsq/{name} -- signature, inputs, outputs, defaults, docs."""
        return self._get(f"/api/rsq/{urllib.parse.quote(name, safe='')}")

    # ------------------------------------------------------------------ #
    # solve / call
    # ------------------------------------------------------------------ #

    def solve(self, name: str, inputs: Optional[Dict[str, Any]] = None,
              si: bool = False, **kwargs: Any) -> Dict[str, Any]:
        """POST /api/solve -- run one RSQ; full response.

        Inputs may be scalars, lists, or ``{"value": x, "unit": "Pa"}`` dicts.
        Returns the full server payload: ``name``, solver ``method``,
        ``results`` ({var: {value, unit, role}}), ``inputs``, ``outputs``.
        """
        merged = dict(inputs or {})
        merged.update(kwargs)
        return self._post("/api/solve", {"name": name, "inputs": merged, "si": si})

    def call(self, name: str, **inputs: Any) -> Dict[str, Any]:
        """Run one RSQ and return just ``{output_name: value}``.

        Mirrors ``anvil.R.<name>(**inputs)``:

            c.call("isentropic_ratios", M=2.0, gamma=1.4)
            # {'T0_T': 1.8, 'P0_P': 7.824..., 'rho0_rho': 4.346...}
        """
        resp = self.solve(name, inputs)
        return {
            k: v["value"]
            for k, v in resp["results"].items()
            if v.get("role") == "output"
        }

    # ------------------------------------------------------------------ #
    # sweep
    # ------------------------------------------------------------------ #

    def sweep(self, name: str, param: str, values: Sequence[float],
              outputs: Optional[Sequence[str]] = None,
              inputs: Optional[Dict[str, Any]] = None,
              si: bool = True) -> Dict[str, Any]:
        """POST /api/sweep -- parametric sweep of one RSQ.

        Returns ``{"name", "param", "data": {var: [..]}, "outputs"}``.
        """
        return self._post("/api/sweep", {
            "name": name,
            "param": param,
            "values": list(values),
            "outputs": list(outputs) if outputs is not None else None,
            "inputs": inputs or {},
            "si": si,
        })

    # ------------------------------------------------------------------ #
    # system builder
    # ------------------------------------------------------------------ #

    def solve_system(self, quantities: Sequence[Dict[str, Any]],
                     relations: Sequence[Any],
                     name: Optional[str] = None,
                     method: Optional[str] = None,
                     max_iter: Optional[int] = None,
                     rtol: Optional[float] = None) -> Dict[str, Any]:
        """POST /api/system/solve -- build and solve a multi-relation System.

        ``quantities``: list of ``{"name": str, "value": float, "unit": str?}``.
        ``relations``: registry names (str) or ``{"name": str, "map": {...}}``
        for input renames. Anvil auto-wires relations by variable name.
        """
        body: Dict[str, Any] = {
            "quantities": list(quantities),
            "relations": list(relations),
        }
        if name is not None:
            body["name"] = name
        if method is not None:
            body["method"] = method
        if max_iter is not None:
            body["max_iter"] = max_iter
        if rtol is not None:
            body["rtol"] = rtol
        return self._post("/api/system/solve", body)

    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:  # pragma: no cover
        return f"AnvilClient(base_url={self.base_url!r})"
