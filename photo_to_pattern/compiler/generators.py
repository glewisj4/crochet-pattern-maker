"""Specialized amigurumi primitive profile generators."""

from __future__ import annotations

from photo_to_pattern.geometric_math import GeometricConfig


def closed_ovoid_profile(rounds: int, peak: int, config: GeometricConfig) -> tuple[int, ...]:
    rounds = max(config.min_rounds_per_primitive, rounds)
    increase = max(2, min(rounds // 3, _delta_steps(config.min_stitches, peak, config) + 1))
    decrease = max(2, increase)
    even = max(0, rounds - increase - decrease)
    counts = _ramp(config.min_stitches, peak, increase)
    counts.extend([peak] * even)
    counts.extend(_ramp(peak, config.min_stitches, decrease + 1)[1:])
    return _force_closed(tuple(counts[:rounds]), config)


def closed_capsule_profile(rounds: int, peak: int, config: GeometricConfig) -> tuple[int, ...]:
    cap = max(2, min(rounds // 4, _delta_steps(config.min_stitches, peak, config) + 1))
    middle = max(1, rounds - cap * 2)
    counts = _ramp(config.min_stitches, peak, cap)
    counts.extend([peak] * middle)
    counts.extend(_ramp(peak, config.min_stitches, cap + 1)[1:])
    return _force_closed(tuple(counts[:rounds]), config)


def curled_tapered_tail_profile(rounds: int, peak: int, config: GeometricConfig) -> tuple[int, ...]:
    base = max(config.min_stitches, min(peak, 18))
    counts = [config.min_stitches]
    current = config.min_stitches
    for index in range(1, max(4, rounds - 3)):
        if index % 2 == 1 and current < base:
            current = min(base, current + 3)
        elif index > rounds * 0.55:
            current = max(config.min_stitches, current - 1)
        counts.append(current)
    counts.extend([max(config.min_stitches, current - 2), config.min_stitches, config.min_stitches])
    return tuple(counts[:rounds])


def inset_ear_profiles(rounds: int, peak: int, config: GeometricConfig) -> tuple[tuple[int, ...], tuple[int, ...]]:
    outer = tuple(reversed(_ramp(config.min_stitches, max(config.min_stitches, min(peak, 18)), max(4, rounds))))
    inner_peak = max(config.min_stitches, round(max(outer) * 0.65))
    inner = tuple(reversed(_ramp(config.min_stitches, inner_peak, max(3, rounds - 2))))
    return outer, inner


def eccentric_oval_muzzle_profile(rounds: int, peak: int, config: GeometricConfig) -> tuple[int, ...]:
    peak = max(config.min_stitches, min(peak, 24))
    counts = _ramp(config.min_stitches, peak, max(2, rounds // 2))
    counts.extend(_ramp(peak, config.min_stitches, max(2, rounds - len(counts) + 1))[1:])
    return tuple(counts[:rounds])


def leaf_cloak_panel_rows(rows: int, widest: int, config: GeometricConfig) -> tuple[int, ...]:
    rows = max(5, rows)
    widest = max(config.min_stitches, widest)
    half = rows // 2
    counts = _ramp(config.min_stitches, widest, half + 1)
    counts.extend(_ramp(widest, config.min_stitches, rows - half)[1:])
    return tuple(counts[:rows])


def _force_closed(profile: tuple[int, ...], config: GeometricConfig) -> tuple[int, ...]:
    counts = list(profile)
    while counts and counts[-1] > config.min_stitches:
        counts.append(max(config.min_stitches, counts[-1] - min(config.max_delta_per_round, counts[-1] - config.min_stitches)))
    if not counts or counts[-1] != config.min_stitches:
        counts.append(config.min_stitches)
    return tuple(counts)


def _delta_steps(start: int, end: int, config: GeometricConfig) -> int:
    return max(1, (max(start, end) - min(start, end) + config.max_delta_per_round - 1) // config.max_delta_per_round)


def _ramp(start: int, end: int, steps: int) -> list[int]:
    if steps <= 1:
        return [end]
    return [round(start + (end - start) * index / (steps - 1)) for index in range(steps)]
