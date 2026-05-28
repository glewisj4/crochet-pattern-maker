"""Yarn weight, hook, material, yardage, and elasticity calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from photo_to_pattern.geometric_math import PatternMap


YarnWeight = Literal[1, 2, 3, 4, 5, 6, 7]
FiberType = Literal["acrylic", "cotton", "wool", "chenille"]


@dataclass(frozen=True)
class YarnProfile:
    weight: YarnWeight
    hook_mm: float
    fiber: FiberType
    color_hex: str

    @property
    def strand_thickness_mm(self) -> float:
        return YARN_WEIGHT_BASELINES[self.weight]

    @property
    def spring_coefficient(self) -> float:
        return FIBER_PROPERTIES[self.fiber].spring_coefficient

    @property
    def elasticity(self) -> float:
        return FIBER_PROPERTIES[self.fiber].elasticity


@dataclass(frozen=True)
class FiberPhysics:
    density_g_per_cm3: float
    elasticity: float
    spring_coefficient: float


@dataclass(frozen=True)
class YardageEstimate:
    color_hex: str
    stitches: int
    yards: float
    meters: float


class YarnDynamicsEngine:
    """Facade for yarn profile, yardage, and physics constants used by planning and simulation."""

    def profile(
        self,
        *,
        weight: YarnWeight = 4,
        hook_mm: float = 3.5,
        fiber: FiberType = "acrylic",
        color_hex: str = "#e87e40",
    ) -> YarnProfile:
        return yarn_profile(weight=weight, hook_mm=hook_mm, fiber=fiber, color_hex=color_hex)

    def estimate_yardage_by_color(
        self,
        pattern_map: PatternMap,
        color_profiles: dict[str, YarnProfile] | None = None,
        part_colors: dict[str, str] | None = None,
        default_profile: YarnProfile | None = None,
    ) -> tuple[YardageEstimate, ...]:
        return estimate_yardage_by_color(
            pattern_map,
            color_profiles=color_profiles,
            part_colors=part_colors,
            default_profile=default_profile,
        )

    def stitch_length_mm(self, profile: YarnProfile, *, stitch_type: str = "even") -> float:
        return structural_stitch_length_mm(profile, stitch_type=stitch_type)


YARN_WEIGHT_BASELINES: dict[YarnWeight, float] = {
    1: 1.4,
    2: 1.8,
    3: 2.4,
    4: 3.0,
    5: 4.0,
    6: 5.5,
    7: 7.0,
}

FIBER_PROPERTIES: dict[FiberType, FiberPhysics] = {
    "acrylic": FiberPhysics(density_g_per_cm3=1.17, elasticity=0.18, spring_coefficient=0.18),
    "cotton": FiberPhysics(density_g_per_cm3=1.54, elasticity=0.06, spring_coefficient=0.30),
    "wool": FiberPhysics(density_g_per_cm3=1.31, elasticity=0.22, spring_coefficient=0.14),
    "chenille": FiberPhysics(density_g_per_cm3=0.95, elasticity=0.34, spring_coefficient=0.10),
}


def yarn_profile(
    *,
    weight: YarnWeight = 4,
    hook_mm: float = 3.5,
    fiber: FiberType = "acrylic",
    color_hex: str = "#e87e40",
) -> YarnProfile:
    if weight not in YARN_WEIGHT_BASELINES:
        raise ValueError("Yarn weight must be an integer category from #1 to #7.")
    if hook_mm <= 0:
        raise ValueError("Hook size must be positive millimeters.")
    if fiber not in FIBER_PROPERTIES:
        raise ValueError("Unsupported fiber type.")
    return YarnProfile(weight=weight, hook_mm=hook_mm, fiber=fiber, color_hex=_normalize_hex(color_hex))


def estimate_yardage_by_color(
    pattern_map: PatternMap,
    color_profiles: dict[str, YarnProfile] | None = None,
    part_colors: dict[str, str] | None = None,
    default_profile: YarnProfile | None = None,
) -> tuple[YardageEstimate, ...]:
    profile = default_profile or yarn_profile()
    colors = part_colors or {}
    profiles = color_profiles or {}
    stitches_by_color: dict[str, int] = {}
    length_by_color_mm: dict[str, float] = {}

    for round_spec in pattern_map.rounds:
        color = _normalize_hex(colors.get(round_spec.primitive_id, profile.color_hex))
        active = profiles.get(color, profile)
        stitches_by_color[color] = stitches_by_color.get(color, 0) + round_spec.stitch_count
        length_by_color_mm[color] = length_by_color_mm.get(color, 0.0) + (
            round_spec.stitch_count * structural_stitch_length_mm(active, stitch_type=round_spec.action)
        )

    return tuple(
        YardageEstimate(
            color_hex=color,
            stitches=stitches_by_color[color],
            yards=length_by_color_mm[color] / 914.4,
            meters=length_by_color_mm[color] / 1000.0,
        )
        for color in sorted(length_by_color_mm)
    )


def structural_stitch_length_mm(profile: YarnProfile, *, stitch_type: str = "even") -> float:
    base_loop = (profile.hook_mm * 1.35) + (profile.strand_thickness_mm * 2.4)
    stitch_factor = {
        "mr": 1.18,
        "inc": 1.28,
        "dec": 1.12,
        "even": 1.0,
    }.get(stitch_type, 1.0)
    material_drag = 1.0 + FIBER_PROPERTIES[profile.fiber].density_g_per_cm3 * 0.035
    return base_loop * stitch_factor * material_drag


def _normalize_hex(value: str) -> str:
    cleaned = value.strip().lower()
    if not cleaned.startswith("#"):
        cleaned = "#" + cleaned
    if len(cleaned) != 7:
        raise ValueError(f"Invalid color hex: {value!r}")
    return cleaned
