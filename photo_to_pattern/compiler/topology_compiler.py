"""Compile topology analysis into balanced crochet round maps."""

from __future__ import annotations

from photo_to_pattern.geometric_math import GeometricConfig, PatternMap, RoundSpec
from photo_to_pattern.geometric_math.staggering import stagger_positions
from photo_to_pattern.planning.topology import MeshSegment, TopologyMap

from .corrections import apply_staggered_increase_corrections


def compile_topology_to_pattern(
    topology: TopologyMap,
    config: GeometricConfig | None = None,
) -> PatternMap:
    """Create a strict arithmetic PatternMap from topology segments."""

    active_config = config or GeometricConfig()
    rounds: list[RoundSpec] = []
    warnings: list[str] = []
    segments = [segment for segment in topology.segments if segment.role != "junction"]
    if not segments:
        warnings.append("Topology analysis found no structural body segments; emitted fallback core.")
        segments = (MeshSegment("body_1", "body", tuple(sample.vertex_index for sample in topology.samples), (), 0.0),)

    for segment in segments:
        if segment.role == "appendage" and len(segment.vertex_indices) < 4:
            warnings.append(f"{segment.id}: small appendage segment may need manual attachment review.")
        rounds.extend(_segment_rounds(segment, active_config))

    corrected = apply_staggered_increase_corrections(PatternMap(rounds=tuple(rounds), warnings=tuple(warnings)), active_config)
    return corrected


def _segment_rounds(segment: MeshSegment, config: GeometricConfig) -> tuple[RoundSpec, ...]:
    total_rounds = max(
        config.min_rounds_per_primitive,
        min(config.max_rounds_per_primitive, max(6, len(segment.vertex_indices) // 4)),
    )
    max_stitches = _linear_circle_target(segment, config)
    grow_rounds = max(1, min(total_rounds // 3, (max_stitches - config.min_stitches) // config.max_delta_per_round + 1))
    finish_rounds = grow_rounds
    even_rounds = max(0, total_rounds - grow_rounds - finish_rounds)

    targets: list[int] = []
    current = config.min_stitches
    targets.append(current)
    while len(targets) < grow_rounds and current < max_stitches:
        current = min(max_stitches, current + config.max_delta_per_round)
        targets.append(current)
    while len(targets) < grow_rounds + even_rounds:
        targets.append(current)
    while len(targets) < total_rounds:
        current = max(config.min_stitches, current - config.max_delta_per_round)
        targets.append(current)

    rounds: list[RoundSpec] = []
    previous = 0
    for index, stitch_count in enumerate(targets, start=1):
        delta = stitch_count - previous
        action = "mr" if index == 1 else "inc" if delta > 0 else "dec" if delta < 0 else "even"
        placements = ()
        if action in {"inc", "dec"} and previous > 0:
            placements = stagger_positions(previous, abs(delta), index)
        rounds.append(
            RoundSpec(
                primitive_id=segment.id,
                round_number=index,
                stitch_count=stitch_count,
                previous_stitch_count=previous,
                delta=delta,
                action=action,  # type: ignore[arg-type]
                phase="start" if index == 1 else "increase" if delta > 0 else "decrease" if delta < 0 else "even",
                placements=placements,
                radius=float(stitch_count),
                note="Attach at bifurcation junction." if segment.role == "appendage" else "",
            )
        )
        previous = stitch_count
    return tuple(rounds)


def _linear_circle_target(segment: MeshSegment, config: GeometricConfig) -> int:
    curvature_boost = 6 if segment.mean_curvature > 0 else 0
    raw = config.min_stitches + min(4, max(1, len(segment.vertex_indices) // 8)) * 6 + curvature_boost
    bounded = max(config.min_stitches, min(config.max_stitches_per_round, raw))
    return max(config.min_stitches, round(bounded / 6) * 6)
