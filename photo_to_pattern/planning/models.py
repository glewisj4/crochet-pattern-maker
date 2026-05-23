"""Typed models for planning-card generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ViewKind = Literal["front", "side", "back", "top", "unknown"]


@dataclass(frozen=True)
class PlanningOptions:
    target_height_inches: float = 8.0
    stitches_per_inch: float = 4.0
    head_scale: float = 1.0
    body_scale: float = 1.0
    limb_scale: float = 1.0
    detail_scale: float = 1.0
    reimagine_as_amigurumi: bool = False


@dataclass(frozen=True)
class PlanningView:
    kind: ViewKind
    source_path: Path
    cleaned_path: Path
    inferred: bool = False
    confidence: float = 1.0
    note: str = ""


@dataclass(frozen=True)
class ShapeGuide:
    name: str
    primitive: str
    bbox: tuple[int, int, int, int]
    color: tuple[int, int, int]


@dataclass(frozen=True)
class ProportionGuide:
    label: str
    value: str


@dataclass(frozen=True)
class ConstructionPiece:
    name: str
    quantity: int
    primitive: str
    round_hint: str


@dataclass(frozen=True)
class DesignPart:
    name: str
    primitive: str
    relative_size: tuple[float, float, float]
    color: tuple[int, int, int] | None
    attachment: str
    source: str
    confidence: float


@dataclass(frozen=True)
class DesignDetail:
    name: str
    method: str
    placement: str
    color: tuple[int, int, int] | None
    source: str
    confidence: float


@dataclass(frozen=True)
class DesignUncertainty:
    field: str
    reason: str
    recommendation: str
    severity: str = "review"


@dataclass(frozen=True)
class FeatureCompromise:
    feature: str
    original_treatment: str
    crochet_treatment: str
    reason: str
    severity: str = "review"


@dataclass(frozen=True)
class PlanningModel:
    title: str
    options: PlanningOptions
    views: tuple[PlanningView, ...]
    shape_guides: tuple[ShapeGuide, ...]
    proportions: tuple[ProportionGuide, ...]
    construction: tuple[ConstructionPiece, ...]
    parts: tuple[DesignPart, ...] = ()
    details: tuple[DesignDetail, ...] = ()
    uncertainties: tuple[DesignUncertainty, ...] = ()
    compromises: tuple[FeatureCompromise, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanningResult:
    model: PlanningModel
    card_path: Path
    work_dir: Path
    model_json_path: Path | None = None
    virtual_build_path: Path | None = None
