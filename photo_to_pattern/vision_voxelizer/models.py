"""Shared typed models for silhouette-to-primitive conversion."""

from dataclasses import dataclass, field
from typing import Literal

PrimitiveKind = Literal["sphere", "ovoid", "cylinder", "cone", "capsule"]
JointHint = Literal["none", "neck", "shoulder", "hip", "elbow", "knee"]
OcclusionKind = Literal["overlap", "hidden_limb", "ambiguous_attachment"]


@dataclass(frozen=True)
class Vec2:
    x: float
    y: float


@dataclass(frozen=True)
class Vec3:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class Axis:
    origin: Vec2
    direction: Vec2
    confidence: float


@dataclass(frozen=True)
class ImageFrame:
    """A dependency-neutral image frame.

    Pixels are optional at this layer so tests and future adapters can supply
    either decoded data or only measurements from another vision backend.
    """

    width: int
    height: int
    source: str
    pixels: object | None = None


@dataclass(frozen=True)
class Silhouette:
    bbox: tuple[int, int, int, int]
    contour: tuple[Vec2, ...]
    area: float
    confidence: float


@dataclass(frozen=True)
class LimbOcclusion:
    kind: OcclusionKind
    location: Vec2
    estimated_depth_order: tuple[str, str] | None
    confidence: float
    note: str


@dataclass(frozen=True)
class Primitive3D:
    id: str
    kind: PrimitiveKind
    center: Vec3
    radius_x: float
    radius_y: float
    radius_z: float
    parent_id: str | None = None
    joint_hint: JointHint = "none"
    confidence: float = 1.0
    metadata: dict[str, str | float | int | bool] = field(default_factory=dict)


@dataclass(frozen=True)
class VoxelModel:
    primitives: tuple[Primitive3D, ...]
    occlusions: tuple[LimbOcclusion, ...] = ()
    symmetry_axis: Axis | None = None
    scale_hint: float | None = None
    notes: tuple[str, ...] = ()

