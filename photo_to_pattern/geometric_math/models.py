"""Typed stitch-map models."""

from dataclasses import dataclass
from typing import Literal

RoundPhase = Literal["start", "increase", "even", "decrease", "finish"]
RoundAction = Literal["mr", "inc", "even", "dec"]


@dataclass(frozen=True)
class GeometricConfig:
    stitch_width_px: float = 8.0
    stitch_aspect_height: float = 0.8
    max_delta_per_round: int = 6
    min_rounds_per_primitive: int = 4
    max_rounds_per_primitive: int = 42
    min_stitches: int = 6
    max_stitches_per_round: int = 72

    @property
    def stitch_height_px(self) -> float:
        return self.stitch_width_px * self.stitch_aspect_height


@dataclass(frozen=True)
class RoundSpec:
    primitive_id: str
    round_number: int
    stitch_count: int
    previous_stitch_count: int
    delta: int
    action: RoundAction
    phase: RoundPhase
    placements: tuple[int, ...]
    radius: float
    note: str = ""


@dataclass(frozen=True)
class PatternMap:
    rounds: tuple[RoundSpec, ...]
    warnings: tuple[str, ...] = ()
