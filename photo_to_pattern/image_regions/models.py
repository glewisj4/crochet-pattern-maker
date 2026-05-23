"""Models for color-region feature extraction."""

from dataclasses import dataclass
from typing import Literal

RegionKind = Literal["body", "face_mask", "eye", "leg", "unknown"]


@dataclass(frozen=True)
class ColorRegion:
    kind: RegionKind
    bbox: tuple[int, int, int, int]
    area: int
    centroid: tuple[float, float]
    average_color: tuple[int, int, int]
    confidence: float
    contour: tuple[tuple[float, float], ...] = ()
    major_axis: tuple[tuple[float, float], tuple[float, float]] | None = None
    centerline: tuple[tuple[float, float], ...] = ()
    median_thickness: float | None = None


@dataclass(frozen=True)
class CharacterAnalysis:
    source: str
    image_size: tuple[int, int]
    foreground_bbox: tuple[int, int, int, int]
    regions: tuple[ColorRegion, ...]
    warnings: tuple[str, ...] = ()

    def regions_of_kind(self, kind: RegionKind) -> tuple[ColorRegion, ...]:
        return tuple(region for region in self.regions if region.kind == kind)
