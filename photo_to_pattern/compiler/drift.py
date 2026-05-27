"""Spiral torque drift compensation for compiled crochet rounds."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from photo_to_pattern.geometric_math import PatternMap, RoundSpec

from .models import AlignmentOffset, CompiledRound


def calculate_spiral_drift_offsets(
    rounds: tuple[RoundSpec, ...],
    *,
    degrees_per_round: float = 3.5,
) -> tuple[AlignmentOffset, ...]:
    """Return deterministic stitch offsets for spiral-round visual alignment."""

    offsets: list[AlignmentOffset] = []
    grouped: dict[str, list[RoundSpec]] = defaultdict(list)
    for round_spec in rounds:
        grouped[round_spec.primitive_id].append(round_spec)

    for primitive_id, primitive_rounds in sorted(grouped.items()):
        accumulated_degrees = 0.0
        for round_spec in sorted(primitive_rounds, key=lambda item: item.round_number):
            accumulated_degrees += degrees_per_round
            stitch_count = max(1, round_spec.stitch_count)
            offset = round((accumulated_degrees / 360.0) * stitch_count) % stitch_count
            offsets.append(
                AlignmentOffset(
                    primitive_id=primitive_id,
                    round_number=round_spec.round_number,
                    stitch_count=stitch_count,
                    offset_stitches=offset,
                    drift_degrees=round(accumulated_degrees, 4),
                )
            )
    return tuple(offsets)


def compile_rounds_with_alignment(pattern_map: PatternMap) -> tuple[CompiledRound, ...]:
    """Convert a PatternMap into compiler IR with alignment offsets attached."""

    offsets = {
        (offset.primitive_id, offset.round_number): offset
        for offset in calculate_spiral_drift_offsets(pattern_map.rounds)
    }
    compiled: list[CompiledRound] = []
    for round_spec in pattern_map.rounds:
        action = "MR" if round_spec.action == "mr" else round_spec.action.upper()
        compiled.append(
            CompiledRound(
                primitive_id=round_spec.primitive_id,
                round_number=round_spec.round_number,
                from_count=round_spec.previous_stitch_count,
                to_count=round_spec.stitch_count,
                action=action,  # type: ignore[arg-type]
                delta=round_spec.delta,
                placements=round_spec.placements,
                alignment_offset=offsets.get((round_spec.primitive_id, round_spec.round_number)),
            )
        )
    return tuple(compiled)


def inject_alignment_offset_stitches(pattern_map: PatternMap) -> PatternMap:
    """Rotate shaping placements by calculated drift offsets without changing counts."""

    offsets = {
        (offset.primitive_id, offset.round_number): offset
        for offset in calculate_spiral_drift_offsets(pattern_map.rounds)
    }
    adjusted: list[RoundSpec] = []
    for round_spec in pattern_map.rounds:
        offset = offsets.get((round_spec.primitive_id, round_spec.round_number))
        placements = round_spec.placements
        if offset is not None and placements and round_spec.previous_stitch_count > 0:
            shift = offset.offset_stitches
            placements = tuple(
                sorted(
                    {
                        ((placement + shift - 1) % round_spec.previous_stitch_count) + 1
                        for placement in placements
                    }
                )
            )
            if len(placements) < len(round_spec.placements):
                placements = _fill_unique_placements(placements, len(round_spec.placements), round_spec.previous_stitch_count)
        adjusted.append(replace(round_spec, placements=placements))
    return PatternMap(rounds=tuple(adjusted), warnings=pattern_map.warnings)


def _fill_unique_placements(existing: tuple[int, ...], target_count: int, stitch_count: int) -> tuple[int, ...]:
    placements = list(existing)
    used = set(placements)
    probe = 1
    while len(placements) < target_count and probe <= stitch_count:
        if probe not in used:
            placements.append(probe)
            used.add(probe)
        probe += 1
    return tuple(sorted(placements))
