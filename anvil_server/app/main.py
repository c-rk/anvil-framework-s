"""FastAPI application for the Anvil framework (Milestone M3).

Endpoints
---------
GET  /healthz            liveness + tier info
GET  /api/registry       list RSQs (name, type, domain, description, tags)
GET  /api/rsq/{name}     signature/inputs/outputs/defaults/description (+latex)
POST /api/solve          run anvil.solve, return values + units + method
POST /api/sweep          run a parametric sweep, return SweepResult data
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import examples_data, executor
from .builder_routes import router as builder_router
from .canvas_routes import router as canvas_router
from .config import settings
from .ws_routes import router as ws_router
from .schemas import (
    CsvRequest,
    CsvResponse,
    ExampleListResponse,
    HealthResponse,
    RefreshResponse,
    RegistryResponse,
    RsqDetail,
    SolveRequest,
    SolveResponse,
    SweepRequest,
    SweepResponse,
    VizConvergenceRequest,
    VizResponse,
    VizSweepRequest,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Anvil API",
        version="1.0.0",
        description="HTTP wrapper over the Anvil RSQ registry and solver (M3).",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------ #
    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse(
            status="ok",
            anvil_version=executor.anvil_version(),
            tier=settings.tier,
            native_only=settings.native_only,
            rsq_count=executor.rsq_count(),
        )

    # ------------------------------------------------------------------ #
    @app.get("/api/registry", response_model=RegistryResponse)
    async def get_registry(
        response: Response,
        calc: int = Query(
            default=0, description="When 1, return only calculator_ok RSQs"
        ),
    ) -> RegistryResponse:
        # Registry is read live from the store; never cache it so newly-pushed
        # RSQs show up immediately.
        response.headers["Cache-Control"] = "no-store"
        items = executor.list_registry(calc_only=bool(calc))
        return RegistryResponse(
            tier=settings.tier,
            native_only=settings.native_only,
            count=len(items),
            items=items,  # type: ignore[arg-type]
        )

    # ------------------------------------------------------------------ #
    @app.post("/api/registry/refresh", response_model=RefreshResponse)
    async def post_registry_refresh() -> RefreshResponse:
        # Re-seed if needed and rebuild the live namespaces so RSQs added to the
        # DB after server start become solvable in-process.
        status = executor.refresh_registry()
        return RefreshResponse(**status)

    # ------------------------------------------------------------------ #
    @app.get("/api/rsq/{name}", response_model=RsqDetail)
    async def get_rsq(name: str, response: Response) -> RsqDetail:
        response.headers["Cache-Control"] = "no-store"
        detail = executor.describe(name)
        if detail is None:
            raise HTTPException(status_code=404, detail=f"RSQ '{name}' not found")
        return RsqDetail(**detail)

    # ------------------------------------------------------------------ #
    @app.post("/api/solve", response_model=SolveResponse)
    async def post_solve(req: SolveRequest) -> SolveResponse:
        try:
            result = executor.solve(req.name, req.inputs, si=req.si)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"RSQ '{req.name}' not found")
        except Exception as exc:  # solver / value errors -> 400
            raise HTTPException(status_code=400, detail=f"Solve failed: {exc}")
        return SolveResponse(**result)

    # ------------------------------------------------------------------ #
    @app.post("/api/sweep", response_model=SweepResponse)
    async def post_sweep(req: SweepRequest) -> SweepResponse:
        try:
            result = executor.sweep(
                req.name, req.param, req.values, req.outputs, req.inputs, si=req.si
            )
        except KeyError:
            raise HTTPException(status_code=404, detail=f"RSQ '{req.name}' not found")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Sweep failed: {exc}")
        return SweepResponse(**result)

    # ------------------------------------------------------------------ #
    @app.post("/api/data/csv", response_model=CsvResponse)
    async def post_csv(req: CsvRequest) -> CsvResponse:
        try:
            parsed = executor.parse_csv(
                req.text, max_rows=req.max_rows or executor.MAX_CSV_ROWS
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"CSV parse failed: {exc}")
        return CsvResponse(**parsed)

    # ------------------------------------------------------------------ #
    @app.get("/api/examples", response_model=ExampleListResponse)
    async def get_examples() -> ExampleListResponse:
        items = examples_data.list_examples()
        return ExampleListResponse(count=len(items), items=items)  # type: ignore[arg-type]

    @app.get("/api/examples/{example_id}")
    async def get_example(example_id: str):
        ex = examples_data.get_example(example_id)
        if ex is None:
            raise HTTPException(
                status_code=404, detail=f"Example '{example_id}' not found"
            )
        return ex

    # ------------------------------------------------------------------ #
    @app.post("/api/viz/sweep", response_model=VizResponse)
    async def post_viz_sweep(req: VizSweepRequest):
        if not executor.matplotlib_available():
            raise HTTPException(
                status_code=501,
                detail="matplotlib not installed; use the frontend SVG charts.",
            )
        try:
            out = executor.render_sweep_png(
                req.name, req.param, req.values, req.outputs, req.inputs, si=req.si
            )
        except KeyError:
            raise HTTPException(status_code=404, detail=f"RSQ '{req.name}' not found")
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"Viz failed: {exc}")
        return VizResponse(**out)

    @app.post("/api/viz/convergence", response_model=VizResponse)
    async def post_viz_convergence(req: VizConvergenceRequest):
        if not executor.matplotlib_available():
            raise HTTPException(
                status_code=501,
                detail="matplotlib not installed; use the frontend SVG charts.",
            )
        try:
            out = executor.render_convergence_png(req.name, req.inputs, req.method)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"RSQ '{req.name}' not found")
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"Viz failed: {exc}")
        return VizResponse(**out)

    # WebSocket: live solver-residual streaming (WS /ws/solve).
    app.include_router(ws_router)

    # System-builder: POST /api/system/solve + WS /ws/system/solve.
    app.include_router(builder_router)

    # Canvas <-> python-script bridge: /api/canvases*, /api/example-scripts*.
    app.include_router(canvas_router)

    # ------------------------------------------------------------------ #
    # Static content: reference wiki + built SPA. Mounted last so all API
    # routes above keep precedence. With these in place a single
    # `python -m anvil_server.run` serves the whole app at one origin.
    repo_root = Path(__file__).resolve().parents[2]

    docs_dir = repo_root / "docs"
    if docs_dir.is_dir():
        @app.get("/wiki", include_in_schema=False)
        async def wiki_root() -> RedirectResponse:
            return RedirectResponse(url="/wiki/ANVIL_WIKI.html")

        app.mount("/wiki", StaticFiles(directory=str(docs_dir)), name="wiki")

    dist_dir = repo_root / "anvil_web" / "dist"
    if dist_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="spa")

    return app


# Module-level app for `uvicorn anvil_server.app.main:app`.
app = create_app()
