"""Export a local stitch graph from generated rounds."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path

from photo_to_pattern.geometric_math import PatternMap, RoundSpec


@dataclass(frozen=True)
class StitchNode:
    id: str
    part_id: str
    round_number: int
    stitch_index: int
    action: str
    position: dict[str, float]


@dataclass(frozen=True)
class StitchEdge:
    source: str
    target: str
    type: str


def export_stitch_graph(pattern_map: PatternMap, output_path: str | Path, title: str) -> Path:
    """Write a connected stitch graph JSON for future 3D simulation backends."""

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(to_stitch_graph(pattern_map, title), indent=2, sort_keys=True), encoding="utf-8")
    return destination


def to_stitch_graph(pattern_map: PatternMap, title: str) -> dict[str, object]:
    grouped: dict[str, list[RoundSpec]] = defaultdict(list)
    for round_spec in pattern_map.rounds:
        grouped[round_spec.primitive_id].append(round_spec)

    parts = []
    for primitive_id, rounds in sorted(grouped.items()):
        parts.append(_part_graph(primitive_id, sorted(rounds, key=lambda item: item.round_number)))
    return {
        "format": "PhotoToPatternStitchGraph",
        "version": 1,
        "title": title,
        "parts": parts,
    }


def _part_graph(primitive_id: str, rounds: list[RoundSpec]) -> dict[str, object]:
    nodes: list[StitchNode] = []
    edges: list[StitchEdge] = []
    previous_ids: list[str] = []
    max_stitches = max((round_spec.stitch_count for round_spec in rounds), default=1)

    for round_index, round_spec in enumerate(rounds):
        current_ids = []
        radius = max(0.2, round_spec.stitch_count / max_stitches)
        z = round_index / max(1, len(rounds) - 1)
        for stitch_index in range(round_spec.stitch_count):
            angle = 2 * math.pi * stitch_index / max(1, round_spec.stitch_count)
            node_id = f"{primitive_id}:R{round_spec.round_number}:S{stitch_index + 1}"
            current_ids.append(node_id)
            nodes.append(
                StitchNode(
                    id=node_id,
                    part_id=primitive_id,
                    round_number=round_spec.round_number,
                    stitch_index=stitch_index + 1,
                    action=round_spec.action,
                    position={
                        "x": round(math.cos(angle) * radius, 4),
                        "y": round(math.sin(angle) * radius, 4),
                        "z": round(z, 4),
                    },
                )
            )
            if stitch_index > 0:
                edges.append(StitchEdge(current_ids[stitch_index - 1], node_id, "round_neighbor"))

        if len(current_ids) > 1:
            edges.append(StitchEdge(current_ids[-1], current_ids[0], "round_neighbor"))
        if previous_ids:
            edges.extend(_worked_into_edges(previous_ids, current_ids, round_spec))
        previous_ids = current_ids

    return {
        "id": primitive_id,
        "nodes": [asdict(node) for node in nodes],
        "edges": [{"from": edge.source, "to": edge.target, "type": edge.type} for edge in edges],
    }


def _worked_into_edges(
    previous_ids: list[str],
    current_ids: list[str],
    round_spec: RoundSpec,
) -> list[StitchEdge]:
    if round_spec.action == "inc":
        return _increase_edges(previous_ids, current_ids, round_spec.placements)
    if round_spec.action == "dec":
        return _decrease_edges(previous_ids, current_ids, round_spec.placements)
    return _even_edges(previous_ids, current_ids)


def _even_edges(previous_ids: list[str], current_ids: list[str]) -> list[StitchEdge]:
    edges = []
    for index, node_id in enumerate(current_ids):
        previous = previous_ids[min(index, len(previous_ids) - 1)]
        edges.append(StitchEdge(previous, node_id, "worked_into"))
    return edges


def _increase_edges(
    previous_ids: list[str],
    current_ids: list[str],
    placements: tuple[int, ...],
) -> list[StitchEdge]:
    placement_set = set(placements)
    edges: list[StitchEdge] = []
    current_index = 0
    for previous_index, previous in enumerate(previous_ids, start=1):
        repeats = 2 if previous_index in placement_set else 1
        for repeat in range(repeats):
            if current_index >= len(current_ids):
                break
            edge_type = "increase_split" if repeats == 2 else "worked_into"
            edges.append(StitchEdge(previous, current_ids[current_index], edge_type))
            current_index += 1
    while current_index < len(current_ids):
        previous = previous_ids[min(len(previous_ids) - 1, current_index % len(previous_ids))]
        edges.append(StitchEdge(previous, current_ids[current_index], "worked_into_overflow"))
        current_index += 1
    return edges


def _decrease_edges(
    previous_ids: list[str],
    current_ids: list[str],
    placements: tuple[int, ...],
) -> list[StitchEdge]:
    placement_set = set(placements)
    edges: list[StitchEdge] = []
    current_index = 0
    consumed: set[int] = set()
    total_previous = len(previous_ids)
    required_pairs = max(0, len(previous_ids) - len(current_ids))
    pairs_made = 0

    for previous_index in sorted(placement_set):
        if pairs_made >= required_pairs or current_index >= len(current_ids) or previous_index < 1 or previous_index > total_previous:
            continue
        next_index = (previous_index % total_previous) + 1
        if previous_index in consumed or next_index in consumed:
            continue
        edges.append(StitchEdge(previous_ids[previous_index - 1], current_ids[current_index], "decrease_merge"))
        edges.append(StitchEdge(previous_ids[next_index - 1], current_ids[current_index], "decrease_merge"))
        consumed.add(previous_index)
        consumed.add(next_index)
        current_index += 1
        pairs_made += 1

    probe = 1
    while pairs_made < required_pairs and current_index < len(current_ids) and probe <= total_previous:
        next_index = (probe % total_previous) + 1
        if probe not in consumed and next_index not in consumed:
            edges.append(StitchEdge(previous_ids[probe - 1], current_ids[current_index], "decrease_merge"))
            edges.append(StitchEdge(previous_ids[next_index - 1], current_ids[current_index], "decrease_merge"))
            consumed.add(probe)
            consumed.add(next_index)
            current_index += 1
            pairs_made += 1
        probe += 1

    for previous_index in range(1, total_previous + 1):
        if previous_index in consumed or current_index >= len(current_ids):
            continue
        previous = previous_ids[previous_index - 1]
        edges.append(StitchEdge(previous, current_ids[current_index], "worked_into"))
        consumed.add(previous_index)
        current_index += 1

    while current_index < len(current_ids):
        previous = previous_ids[current_index % total_previous]
        edges.append(StitchEdge(previous, current_ids[current_index], "worked_into_underflow"))
        current_index += 1
    return edges
