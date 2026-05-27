import math
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from photo_to_pattern.compiler import (
    apply_staggered_increase_corrections,
    calculate_spiral_drift_offsets,
    compile_rounds_with_alignment,
    compile_topology_to_pattern,
    inject_alignment_offset_stitches,
    validate_strict_pattern,
)
from photo_to_pattern.core import Face, Mesh, Vertex, build_watertight_mesh_from_orthographic, load_orthographic_views
from photo_to_pattern.geometric_math import GeometricConfig, PatternMap, RoundSpec
from photo_to_pattern.planning.topology import analyze_mesh_topology, calculate_gaussian_curvature
from photo_to_pattern.verification import export_strict_pattern, validate_stitch_graph
from photo_to_pattern.verification.stitch_graph import to_stitch_graph


class Phase2CompilerTests(unittest.TestCase):
    def test_gaussian_curvature_integrates_near_four_pi(self):
        mesh = _ellipsoid_mesh()

        samples = calculate_gaussian_curvature(mesh)
        integrated = sum(sample.gaussian_curvature * sample.area for sample in samples)

        self.assertTrue(all(math.isfinite(sample.gaussian_curvature) for sample in samples))
        self.assertAlmostEqual(integrated, 4.0 * math.pi, delta=0.45)
        self.assertTrue(any(sample.role == "increase" for sample in samples))

    def test_bifurcation_segmentation_finds_junction_and_appendage(self):
        topology = analyze_mesh_topology(_bifurcated_cone_mesh())

        roles = {segment.role for segment in topology.segments}

        self.assertIn("junction", roles)
        self.assertIn("body", roles)
        self.assertIn("appendage", roles)
        self.assertTrue(topology.bifurcation_vertices)

    def test_plain_ellipsoid_is_not_misclassified_as_all_junction(self):
        topology = analyze_mesh_topology(_ellipsoid_mesh())

        self.assertFalse(topology.bifurcation_vertices)
        self.assertEqual({segment.role for segment in topology.segments}, {"body"})

    def test_strict_parser_accepts_exported_balanced_rounds(self):
        pattern_map = PatternMap(
            rounds=(
                _round(1, 6, 0, 6, "mr", ()),
                _round(2, 12, 6, 6, "inc", (1, 2, 3, 4, 5, 6)),
                _round(3, 12, 12, 0, "even", ()),
                _round(4, 6, 12, -6, "dec", (1, 3, 5, 7, 9, 11)),
            )
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output = export_strict_pattern(pattern_map, Path(temp_dir) / "test.cr", "strict-test")

            report = validate_strict_pattern(output.read_text(encoding="utf-8"))

            self.assertTrue(report.passed)
            self.assertEqual(len(report.rounds), 4)

    def test_strict_parser_rejects_bad_arithmetic_and_placements(self):
        script = "\n".join(
            (
                'FORMAT "PhotoToPatternStrict" 1',
                'TITLE "bad"',
                "TERMINOLOGY US",
                "STYLE SPIRAL_ROUNDS",
                'PART "body"',
                "ROUND 1 FROM 0 TO 6 ACTION MR DELTA 6 PLACEMENTS -",
                "ROUND 2 FROM 6 TO 14 ACTION INC DELTA 6 PLACEMENTS 1,1,8,9,10,11",
                "END_PART",
                "END_PATTERN",
            )
        )

        report = validate_strict_pattern(script)

        self.assertFalse(report.passed)
        messages = " ".join(issue.message for issue in report.issues)
        self.assertIn("TO == FROM + DELTA", messages)
        self.assertIn("unique", messages)
        self.assertIn("within 1..FROM", messages)

    def test_strict_parser_rejects_trailing_content_and_unclosed_parts(self):
        trailing = "\n".join(
            (
                'FORMAT "PhotoToPatternStrict" 1',
                'TITLE "bad"',
                "TERMINOLOGY US",
                "STYLE SPIRAL_ROUNDS",
                'PART "body"',
                "ROUND 1 FROM 0 TO 6 ACTION MR DELTA 6 PLACEMENTS -",
                "END_PART",
                "END_PATTERN",
                "GARBAGE",
            )
        )
        unclosed = "\n".join(
            (
                'FORMAT "PhotoToPatternStrict" 1',
                'TITLE "bad"',
                "TERMINOLOGY US",
                "STYLE SPIRAL_ROUNDS",
                'PART "body"',
                "ROUND 1 FROM 0 TO 6 ACTION MR DELTA 6 PLACEMENTS -",
                "END_PATTERN",
            )
        )

        self.assertFalse(validate_strict_pattern(trailing).passed)
        self.assertFalse(validate_strict_pattern(unclosed).passed)

    def test_strict_parser_requires_ordered_headers_outside_parts(self):
        missing_headers = "\n".join(
            (
                'FORMAT "PhotoToPatternStrict" 1',
                'PART "body"',
                "ROUND 1 FROM 0 TO 6 ACTION MR DELTA 6 PLACEMENTS -",
                "END_PART",
                "END_PATTERN",
            )
        )
        header_inside_part = "\n".join(
            (
                'FORMAT "PhotoToPatternStrict" 1',
                'TITLE "bad"',
                "TERMINOLOGY US",
                "STYLE SPIRAL_ROUNDS",
                'PART "body"',
                'TITLE "inside"',
                "ROUND 1 FROM 0 TO 6 ACTION MR DELTA 6 PLACEMENTS -",
                "END_PART",
                "END_PATTERN",
            )
        )

        self.assertFalse(validate_strict_pattern(missing_headers).passed)
        self.assertFalse(validate_strict_pattern(header_inside_part).passed)

    def test_strict_parser_rejects_inconsistent_or_dangling_offsets(self):
        bad_count = "\n".join(
            (
                'FORMAT "PhotoToPatternStrict" 1',
                'TITLE "bad"',
                "TERMINOLOGY US",
                "STYLE SPIRAL_ROUNDS",
                'PART "body"',
                "ROUND 1 FROM 0 TO 6 ACTION MR DELTA 6 PLACEMENTS -",
                "OFFSET ROUND 2 STITCH_COUNT 999 SHIFT 998 DRIFT 7.0",
                "ROUND 2 FROM 6 TO 12 ACTION INC DELTA 6 PLACEMENTS 1,2,3,4,5,6",
                "END_PART",
                "END_PATTERN",
            )
        )
        dangling = "\n".join(
            (
                'FORMAT "PhotoToPatternStrict" 1',
                'TITLE "bad"',
                "TERMINOLOGY US",
                "STYLE SPIRAL_ROUNDS",
                'PART "body"',
                "ROUND 1 FROM 0 TO 6 ACTION MR DELTA 6 PLACEMENTS -",
                "OFFSET ROUND 9 STITCH_COUNT 6 SHIFT 1 DRIFT 7.0",
                "END_PART",
                "END_PATTERN",
            )
        )

        self.assertFalse(validate_strict_pattern(bad_count).passed)
        self.assertFalse(validate_strict_pattern(dangling).passed)

    def test_strict_parser_attaches_offsets_after_matching_rounds(self):
        script = "\n".join(
            (
                'FORMAT "PhotoToPatternStrict" 1',
                'TITLE "offset-order"',
                "TERMINOLOGY US",
                "STYLE SPIRAL_ROUNDS",
                'PART "body"',
                "ROUND 1 FROM 0 TO 6 ACTION MR DELTA 6 PLACEMENTS -",
                "ROUND 2 FROM 6 TO 12 ACTION INC DELTA 6 PLACEMENTS 1,2,3,4,5,6",
                "OFFSET ROUND 2 STITCH_COUNT 12 SHIFT 1 DRIFT 7.0",
                "END_PART",
                "END_PATTERN",
            )
        )

        report = validate_strict_pattern(script)

        self.assertTrue(report.passed)
        self.assertIsNotNone(report.rounds[1].alignment_offset)
        self.assertEqual(report.rounds[1].alignment_offset.offset_stitches, 1)

    def test_staggered_corrections_bound_deltas_and_avoid_repeated_columns(self):
        pattern_map = PatternMap(
            rounds=(
                _round(1, 6, 0, 6, "mr", ()),
                _round(2, 18, 6, 12, "inc", (1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6)),
                _round(3, 24, 18, 6, "inc", (1, 2, 3, 4, 5, 6)),
            )
        )

        corrected = apply_staggered_increase_corrections(pattern_map, GeometricConfig(max_delta_per_round=6))
        rounds = corrected.rounds

        self.assertTrue(all(abs(round_spec.delta) <= 6 for round_spec in rounds))
        self.assertFalse(set(rounds[1].placements).intersection(rounds[2].placements))

    def test_spiral_drift_offsets_are_deterministic_bounded_and_injected(self):
        pattern_map = PatternMap(
            rounds=(
                _round(1, 6, 0, 6, "mr", ()),
                _round(2, 9, 6, 3, "inc", (1, 3, 5)),
                _round(3, 15, 9, 6, "inc", (1, 2, 3, 4, 5, 6)),
                _round(4, 21, 15, 6, "inc", (1, 3, 5, 7, 9, 11)),
                _round(5, 27, 21, 6, "inc", (1, 4, 7, 10, 13, 16)),
                _round(6, 33, 27, 6, "inc", (1, 5, 9, 13, 17, 21)),
                _round(7, 39, 33, 6, "inc", (1, 6, 11, 16, 21, 26)),
            )
        )

        first = calculate_spiral_drift_offsets(pattern_map.rounds)
        second = calculate_spiral_drift_offsets(pattern_map.rounds)
        compiled = compile_rounds_with_alignment(pattern_map)
        injected = inject_alignment_offset_stitches(pattern_map)

        self.assertEqual(first, second)
        self.assertTrue(all(0 <= offset.offset_stitches < offset.stitch_count for offset in first))
        self.assertTrue(all(round_spec.alignment_offset is not None for round_spec in compiled))
        changed_rounds = [
            index
            for index, round_spec in enumerate(pattern_map.rounds)
            if round_spec.placements != injected.rounds[index].placements
        ]
        self.assertTrue(changed_rounds)
        self.assertEqual([round_spec.stitch_count for round_spec in pattern_map.rounds], [round_spec.stitch_count for round_spec in injected.rounds])

    def test_topology_compiler_generates_graph_valid_pattern(self):
        topology = analyze_mesh_topology(_ellipsoid_mesh())

        pattern_map = compile_topology_to_pattern(topology, GeometricConfig(max_delta_per_round=6))
        graph = to_stitch_graph(pattern_map, "compiled")

        self.assertTrue(pattern_map.rounds)
        self.assertFalse(pattern_map.warnings)
        self.assertEqual({round_spec.primitive_id for round_spec in pattern_map.rounds}, {"body_1"})
        self.assertTrue(validate_stitch_graph(graph).passed)
        part = graph["parts"][0]
        nodes_by_round = {}
        for node in part["nodes"]:
            nodes_by_round.setdefault(node["round_number"], []).append(node["id"])
        work_targets = {
            edge["to"]
            for edge in part["edges"]
            if edge["type"] in {"worked_into", "increase_split", "decrease_merge", "worked_into_overflow", "worked_into_underflow"}
        }
        first_round = min(nodes_by_round)
        for round_number, node_ids in nodes_by_round.items():
            if round_number == first_round:
                continue
            self.assertTrue(set(node_ids).issubset(work_targets))


def _round(
    number: int,
    stitch_count: int,
    previous: int,
    delta: int,
    action: str,
    placements: tuple[int, ...],
) -> RoundSpec:
    return RoundSpec(
        primitive_id="body",
        round_number=number,
        stitch_count=stitch_count,
        previous_stitch_count=previous,
        delta=delta,
        action=action,  # type: ignore[arg-type]
        phase="start" if number == 1 else "increase" if delta > 0 else "decrease" if delta < 0 else "even",
        placements=placements,
        radius=float(stitch_count),
    )


def _ellipsoid_mesh() -> Mesh:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        front = _view(root / "front.png", (180, 220), (40, 20, 140, 200))
        side = _view(root / "side.png", (160, 220), (55, 20, 105, 200))
        return build_watertight_mesh_from_orthographic(
            load_orthographic_views(front=front, side=side, mask_size=64),
            radial_segments=16,
            height_segments=8,
        )


def _view(path: Path, size: tuple[int, int], bbox: tuple[int, int, int, int]) -> Path:
    image = Image.new("RGBA", size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse(bbox, fill=(220, 120, 60, 255))
    image.save(path)
    return path


def _bifurcated_cone_mesh() -> Mesh:
    apex = Vertex(0.0, 0.0, 1.4)
    vertices = [apex]
    vertices.extend(_ring_vertices(8, radius=1.4, z=0.0, x_offset=-0.4))
    body_center = len(vertices)
    vertices.append(Vertex(-0.4, 0.0, 0.0))
    limb_start = len(vertices)
    vertices.extend(_ring_vertices(3, radius=0.45, z=0.0, x_offset=2.0))
    limb_center = len(vertices)
    vertices.append(Vertex(2.0, 0.0, 0.0))

    faces: list[Face] = []
    faces.extend(_cone_faces(0, 1, 8, body_center))
    faces.extend(_cone_faces(0, limb_start, 3, limb_center))
    mesh = Mesh(vertices=tuple(vertices), faces=tuple(faces), source="bifurcated-test")
    if mesh.signed_volume() < 0:
        mesh = Mesh(vertices=mesh.vertices, faces=tuple(Face(face.a, face.c, face.b) for face in mesh.faces), source=mesh.source)
    mesh.validate()
    return mesh


def _ring_vertices(count: int, *, radius: float, z: float, x_offset: float) -> list[Vertex]:
    return [
        Vertex(x_offset + math.cos(2.0 * math.pi * index / count) * radius, math.sin(2.0 * math.pi * index / count) * radius, z)
        for index in range(count)
    ]


def _cone_faces(apex_index: int, ring_start: int, ring_count: int, center_index: int) -> list[Face]:
    faces: list[Face] = []
    for index in range(ring_count):
        current = ring_start + index
        nxt = ring_start + ((index + 1) % ring_count)
        faces.append(Face(apex_index, current, nxt))
        faces.append(Face(center_index, nxt, current))
    return faces


if __name__ == "__main__":
    unittest.main()
