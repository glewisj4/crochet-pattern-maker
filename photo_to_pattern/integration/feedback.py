"""Simulation feedback loop for density refinement."""

from __future__ import annotations

from dataclasses import dataclass, replace

from photo_to_pattern.core import Mesh, Vertex
from photo_to_pattern.geometric_math import GeometricConfig, PatternMap, RoundSpec
from photo_to_pattern.geometric_math.staggering import stagger_positions
from photo_to_pattern.planning.virtual_build import SimulationConfig, SimulationReport, build_mass_spring_model, simulate_virtual_physics
from photo_to_pattern.vision_voxelizer import VoxelModel


@dataclass(frozen=True)
class RefinementReport:
    pattern_map: PatternMap
    simulation_report: SimulationReport
    iterations: int
    accuracy_target: float
    converged: bool


def refine_pattern_until_accuracy(
    pattern_map: PatternMap,
    target_mesh: Mesh,
    *,
    accuracy_target: float = 0.90,
    max_iterations: int = 4,
    geometric_config: GeometricConfig | None = None,
    simulation_config: SimulationConfig | None = None,
) -> RefinementReport:
    """Scale stitch density and re-simulate until the target accuracy is reached."""

    active_geometry = geometric_config or GeometricConfig()
    active_simulation = simulation_config or SimulationConfig(iterations=20)
    current = pattern_map
    best_report = simulate_virtual_physics(current, target_mesh=target_mesh, config=active_simulation)
    best_pattern = current

    for iteration in range(max_iterations + 1):
        if best_report.accuracy >= accuracy_target:
            return RefinementReport(best_pattern, best_report, iteration, accuracy_target, True)
        if iteration == max_iterations:
            break
        scale = _density_scale(best_report.accuracy, accuracy_target)
        current = _scale_pattern_density(best_pattern, scale, active_geometry)
        candidate = simulate_virtual_physics(current, target_mesh=target_mesh, config=active_simulation)
        if candidate.accuracy >= best_report.accuracy:
            best_pattern = current
            best_report = candidate
        else:
            best_report = candidate
            break

    return RefinementReport(best_pattern, best_report, max_iterations, accuracy_target, best_report.accuracy >= accuracy_target)


def target_mesh_from_pattern(pattern_map: PatternMap) -> Mesh:
    """Create a point-target mesh from a pattern's initial virtual build nodes."""

    build = build_mass_spring_model(pattern_map)
    vertices = tuple(node.position for node in build.nodes)
    if not vertices:
        vertices = (Vertex(0.0, 0.0, 0.0),)
    return Mesh(vertices=vertices, faces=(), source="pattern_node_target")


def target_mesh_from_voxel_model(voxel_model: VoxelModel) -> Mesh:
    """Create a geometry target point cloud from detected 3D primitives."""

    vertices: list[Vertex] = []
    for primitive in voxel_model.primitives:
        cx = primitive.center.x
        cy = primitive.center.y
        cz = primitive.center.z
        rx = max(1.0, primitive.radius_x)
        ry = max(1.0, primitive.radius_y)
        rz = max(1.0, primitive.radius_z)
        for sx, sy, sz in (
            (1.0, 0.0, 0.0),
            (-1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, -1.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, -1.0),
            (0.707, 0.707, 0.0),
            (-0.707, 0.707, 0.0),
            (0.707, -0.707, 0.0),
            (-0.707, -0.707, 0.0),
        ):
            vertices.append(Vertex(cx + sx * rx, cy + sy * ry, cz + sz * rz))
    if not vertices:
        return Mesh(vertices=(Vertex(0.0, 0.0, 0.0),), faces=(), source="empty_voxel_target")
    return _normalize_target_cloud(tuple(vertices), "voxel_model_target")


def _normalize_target_cloud(vertices: tuple[Vertex, ...], source: str) -> Mesh:
    lower = Vertex(min(v.x for v in vertices), min(v.y for v in vertices), min(v.z for v in vertices))
    upper = Vertex(max(v.x for v in vertices), max(v.y for v in vertices), max(v.z for v in vertices))
    center = Vertex((lower.x + upper.x) / 2.0, (lower.y + upper.y) / 2.0, (lower.z + upper.z) / 2.0)
    span = max(upper.x - lower.x, upper.y - lower.y, upper.z - lower.z, 1.0)
    scale = 8.0 / span
    normalized = tuple(Vertex((v.x - center.x) * scale, (v.y - center.y) * scale, (v.z - center.z) * scale) for v in vertices)
    return Mesh(vertices=normalized, faces=(), source=source)


def _density_scale(accuracy: float, target: float) -> float:
    deficit = max(0.0, target - accuracy)
    return min(1.35, 1.0 + deficit * 0.55)


def _scale_pattern_density(pattern_map: PatternMap, scale: float, config: GeometricConfig) -> PatternMap:
    grouped: dict[str, list[RoundSpec]] = {}
    for round_spec in pattern_map.rounds:
        grouped.setdefault(round_spec.primitive_id, []).append(round_spec)

    scaled_rounds: list[RoundSpec] = []
    for primitive_id, rounds in sorted(grouped.items()):
        previous = 0
        for round_spec in sorted(rounds, key=lambda item: item.round_number):
            if round_spec.round_number == 1:
                stitch_count = config.min_stitches
            else:
                requested = max(config.min_stitches, round(round_spec.stitch_count * scale / 6) * 6)
                requested = min(config.max_stitches_per_round, requested)
                delta = max(-config.max_delta_per_round, min(config.max_delta_per_round, requested - previous))
                stitch_count = max(config.min_stitches, previous + delta)
            delta = stitch_count - previous
            action = "mr" if round_spec.round_number == 1 else "inc" if delta > 0 else "dec" if delta < 0 else "even"
            placements = ()
            if action in {"inc", "dec"} and previous > 0:
                placements = stagger_positions(previous, abs(delta), round_spec.round_number)
            scaled_rounds.append(
                replace(
                    round_spec,
                    stitch_count=stitch_count,
                    previous_stitch_count=previous,
                    delta=delta,
                    action=action,  # type: ignore[arg-type]
                    placements=placements,
                )
            )
            previous = stitch_count

    return PatternMap(rounds=tuple(scaled_rounds), warnings=pattern_map.warnings)
