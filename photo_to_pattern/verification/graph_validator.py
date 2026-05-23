"""Validation for exported stitch graph semantics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from typing import Literal


GraphSeverity = Literal["info", "warning", "error"]

SUPPORTED_EDGE_TYPES = {
    "round_neighbor",
    "worked_into",
    "increase_split",
    "decrease_merge",
    "worked_into_overflow",
    "worked_into_underflow",
}
WORK_CONNECTION_TYPES = {
    "worked_into",
    "increase_split",
    "decrease_merge",
    "worked_into_overflow",
    "worked_into_underflow",
}


@dataclass(frozen=True)
class GraphIssue:
    severity: GraphSeverity
    scope: str
    message: str


@dataclass(frozen=True)
class GraphValidationReport:
    issues: tuple[GraphIssue, ...]

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")


def validate_stitch_graph(graph: dict[str, object]) -> GraphValidationReport:
    """Check graph schema, edge integrity, round continuity, and stitch semantics."""

    issues: list[GraphIssue] = []
    if graph.get("format") != "PhotoToPatternStitchGraph":
        issues.append(GraphIssue("error", "graph", "Unsupported or missing graph format."))
    if graph.get("version") != 1:
        issues.append(GraphIssue("error", "graph", "Unsupported or missing graph version."))

    parts = graph.get("parts")
    if not isinstance(parts, list) or not parts:
        issues.append(GraphIssue("error", "graph", "Graph must contain at least one part."))
        return GraphValidationReport(tuple(issues))

    for part_index, part in enumerate(parts, start=1):
        if not isinstance(part, dict):
            issues.append(GraphIssue("error", f"part[{part_index}]", "Part entry must be an object."))
            continue
        _validate_part(part, issues, part_index)

    return GraphValidationReport(tuple(issues))


def _validate_part(part: dict[str, object], issues: list[GraphIssue], part_index: int) -> None:
    part_id = str(part.get("id") or f"part[{part_index}]")
    nodes = part.get("nodes")
    edges = part.get("edges")
    if not isinstance(nodes, list) or not nodes:
        issues.append(GraphIssue("error", part_id, "Part must contain at least one stitch node."))
        return
    if not isinstance(edges, list):
        issues.append(GraphIssue("error", part_id, "Part edges must be a list."))
        edges = []

    node_ids: set[str] = set()
    node_rounds: dict[str, int] = {}
    rounds: dict[int, list[dict[str, object]]] = defaultdict(list)
    incoming_work: dict[str, list[dict[str, object]]] = defaultdict(list)
    increase_targets: dict[str, set[str]] = defaultdict(set)
    decrease_sources: dict[str, set[str]] = defaultdict(set)

    for node_index, node in enumerate(nodes, start=1):
        if not isinstance(node, dict):
            issues.append(GraphIssue("error", part_id, f"Node {node_index} must be an object."))
            continue
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            issues.append(GraphIssue("error", part_id, f"Node {node_index} is missing an id."))
            continue
        if node_id in node_ids:
            issues.append(GraphIssue("error", part_id, f"Duplicate node id {node_id}."))
        node_ids.add(node_id)
        _validate_node_shape(node, part_id, node_id, issues)
        round_number = _int_or_none(node.get("round_number"))
        if round_number is not None:
            node_rounds[node_id] = round_number
            rounds[round_number].append(node)

    for edge_index, edge in enumerate(edges, start=1):
        if not isinstance(edge, dict):
            issues.append(GraphIssue("error", part_id, f"Edge {edge_index} must be an object."))
            continue
        source = edge.get("from")
        target = edge.get("to")
        edge_type = edge.get("type")
        if not isinstance(source, str) or not isinstance(target, str):
            issues.append(GraphIssue("error", part_id, f"Edge {edge_index} must include string from/to endpoints."))
            continue
        if source not in node_ids:
            issues.append(GraphIssue("error", part_id, f"Edge {edge_index} source {source} does not exist."))
        if target not in node_ids:
            issues.append(GraphIssue("error", part_id, f"Edge {edge_index} target {target} does not exist."))
        if edge_type not in SUPPORTED_EDGE_TYPES:
            issues.append(GraphIssue("error", part_id, f"Edge {edge_index} has unsupported type {edge_type}."))
            continue
        if edge_type in WORK_CONNECTION_TYPES:
            if source in node_rounds and target in node_rounds:
                if node_rounds[target] != node_rounds[source] + 1:
                    issues.append(
                        GraphIssue(
                            "error",
                            part_id,
                            f"Edge {edge_index} must connect work from round {node_rounds[target] - 1} into round {node_rounds[target]}.",
                        )
                    )
                else:
                    incoming_work[target].append(edge)
        if edge_type == "increase_split":
            increase_targets[source].add(target)
        if edge_type == "decrease_merge":
            decrease_sources[target].add(source)

    _validate_rounds(part_id, rounds, edges, issues)
    _validate_work_continuity(part_id, rounds, incoming_work, issues)
    _validate_shaping_semantics(part_id, increase_targets, decrease_sources, issues)


def _validate_node_shape(
    node: dict[str, object],
    part_id: str,
    node_id: str,
    issues: list[GraphIssue],
) -> None:
    for field in ("part_id", "round_number", "stitch_index", "action"):
        if field not in node:
            issues.append(GraphIssue("error", part_id, f"Node {node_id} is missing {field}."))
    position = node.get("position")
    if not isinstance(position, dict):
        issues.append(GraphIssue("error", part_id, f"Node {node_id} is missing position coordinates."))
        return
    for axis in ("x", "y", "z"):
        value = position.get(axis)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            issues.append(GraphIssue("error", part_id, f"Node {node_id} has invalid {axis} coordinate."))


def _validate_rounds(
    part_id: str,
    rounds: dict[int, list[dict[str, object]]],
    edges: object,
    issues: list[GraphIssue],
) -> None:
    if not rounds:
        issues.append(GraphIssue("error", part_id, "No valid round numbers found."))
        return
    for round_number, round_nodes in sorted(rounds.items()):
        stitch_indexes = sorted(_int_or_none(node.get("stitch_index")) for node in round_nodes)
        if any(index is None for index in stitch_indexes):
            issues.append(GraphIssue("error", part_id, f"Round {round_number} has invalid stitch indexes."))
            continue
        expected = list(range(1, len(round_nodes) + 1))
        if stitch_indexes != expected:
            issues.append(GraphIssue("error", part_id, f"Round {round_number} stitch indexes are not contiguous."))

    if not isinstance(edges, list):
        return
    round_node_ids = {round_number: {str(node.get("id")) for node in round_nodes} for round_number, round_nodes in rounds.items()}
    for round_number, node_ids in round_node_ids.items():
        if len(node_ids) <= 1:
            continue
        neighbor_count = 0
        for edge in edges:
            if not isinstance(edge, dict) or edge.get("type") != "round_neighbor":
                continue
            if edge.get("from") in node_ids and edge.get("to") in node_ids:
                neighbor_count += 1
        if neighbor_count < len(node_ids):
            issues.append(GraphIssue("warning", part_id, f"Round {round_number} does not have a closed neighbor ring."))


def _validate_work_continuity(
    part_id: str,
    rounds: dict[int, list[dict[str, object]]],
    incoming_work: dict[str, list[dict[str, object]]],
    issues: list[GraphIssue],
) -> None:
    if len(rounds) < 2:
        return
    first_round = min(rounds)
    for round_number, round_nodes in sorted(rounds.items()):
        if round_number == first_round:
            continue
        missing = [str(node.get("id")) for node in round_nodes if str(node.get("id")) not in incoming_work]
        if missing:
            issues.append(
                GraphIssue(
                    "error",
                    part_id,
                    f"Round {round_number} has {len(missing)} stitch(es) without a worked-into source.",
                )
            )


def _validate_shaping_semantics(
    part_id: str,
    increase_targets: dict[str, set[str]],
    decrease_sources: dict[str, set[str]],
    issues: list[GraphIssue],
) -> None:
    for source, targets in increase_targets.items():
        if len(targets) < 2:
            issues.append(GraphIssue("error", part_id, f"Increase source {source} does not split into multiple targets."))
    for target, sources in decrease_sources.items():
        if len(sources) < 2:
            issues.append(GraphIssue("error", part_id, f"Decrease target {target} does not merge multiple sources."))


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
