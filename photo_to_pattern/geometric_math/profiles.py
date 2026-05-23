"""Primitive profile sampling."""

from math import ceil, pi, sin

from photo_to_pattern.vision_voxelizer import Primitive3D

from .models import GeometricConfig


def desired_profile(primitive: Primitive3D, config: GeometricConfig) -> tuple[int, ...]:
    """Return desired stitch counts for each round of a primitive."""

    if primitive.kind == "cylinder":
        return _cylinder_profile(primitive, config)
    if primitive.kind == "capsule":
        return _capsule_profile(primitive, config)
    if primitive.kind == "cone":
        return _cone_profile(primitive, config)
    return _ovoid_profile(primitive, config)


def _round_count(height_px: float, config: GeometricConfig) -> int:
    raw = ceil(max(height_px, 1.0) / config.stitch_height_px)
    return max(config.min_rounds_per_primitive, min(config.max_rounds_per_primitive, raw))


def _max_stitches(primitive: Primitive3D, config: GeometricConfig) -> int:
    radius = max(primitive.radius_x, primitive.radius_z, 1.0)
    count = round((2 * pi * radius) / config.stitch_width_px)
    return max(config.min_stitches, min(config.max_stitches_per_round, count))


def _ovoid_profile(primitive: Primitive3D, config: GeometricConfig) -> tuple[int, ...]:
    rounds = _round_count(primitive.radius_y * 2, config)
    peak = _max_stitches(primitive, config)
    counts = []
    for index in range(rounds):
        theta = pi * (index + 0.5) / rounds
        count = max(config.min_stitches, round(peak * sin(theta)))
        counts.append(count)
    counts[0] = config.min_stitches
    counts[-1] = config.min_stitches
    return tuple(counts)


def _cylinder_profile(primitive: Primitive3D, config: GeometricConfig) -> tuple[int, ...]:
    rounds = _round_count(primitive.radius_y * 2, config)
    peak = _max_stitches(primitive, config)
    base_rounds = max(1, min(rounds // 3, ceil((peak - config.min_stitches) / config.max_delta_per_round)))
    counts = [config.min_stitches]
    current = config.min_stitches
    for _ in range(base_rounds):
        current = min(peak, current + config.max_delta_per_round)
        counts.append(current)
    while len(counts) < rounds:
        counts.append(peak)
    return tuple(counts[:rounds])


def _cone_profile(primitive: Primitive3D, config: GeometricConfig) -> tuple[int, ...]:
    rounds = _round_count(primitive.radius_y * 2, config)
    peak = _max_stitches(primitive, config)
    return tuple(
        max(config.min_stitches, round(config.min_stitches + (peak - config.min_stitches) * i / max(1, rounds - 1)))
        for i in range(rounds)
    )


def _capsule_profile(primitive: Primitive3D, config: GeometricConfig) -> tuple[int, ...]:
    rounds = _round_count(primitive.radius_y * 2, config)
    peak = _max_stitches(primitive, config)
    cap = max(2, rounds // 4)
    counts = []
    for index in range(rounds):
        if index < cap:
            theta = (pi / 2) * (index + 1) / cap
            count = round(peak * sin(theta))
        elif index >= rounds - cap:
            theta = (pi / 2) * (rounds - index) / cap
            count = round(peak * sin(theta))
        else:
            count = peak
        counts.append(max(config.min_stitches, count))
    counts[0] = config.min_stitches
    counts[-1] = config.min_stitches
    return tuple(counts)
