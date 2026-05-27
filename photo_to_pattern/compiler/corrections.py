"""Compiler correction passes for crochet shaping rounds."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from photo_to_pattern.geometric_math import GeometricConfig, PatternMap, RoundSpec
from photo_to_pattern.geometric_math.staggering import stagger_positions


def apply_staggered_increase_corrections(
    pattern_map: PatternMap,
    config: GeometricConfig | None = None,
) -> PatternMap:
    """Canonicalize shaping deltas and stagger placement columns."""

    active_config = config or GeometricConfig()
    grouped: dict[str, list[RoundSpec]] = defaultdict(list)
    for round_spec in pattern_map.rounds:
        grouped[round_spec.primitive_id].append(round_spec)

    corrected: list[RoundSpec] = []
    for primitive_id, rounds in sorted(grouped.items()):
        previous_columns: tuple[int, ...] = ()
        previous_count = 0
        for original in sorted(rounds, key=lambda item: item.round_number):
            delta = original.stitch_count - previous_count
            if delta > active_config.max_delta_per_round:
                delta = active_config.max_delta_per_round
            if delta < -active_config.max_delta_per_round:
                delta = -active_config.max_delta_per_round
            stitch_count = max(active_config.min_stitches, previous_count + delta)
            action = "mr" if original.round_number == 1 else "inc" if delta > 0 else "dec" if delta < 0 else "even"
            placements = ()
            if action in {"inc", "dec"} and previous_count > 0:
                placements = _non_repeating_stagger(previous_count, abs(delta), original.round_number, previous_columns)
            corrected_round = replace(
                original,
                previous_stitch_count=previous_count,
                stitch_count=stitch_count,
                delta=stitch_count - previous_count,
                action=action,  # type: ignore[arg-type]
                placements=placements,
            )
            corrected.append(corrected_round)
            previous_columns = placements
            previous_count = stitch_count

    return PatternMap(rounds=tuple(corrected), warnings=pattern_map.warnings)


def _non_repeating_stagger(
    previous_count: int,
    operations: int,
    round_number: int,
    previous_columns: tuple[int, ...],
) -> tuple[int, ...]:
    if operations <= 0:
        return ()
    placements = stagger_positions(previous_count, operations, round_number)
    if not previous_columns or not set(placements).intersection(previous_columns):
        return placements

    previous_set = set(previous_columns)
    for shift in range(1, previous_count + 1):
        shifted = tuple(sorted((((placement + shift - 1) % previous_count) + 1) for placement in placements))
        if len(set(shifted)) == len(shifted) and not set(shifted).intersection(previous_set):
            return shifted
    available = [column for column in range(1, previous_count + 1) if column not in previous_set]
    if len(available) >= operations:
        return tuple(available[:operations])
    return placements
