"""Typed models for planning-card generation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ViewKind = Literal["front", "side", "back", "top", "unknown"]
SemanticCategory = Literal["Primary Body", "Accents", "Appendages", "Overlaid Garments", "Facial Embroidery", "Insets"]
YarnFiberOption = Literal["acrylic", "cotton", "wool", "chenille", "velvet/chenille"]


@dataclass(frozen=True)
class PlanningOptions:
    target_height_inches: float = 8.0
    stitches_per_inch: float = 4.0
    head_scale: float = 1.0
    body_scale: float = 1.0
    limb_scale: float = 1.0
    detail_scale: float = 1.0
    reimagine_as_amigurumi: bool = False
    infant_safe: bool = False
    gemini_api_key: str = ""
    aesthetic_style: str = "classic"
    yarn_weight: int = 4
    hook_size_mm: float = 3.5
    fiber_type: YarnFiberOption = "acrylic"



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
    pose_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_degrees: float = 0.0
    yarn_type: str = "acrylic"
    color_hex: str = "#e87e40"
    category: SemanticCategory = "Primary Body"



@dataclass(frozen=True)
class DesignDetail:
    name: str
    method: str
    placement: str
    color: tuple[int, int, int] | None
    source: str
    confidence: float
    pose_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_degrees: float = 0.0
    yarn_type: str = "acrylic"
    color_hex: str = "#e87e40"
    category: SemanticCategory = "Accents"



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


def snap_part_to_parent(
    part_pos: tuple[float, float, float],
    parent_pos: tuple[float, float, float],
    parent_w: float,
    parent_h: float,
) -> tuple[float, float, float]:
    """Snap a limb part position to stay within a maximum boundary from its parent center."""
    px, py, pz = part_pos
    parent_x, parent_y, _ = parent_pos

    dx = px - parent_x
    dy = py - parent_y
    dist = math.sqrt(dx * dx + dy * dy)

    r = 1.5 * max(parent_w, parent_h)
    if dist > r:
        if dist == 0:
            return (parent_x, parent_y, pz)
        ux = dx / dist
        uy = dy / dist
        new_x = parent_x + ux * r
        new_y = parent_y + uy * r
        return (new_x, new_y, pz)

    return (px, py, pz)
