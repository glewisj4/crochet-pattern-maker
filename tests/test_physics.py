import math
import unittest

from photo_to_pattern.core import Face, Mesh, Vertex
from photo_to_pattern.geometric_math import PatternMap, RoundSpec
from photo_to_pattern.planning.virtual_build import (
    STITCH_HEIGHT_TO_WIDTH,
    SimulationConfig,
    build_mass_spring_model,
    calculate_hausdorff_distance,
    hausdorff_distance,
    simulate_virtual_physics,
    volumetric_accuracy,
)


class Phase3PhysicsTests(unittest.TestCase):
    def test_mass_spring_model_uses_anisotropic_stitch_spacing(self):
        pattern_map = PatternMap(rounds=(_round(1, 6, 0, 6, "mr"), _round(2, 6, 6, 0, "even")))

        build = build_mass_spring_model(pattern_map, SimulationConfig(stitch_width=2.0))

        self.assertEqual(len(build.nodes), 12)
        worked = [spring for spring in build.springs if spring.kind == "worked_into"]
        shear = [spring for spring in build.springs if spring.kind == "shear"]
        self.assertEqual(len(worked), 6)
        self.assertEqual(len(shear), 6)
        self.assertTrue(all(math.isclose(spring.rest_length, 2.0 * STITCH_HEIGHT_TO_WIDTH) for spring in worked))

    def test_stuffing_pressure_relaxation_expands_node_cloud(self):
        pattern_map = PatternMap(rounds=(_round(1, 6, 0, 6, "mr"), _round(2, 12, 6, 6, "inc"), _round(3, 12, 12, 0, "even")))
        config = SimulationConfig(iterations=20, stuffing_pressure=0.08)
        initial = build_mass_spring_model(pattern_map, config)
        initial_radius = _mean_radius(initial.nodes)

        report = simulate_virtual_physics(pattern_map, config=config)

        self.assertEqual(report.iterations, 20)
        self.assertGreater(_mean_radius(report.build.nodes), initial_radius)

    def test_hausdorff_distance_is_zero_for_identical_points_and_positive_for_shifted_points(self):
        points = (Vertex(0.0, 0.0, 0.0), Vertex(1.0, 0.0, 0.0), Vertex(0.0, 1.0, 0.0))
        shifted = (Vertex(1.0, 0.0, 0.0), Vertex(2.0, 0.0, 0.0), Vertex(1.0, 1.0, 0.0))

        self.assertEqual(calculate_hausdorff_distance(points, points), 0.0)
        self.assertGreater(calculate_hausdorff_distance(points, shifted), 0.0)

    def test_mesh_hausdorff_distance_and_accuracy_are_bounded(self):
        pattern_map = PatternMap(rounds=(_round(1, 6, 0, 6, "mr"), _round(2, 6, 6, 0, "even")))
        build = build_mass_spring_model(pattern_map)
        target = _mesh_from_nodes(tuple(node.position for node in build.nodes))

        distance = hausdorff_distance(build, target)
        accuracy = volumetric_accuracy(build, target, distance)

        self.assertGreaterEqual(distance, 0.0)
        self.assertGreaterEqual(accuracy, 0.0)
        self.assertLessEqual(accuracy, 1.0)

    def test_simulation_reports_accuracy_against_target_mesh(self):
        pattern_map = PatternMap(rounds=(_round(1, 6, 0, 6, "mr"), _round(2, 6, 6, 0, "even")))
        build = build_mass_spring_model(pattern_map)
        target = _mesh_from_nodes(tuple(node.position for node in build.nodes))

        report = simulate_virtual_physics(pattern_map, target_mesh=target, config=SimulationConfig(iterations=0))

        self.assertGreaterEqual(report.hausdorff_distance, 0.0)
        self.assertGreaterEqual(report.accuracy, 0.0)
        self.assertLessEqual(report.accuracy, 1.0)


def _round(number: int, stitch_count: int, previous: int, delta: int, action: str) -> RoundSpec:
    return RoundSpec(
        primitive_id="body",
        round_number=number,
        stitch_count=stitch_count,
        previous_stitch_count=previous,
        delta=delta,
        action=action,  # type: ignore[arg-type]
        phase="start" if number == 1 else "increase" if delta > 0 else "decrease" if delta < 0 else "even",
        placements=tuple(range(1, abs(delta) + 1)) if action in {"inc", "dec"} else (),
        radius=float(stitch_count),
    )


def _mean_radius(nodes) -> float:
    cx = sum(node.position.x for node in nodes) / len(nodes)
    cy = sum(node.position.y for node in nodes) / len(nodes)
    cz = sum(node.position.z for node in nodes) / len(nodes)
    return sum(
        math.sqrt((node.position.x - cx) ** 2 + (node.position.y - cy) ** 2 + (node.position.z - cz) ** 2)
        for node in nodes
    ) / len(nodes)


def _mesh_from_nodes(points: tuple[Vertex, ...]) -> Mesh:
    vertices = points + (Vertex(0.0, 0.0, 4.0), Vertex(0.0, 0.0, -4.0))
    top = len(vertices) - 2
    bottom = len(vertices) - 1
    ring_count = len(points)
    faces = []
    for index in range(ring_count):
        nxt = (index + 1) % ring_count
        faces.append(Face(top, index, nxt))
        faces.append(Face(bottom, nxt, index))
    mesh = Mesh(vertices=vertices, faces=tuple(faces), source="physics-target")
    if mesh.signed_volume() < 0:
        mesh = Mesh(vertices=mesh.vertices, faces=tuple(Face(face.a, face.c, face.b) for face in mesh.faces), source=mesh.source)
    mesh.validate()
    return mesh


if __name__ == "__main__":
    unittest.main()
