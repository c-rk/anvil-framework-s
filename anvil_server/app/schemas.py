"""Pydantic request/response models for the Anvil backend.

The response shapes mirror the actual Anvil objects defined in
``src/anvil/system.py`` and ``src/anvil/inspect.py``:

  * ``Result.to_json()``  -> ``{name: {"value": float, "unit": str}}``
  * ``Result.to_dict()``  -> ``{name: float}``
  * ``Result.method``     -> solver method string ("forward", "gauss_seidel", ...)
  * ``anvil.check(name)`` -> dict with inputs/outputs/defaults/domain/description
  * ``SweepResult.to_json()`` -> ``{param: [..], output: [..], ...}``
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


# ----------------------------- Registry -------------------------------------

class RegistryEntry(BaseModel):
    name: str
    type: str = Field(description="R (Relation), S (System), or Q (Quantity)")
    domain: str = ""
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    calculator_ok: bool = Field(
        default=False,
        description="Plain Relation the web calculator can drive with scalar inputs",
    )
    array_input: bool = Field(
        default=False,
        description="Takes a 1-D array / time-series as a primary input",
    )
    adapter: bool = Field(
        default=False, description="Wraps an external solver/library (adapter)"
    )
    project: bool = Field(
        default=False,
        description="Comes from a mounted project registry (--project)",
    )


class RegistryResponse(BaseModel):
    tier: str
    native_only: bool
    count: int
    items: List[RegistryEntry]


# ----------------------------- RSQ detail -----------------------------------

class RsqInput(BaseModel):
    name: str
    default: Optional[Any] = None
    unit: str = ""
    desc: str = ""


class RsqOutput(BaseModel):
    name: str
    unit: str = ""
    desc: str = ""


class RsqDetail(BaseModel):
    name: str
    type: str
    domain: str = ""
    description: str = ""
    version: str = ""
    signature: str = Field(description="Python-style call signature, used when no LaTeX is present")
    latex: Optional[str] = Field(default=None, description="LaTeX formula if the RSQ metadata provides one")
    inputs: List[RsqInput] = Field(default_factory=list)
    outputs: List[RsqOutput] = Field(default_factory=list)
    defaults: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    calculator_ok: bool = False
    array_input: bool = False
    adapter: bool = False


# ----------------------------- Solve ----------------------------------------

# An input value may be: a bare scalar, a list/array (time-series), or a
# {"value": x|[..], "unit": "Pa"} object.
InputValue = Union[float, int, str, bool, List[Any], Dict[str, Any]]


class SolveRequest(BaseModel):
    name: str
    inputs: Dict[str, InputValue] = Field(default_factory=dict)
    si: bool = False


class ResultValue(BaseModel):
    value: Any
    unit: str = ""
    role: str = Field(default="output", description="'input' or 'output'")
    note: Optional[str] = Field(
        default=None,
        description="Serialization note, e.g. array downsampling info",
    )


class SolveResponse(BaseModel):
    name: str
    method: str
    results: Dict[str, ResultValue]
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)


# ----------------------------- Sweep ----------------------------------------

class SweepRequest(BaseModel):
    name: str
    param: str
    values: List[float]
    outputs: Optional[List[str]] = None
    # Extra FIXED (non-swept) inputs to set on the system/relation before
    # sweeping. Each may be a scalar, array, or {"value", "unit"} object.
    inputs: Dict[str, InputValue] = Field(default_factory=dict)
    si: bool = True


class SweepResponse(BaseModel):
    name: str
    param: str
    data: Dict[str, List[Any]]
    outputs: List[str] = Field(default_factory=list)


# ----------------------------- Misc -----------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    anvil_version: str
    tier: str
    native_only: bool
    rsq_count: int


# ----------------------------- Registry refresh -----------------------------

class RefreshResponse(BaseModel):
    status: str = "ok"
    rsq_count: int


# ----------------------------- CSV ------------------------------------------

class CsvRequest(BaseModel):
    text: str = Field(description="Raw CSV text")
    max_rows: Optional[int] = Field(
        default=None, description="Cap on rows kept in 'data' (downsampled beyond)"
    )


class CsvResponse(BaseModel):
    columns: List[str]
    rows: int
    preview: List[Dict[str, Any]]
    data: Dict[str, List[Any]]
    note: Optional[str] = None


# ----------------------------- Examples -------------------------------------

class ExampleSummary(BaseModel):
    id: str
    name: str
    description: str = ""
    domain: str = ""
    relations: List[str] = Field(default_factory=list)
    array_input: bool = False
    n_quantities: int = 0


class ExampleListResponse(BaseModel):
    count: int
    items: List[ExampleSummary]


# ----------------------------- Viz ------------------------------------------

class VizSweepRequest(BaseModel):
    name: str
    param: str
    values: List[float]
    outputs: Optional[List[str]] = None
    inputs: Dict[str, InputValue] = Field(default_factory=dict)
    si: bool = True


class VizConvergenceRequest(BaseModel):
    name: str
    inputs: Dict[str, InputValue] = Field(default_factory=dict)
    method: Optional[str] = None


class VizResponse(BaseModel):
    png_base64: str
