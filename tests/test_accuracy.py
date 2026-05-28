import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw

from photo_to_pattern.accuracy import build_accuracy_report
from photo_to_pattern.accuracy.report import structural_confidence_index
from photo_to_pattern.app import AppResult, PhotoToPatternApp
from photo_to_pattern.geometric_math import PatternMap
from photo_to_pattern.planning import PlanningOrchestrator
from photo_to_pattern.planning.gemini_adapter import GeminiAdapter
from photo_to_pattern.planning.models import ConstructionPiece, DesignDetail, DesignPart, PlanningModel, PlanningOptions, PlanningView
from photo_to_pattern.pattern_linguist import CrochetPattern
from photo_to_pattern.qa_simulation import PatternQASimulator
from photo_to_pattern.vision_voxelizer import VoxelModel


class AccuracyReportTests(unittest.TestCase):
    def test_builds_accuracy_report_for_generated_plan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = _source_image(Path(temp_dir) / "front.png")
            with patch.object(GeminiAdapter, "analyze_character", return_value=_gemini_payload()):
                planning = PlanningOrchestrator(work_root=Path(temp_dir) / "plans").create_from_images(
                    [source],
                    title="fox",
                    options=PlanningOptions(gemini_api_key="test-key"),
                )
            result = PhotoToPatternApp().from_image_with_plan(source, planning.model, title="fox")

            report = build_accuracy_report(planning, result)

            self.assertGreaterEqual(report.overall_score, 0.45)
            self.assertGreaterEqual(report.crochet_feasibility_score, 0.50)
            self.assertTrue(any(check.name == "Crochet feasibility" for check in report.checks))
            self.assertIn("Accuracy Report", report.render())

    def test_accuracy_report_flags_missing_generated_structural_part(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = _source_image(Path(temp_dir) / "front.png")
            view = PlanningView(kind="front", source_path=source, cleaned_path=source)
            model = PlanningModel(
                title="missing",
                options=PlanningOptions(),
                views=(view,),
                shape_guides=(),
                proportions=(),
                construction=(ConstructionPiece("Wings", 2, "capsule", "paired tapered wings"),),
                parts=(DesignPart("Wings", "capsule", (0.4, 0.2, 0.1), (200, 180, 80), "back", "front", 0.8),),
            )
            planning = SimpleNamespace(model=model, card_path=source, model_json_path=None, virtual_build_path=None)
            result = AppResult(
                voxel_model=VoxelModel(primitives=()),
                pattern_map=PatternMap(rounds=()),
                crochet_pattern=CrochetPattern(title="missing", stitch_style="amigurumi", terminology="US", sections=()),
                qa_report=PatternQASimulator().evaluate(PatternMap(rounds=()), VoxelModel(primitives=())),
            )

            report = build_accuracy_report(planning, result)  # type: ignore[arg-type]

            self.assertFalse(report.passed)
            self.assertTrue(any("Missing generated rounds" in issue.message for issue in report.issues))

    def test_accuracy_report_hard_fails_low_structural_confidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = _source_image(Path(temp_dir) / "front.png")
            view = PlanningView(kind="front", source_path=source, cleaned_path=source)
            model = PlanningModel(
                title="low-confidence",
                options=PlanningOptions(),
                views=(view,),
                shape_guides=(),
                proportions=(),
                construction=(ConstructionPiece("Body", 1, "ovoid", "body"),),
                parts=(DesignPart("Body", "ovoid", (1.0, 1.0, 0.8), (200, 180, 80), "root", "front", 0.70),),
            )
            planning = SimpleNamespace(model=model, card_path=source, model_json_path=None, virtual_build_path=source)
            result = AppResult(
                voxel_model=VoxelModel(primitives=()),
                pattern_map=PatternMap(rounds=()),
                crochet_pattern=CrochetPattern(title="low-confidence", stitch_style="amigurumi", terminology="US", sections=()),
                qa_report=PatternQASimulator().evaluate(PatternMap(rounds=()), VoxelModel(primitives=())),
            )

            report = build_accuracy_report(planning, result)  # type: ignore[arg-type]

            self.assertEqual(structural_confidence_index(model), 0.70)
            self.assertFalse(report.passed)
            self.assertTrue(any("below required 75%" in issue.message for issue in report.issues))

    def test_accuracy_report_explains_missing_shape_guides(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = _source_image(Path(temp_dir) / "front.png")
            view = PlanningView(kind="front", source_path=source, cleaned_path=source)
            model = PlanningModel(
                title="no-guides",
                options=PlanningOptions(),
                views=(view,),
                shape_guides=(),
                proportions=(),
                construction=(ConstructionPiece("Body", 1, "ovoid", "body"),),
                parts=(DesignPart("Body", "ovoid", (1.0, 1.0, 0.8), (200, 180, 80), "root", "front", 0.8),),
            )
            planning = SimpleNamespace(model=model, card_path=source, model_json_path=None, virtual_build_path=None)
            result = AppResult(
                voxel_model=VoxelModel(primitives=()),
                pattern_map=PatternMap(rounds=()),
                crochet_pattern=CrochetPattern(title="no-guides", stitch_style="amigurumi", terminology="US", sections=()),
                qa_report=PatternQASimulator().evaluate(PatternMap(rounds=()), VoxelModel(primitives=())),
            )

            report = build_accuracy_report(planning, result)  # type: ignore[arg-type]

            self.assertTrue(any("No shape-guide evidence" in issue.message for issue in report.issues))

    def test_accuracy_report_flags_reference_framing_ambiguity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = _source_image(Path(temp_dir) / "front.png")
            view = PlanningView(kind="front", source_path=source, cleaned_path=source, confidence=0.55, note="cropped partial framing")
            model = PlanningModel(
                title="ambiguous",
                options=PlanningOptions(),
                views=(view,),
                shape_guides=(),
                proportions=(),
                construction=(ConstructionPiece("Body", 1, "ovoid", "body"),),
                parts=(DesignPart("Body", "ovoid", (1.0, 1.0, 0.8), (200, 180, 80), "root", "front", 0.8),),
            )
            planning = SimpleNamespace(model=model, card_path=source, model_json_path=None, virtual_build_path=None)
            result = AppResult(
                voxel_model=VoxelModel(primitives=()),
                pattern_map=PatternMap(rounds=()),
                crochet_pattern=CrochetPattern(title="ambiguous", stitch_style="amigurumi", terminology="US", sections=()),
                qa_report=PatternQASimulator().evaluate(PatternMap(rounds=()), VoxelModel(primitives=())),
            )

            report = build_accuracy_report(planning, result)  # type: ignore[arg-type]

            self.assertTrue(any(issue.area == "reference framing" for issue in report.issues))
            self.assertTrue(any(issue.area == "reference ambiguity" for issue in report.issues))

    def test_accuracy_report_flags_missing_distinctive_features_for_low_confidence_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = _source_image(Path(temp_dir) / "front.png")
            view = PlanningView(kind="front", source_path=source, cleaned_path=source)
            model = PlanningModel(
                title="fox leaf character",
                options=PlanningOptions(),
                views=(view,),
                shape_guides=(),
                proportions=(),
                construction=(ConstructionPiece("Body", 1, "ovoid", "body"),),
                parts=(DesignPart("Body", "ovoid", (1.0, 1.0, 0.8), (200, 180, 80), "root", "front", 0.8),),
                details=(DesignDetail("Face", "embroider after stuffing", "front head center", None, "inferred default", 0.25),),
            )
            planning = SimpleNamespace(model=model, card_path=source, model_json_path=None, virtual_build_path=None)
            result = AppResult(
                voxel_model=VoxelModel(primitives=()),
                pattern_map=PatternMap(rounds=()),
                crochet_pattern=CrochetPattern(title="leaf character", stitch_style="amigurumi", terminology="US", sections=()),
                qa_report=PatternQASimulator().evaluate(PatternMap(rounds=()), VoxelModel(primitives=())),
            )

            report = build_accuracy_report(planning, result)  # type: ignore[arg-type]

            messages = [issue.message for issue in report.issues if issue.area == "distinctive features"]
            self.assertEqual(len(messages), 1)
            self.assertIn("leaf cloak", messages[0])
            self.assertIn("inner ears", messages[0])
            self.assertIn("snout/muzzle", messages[0])
            self.assertIn("tail", messages[0])
            self.assertNotIn("embroidery", messages[0])

    def test_accuracy_report_accepts_distinctive_features_in_details_and_construction(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = _source_image(Path(temp_dir) / "front.png")
            view = PlanningView(kind="front", source_path=source, cleaned_path=source)
            model = PlanningModel(
                title="fox leaf character",
                options=PlanningOptions(),
                views=(view,),
                shape_guides=(),
                proportions=(),
                construction=(
                    ConstructionPiece("Leaf cloak", 1, "surface detail", "leaf cloak collar"),
                    ConstructionPiece("Tail", 1, "tapered cone", "tail"),
                ),
                parts=(DesignPart("Body", "ovoid", (1.0, 1.0, 0.8), (200, 180, 80), "root", "front", 0.8),),
                details=(
                    DesignDetail("Face", "embroider after stuffing", "front head center", None, "inferred default", 0.25),
                    DesignDetail("Inner ears", "ear inset applique", "inside each ear", (240, 190, 180), "reviewed", 0.8),
                    DesignDetail("Muzzle", "snout oval applique", "front lower face", (245, 230, 210), "reviewed", 0.8),
                ),
            )
            planning = SimpleNamespace(model=model, card_path=source, model_json_path=None, virtual_build_path=None)
            result = AppResult(
                voxel_model=VoxelModel(primitives=()),
                pattern_map=PatternMap(rounds=()),
                crochet_pattern=CrochetPattern(title="leaf character", stitch_style="amigurumi", terminology="US", sections=()),
                qa_report=PatternQASimulator().evaluate(PatternMap(rounds=()), VoxelModel(primitives=())),
            )

            report = build_accuracy_report(planning, result)  # type: ignore[arg-type]

            self.assertFalse(any(issue.area == "distinctive features" for issue in report.issues))

    def test_accuracy_report_does_not_require_fox_leaf_features_for_generic_plan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = _source_image(Path(temp_dir) / "front.png")
            view = PlanningView(kind="front", source_path=source, cleaned_path=source)
            model = PlanningModel(
                title="round body",
                options=PlanningOptions(),
                views=(view,),
                shape_guides=(),
                proportions=(),
                construction=(ConstructionPiece("Body", 1, "ovoid", "body"),),
                parts=(DesignPart("Body", "ovoid", (1.0, 1.0, 0.8), (200, 180, 80), "root", "front", 0.8),),
                details=(DesignDetail("Face", "embroider after stuffing", "front head center", None, "inferred default", 0.25),),
            )
            planning = SimpleNamespace(model=model, card_path=source, model_json_path=None, virtual_build_path=None)
            result = AppResult(
                voxel_model=VoxelModel(primitives=()),
                pattern_map=PatternMap(rounds=()),
                crochet_pattern=CrochetPattern(title="round body", stitch_style="amigurumi", terminology="US", sections=()),
                qa_report=PatternQASimulator().evaluate(PatternMap(rounds=()), VoxelModel(primitives=())),
            )

            report = build_accuracy_report(planning, result)  # type: ignore[arg-type]

            messages = [issue.message for issue in report.issues if issue.area == "distinctive features"]
            self.assertFalse(any("leaf cloak" in message for message in messages))
            self.assertFalse(any("inner ears" in message for message in messages))


def _source_image(path: Path) -> Path:
    image = Image.new("RGBA", (220, 280), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((55, 30, 165, 140), fill=(230, 125, 52, 255))
    draw.rectangle((78, 132, 142, 250), fill=(230, 125, 52, 255))
    image.save(path)
    return path


def _gemini_payload() -> dict:
    return {
        "parts": [
            {"name": "Head", "category": "Primary Body", "primitive": "sphere", "relative_size": [0.50, 0.36, 0.40], "color_hex": "#e67d34", "attachment": "above body", "confidence": 0.94},
            {"name": "Body", "category": "Primary Body", "primitive": "ovoid", "relative_size": [0.44, 0.62, 0.32], "color_hex": "#e67d34", "attachment": "root", "confidence": 0.93},
            {"name": "Ears", "category": "Insets", "primitive": "inset_ear", "relative_size": [0.22, 0.34, 0.12], "color_hex": "#e67d34", "attachment": "top head", "confidence": 0.91},
            {"name": "Tail", "category": "Appendages", "primitive": "curled_tail", "relative_size": [0.24, 0.50, 0.19], "color_hex": "#8b512b", "attachment": "back body", "confidence": 0.90},
        ],
        "details": [
            {"name": "Snout/muzzle", "category": "Accents", "method": "crochet applique snout", "placement": "lower front face", "color_hex": "#eed3b2", "confidence": 0.89},
        ],
    }


if __name__ == "__main__":
    unittest.main()
