"""Runtime dashboard data for GUI and reports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from photo_to_pattern.geometric_math import PatternMap
from photo_to_pattern.planning.virtual_build import SimulationReport


@dataclass(frozen=True)
class RuntimeDashboardSnapshot:
    virtual_build_path: Path | None
    node_count: int
    spring_count: int
    accuracy: float
    hausdorff_distance: float
    node_configuration: tuple[str, ...]

    def render(self) -> str:
        lines = [
            f"Virtual build: {self.virtual_build_path}" if self.virtual_build_path else "Virtual build: not generated",
            f"Physics nodes: {self.node_count}",
            f"Physics springs: {self.spring_count}",
            f"Physics accuracy: {round(self.accuracy * 100)}%",
            f"Hausdorff distance: {self.hausdorff_distance:.4f}",
        ]
        if self.node_configuration:
            lines.append("Node configuration:")
            lines.extend(f"- {item}" for item in self.node_configuration)
        return "\n".join(lines)


def build_runtime_dashboard_snapshot(
    pattern_map: PatternMap,
    simulation_report: SimulationReport,
    *,
    virtual_build_path: str | Path | None = None,
) -> RuntimeDashboardSnapshot:
    """Build a compact GUI/report dashboard snapshot from simulation output."""

    counts: dict[str, int] = {}
    for round_spec in pattern_map.rounds:
        counts[round_spec.primitive_id] = counts.get(round_spec.primitive_id, 0) + round_spec.stitch_count
    node_configuration = tuple(f"{part_id}: {count} stitch nodes" for part_id, count in sorted(counts.items()))
    return RuntimeDashboardSnapshot(
        virtual_build_path=Path(virtual_build_path) if virtual_build_path is not None else None,
        node_count=len(simulation_report.build.nodes),
        spring_count=len(simulation_report.build.springs),
        accuracy=simulation_report.accuracy,
        hausdorff_distance=simulation_report.hausdorff_distance,
        node_configuration=node_configuration,
    )
