import tempfile
import unittest
import json
from pathlib import Path

from photo_to_pattern.app import PhotoToPatternApp
from photo_to_pattern.geometric_math import PatternMap, RoundSpec
from photo_to_pattern.verification import export_stitch_graph, export_strict_pattern, render_design_proof, render_stitch_simulation, validate_pattern_map, validate_stitch_graph
from photo_to_pattern.verification.stitch_graph import to_stitch_graph
from photo_to_pattern.vision_voxelizer import ImageFrame


class VerificationTests(unittest.TestCase):
    def test_exports_strict_pattern_and_simulation(self):
        result = PhotoToPatternApp().from_frame(ImageFrame(width=120, height=160, source="synthetic.png"), title="test")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            strict = export_strict_pattern(result.pattern_map, root / "pattern.strict", "test")
            graph = export_stitch_graph(result.pattern_map, root / "graph.json", "test")
            proof = render_design_proof(result.pattern_map, None, root / "proof.jpg", "test")
            simulation = render_stitch_simulation(result.pattern_map, root / "simulation.jpg", "test")
            report = validate_pattern_map(result.pattern_map)

            self.assertTrue(strict.exists())
            self.assertTrue(graph.exists())
            self.assertTrue(proof.exists())
            self.assertTrue(simulation.exists())
            text = strict.read_text(encoding="utf-8")
            self.assertIn('FORMAT "PhotoToPatternStrict" 1', text)
            self.assertIn("ROUND", text)
            graph_data = json.loads(graph.read_text(encoding="utf-8"))
            self.assertEqual(graph_data["format"], "PhotoToPatternStitchGraph")
            edge_types = {edge["type"] for part in graph_data["parts"] for edge in part["edges"]}
            self.assertIn("round_neighbor", edge_types)
            self.assertTrue({"worked_into", "increase_split", "decrease_merge"} & edge_types)
            self.assertTrue(report.passed)
            self.assertTrue(validate_stitch_graph(graph_data).passed)

    def test_stitch_graph_maps_even_increase_and_decrease_edges(self):
        pattern_map = PatternMap(
            rounds=(
                _round(1, 6, 0, 6, "mr", ()),
                _round(2, 6, 6, 0, "even", ()),
                _round(3, 8, 6, 2, "inc", (2, 5)),
                _round(4, 6, 8, -2, "dec", (3, 8)),
            )
        )

        graph = to_stitch_graph(pattern_map, "edge-test")
        part = graph["parts"][0]
        edge_types = [edge["type"] for edge in part["edges"]]

        self.assertIn("worked_into", edge_types)
        self.assertEqual(edge_types.count("increase_split"), 4)
        self.assertEqual(edge_types.count("decrease_merge"), 4)

    def test_stitch_graph_maps_terminal_decrease_with_wraparound(self):
        pattern_map = PatternMap(
            rounds=(
                _round(1, 6, 0, 6, "mr", ()),
                _round(2, 5, 6, -1, "dec", (6,)),
            )
        )

        graph = to_stitch_graph(pattern_map, "wrap-test")
        part = graph["parts"][0]
        merge_edges = [edge for edge in part["edges"] if edge["type"] == "decrease_merge"]

        self.assertEqual(len(merge_edges), 2)
        self.assertTrue(any(edge["from"].endswith(":S6") for edge in merge_edges))
        self.assertTrue(any(edge["from"].endswith(":S1") for edge in merge_edges))

    def test_stitch_graph_fills_dense_overlapping_decrease_pairs(self):
        pattern_map = PatternMap(
            rounds=(
                _round(1, 12, 0, 12, "mr", ()),
                _round(2, 6, 12, -6, "dec", (3, 5, 7, 9, 11, 12)),
            )
        )

        graph = to_stitch_graph(pattern_map, "dense-dec-test")
        part = graph["parts"][0]
        merge_edges = [edge for edge in part["edges"] if edge["type"] == "decrease_merge"]
        merge_targets = {edge["to"] for edge in merge_edges}

        self.assertEqual(len(merge_edges), 12)
        self.assertEqual(len(merge_targets), 6)

    def test_stitch_graph_validator_reports_missing_edge_endpoint(self):
        pattern_map = PatternMap(rounds=(_round(1, 6, 0, 6, "mr", ()), _round(2, 6, 6, 0, "even", ())))
        graph = to_stitch_graph(pattern_map, "invalid-edge-test")
        graph["parts"][0]["edges"][0]["to"] = "missing-node"

        report = validate_stitch_graph(graph)

        self.assertFalse(report.passed)
        self.assertTrue(any("does not exist" in issue.message for issue in report.issues))

    def test_stitch_graph_validator_reports_unworked_later_round_stitches(self):
        pattern_map = PatternMap(rounds=(_round(1, 6, 0, 6, "mr", ()), _round(2, 6, 6, 0, "even", ())))
        graph = to_stitch_graph(pattern_map, "continuity-test")
        part = graph["parts"][0]
        part["edges"] = [edge for edge in part["edges"] if edge["type"] == "round_neighbor"]

        report = validate_stitch_graph(graph)

        self.assertFalse(report.passed)
        self.assertTrue(any("without a worked-into source" in issue.message for issue in report.issues))

    def test_stitch_graph_validator_rejects_wrong_round_work_edges(self):
        pattern_map = PatternMap(rounds=(_round(1, 6, 0, 6, "mr", ()), _round(2, 6, 6, 0, "even", ())))
        graph = to_stitch_graph(pattern_map, "direction-test")
        part = graph["parts"][0]
        work_edge = next(edge for edge in part["edges"] if edge["type"] == "worked_into")
        work_edge["from"] = "test:R2:S1"

        report = validate_stitch_graph(graph)

        self.assertFalse(report.passed)
        self.assertTrue(any("must connect work from round" in issue.message for issue in report.issues))

    def test_stitch_graph_validator_rejects_single_sided_shaping_edges(self):
        pattern_map = PatternMap(
            rounds=(
                _round(1, 6, 0, 6, "mr", ()),
                _round(2, 8, 6, 2, "inc", (2, 5)),
            )
        )
        graph = to_stitch_graph(pattern_map, "shaping-test")
        part = graph["parts"][0]
        first_split_source = next(edge["from"] for edge in part["edges"] if edge["type"] == "increase_split")
        removed = False
        filtered_edges = []
        for edge in part["edges"]:
            if edge["type"] == "increase_split" and edge["from"] == first_split_source and not removed:
                removed = True
                continue
            filtered_edges.append(edge)
        part["edges"] = filtered_edges

        report = validate_stitch_graph(graph)

        self.assertFalse(report.passed)
        self.assertTrue(any("does not split into multiple targets" in issue.message for issue in report.issues))


def _round(
    number: int,
    stitch_count: int,
    previous: int,
    delta: int,
    action: str,
    placements: tuple[int, ...],
) -> RoundSpec:
    return RoundSpec(
        primitive_id="test",
        round_number=number,
        stitch_count=stitch_count,
        previous_stitch_count=previous,
        delta=delta,
        action=action,  # type: ignore[arg-type]
        phase="start" if number == 1 else "increase" if delta > 0 else "decrease" if delta < 0 else "even",
        placements=placements,
        radius=stitch_count,
    )


if __name__ == "__main__":
    unittest.main()
