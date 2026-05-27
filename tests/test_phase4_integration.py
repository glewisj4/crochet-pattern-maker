import unittest
from pathlib import Path

from photo_to_pattern.core import Face, Mesh, Vertex
from photo_to_pattern.app import PhotoToPatternApp
from photo_to_pattern.geometric_math import PatternMap, RoundSpec
from photo_to_pattern.integration import build_runtime_dashboard_snapshot, refine_pattern_until_accuracy, target_mesh_from_pattern
from photo_to_pattern.planning.virtual_build import SimulationConfig, simulate_virtual_physics
from photo_to_pattern.vision_voxelizer import ImageFrame


class Phase4IntegrationTests(unittest.TestCase):
    def test_feedback_loop_reports_convergence_when_accuracy_target_is_met(self):
        pattern_map = PatternMap(rounds=(_round(1, 6, 0, 6, "mr"), _round(2, 6, 6, 0, "even")))
        target = target_mesh_from_pattern(pattern_map)

        report = refine_pattern_until_accuracy(
            pattern_map,
            target,
            accuracy_target=0.90,
            max_iterations=2,
            simulation_config=SimulationConfig(iterations=0),
        )

        self.assertTrue(report.converged)
        self.assertGreaterEqual(report.simulation_report.accuracy, 0.90)

    def test_feedback_loop_keeps_pattern_arithmetic_balanced(self):
        pattern_map = PatternMap(rounds=(_round(1, 6, 0, 6, "mr"), _round(2, 12, 6, 6, "inc"), _round(3, 12, 12, 0, "even")))
        target = _mesh_from_pattern(pattern_map, scale=1.8)

        report = refine_pattern_until_accuracy(
            pattern_map,
            target,
            accuracy_target=0.95,
            max_iterations=2,
            simulation_config=SimulationConfig(iterations=0),
        )

        for round_spec in report.pattern_map.rounds:
            self.assertEqual(round_spec.stitch_count, round_spec.previous_stitch_count + round_spec.delta)
            self.assertLessEqual(abs(round_spec.delta), 6)

    def test_dashboard_snapshot_exposes_virtual_build_and_node_configuration(self):
        pattern_map = PatternMap(rounds=(_round(1, 6, 0, 6, "mr"), _round(2, 6, 6, 0, "even")))
        simulation = simulate_virtual_physics(pattern_map, config=SimulationConfig(iterations=0))

        snapshot = build_runtime_dashboard_snapshot(pattern_map, simulation, virtual_build_path=Path("build.jpg"))
        text = snapshot.render()

        self.assertEqual(snapshot.virtual_build_path, Path("build.jpg"))
        self.assertIn("Physics nodes: 12", text)
        self.assertIn("body: 12 stitch nodes", text)

    def test_app_runtime_generation_includes_refinement_and_dashboard(self):
        result = PhotoToPatternApp().from_frame(ImageFrame(width=120, height=160, source="synthetic.png"))

        self.assertIsNotNone(result.refinement_report)
        self.assertIsNotNone(result.dashboard_snapshot)
        self.assertGreaterEqual(result.refinement_report.simulation_report.accuracy, 0.90)
        self.assertGreater(result.dashboard_snapshot.node_count, 0)


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


def _mesh_from_pattern(pattern_map: PatternMap, scale: float = 1.0) -> Mesh:
    simulation = simulate_virtual_physics(pattern_map, config=SimulationConfig(iterations=0))
    points = tuple(Vertex(node.position.x * scale, node.position.y * scale, node.position.z * scale) for node in simulation.build.nodes)
    vertices = points + (Vertex(0.0, 0.0, 5.0 * scale), Vertex(0.0, 0.0, -5.0 * scale))
    top = len(vertices) - 2
    bottom = len(vertices) - 1
    faces = []
    for index in range(len(points)):
        nxt = (index + 1) % len(points)
        faces.append(Face(top, index, nxt))
        faces.append(Face(bottom, nxt, index))
    mesh = Mesh(vertices=vertices, faces=tuple(faces), source="phase4-target")
    if mesh.signed_volume() < 0:
        mesh = Mesh(vertices=mesh.vertices, faces=tuple(Face(face.a, face.c, face.b) for face in mesh.faces), source=mesh.source)
    mesh.validate()
    return mesh


if __name__ == "__main__":
    unittest.main()
