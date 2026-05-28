import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from photo_to_pattern.app import PhotoToPatternApp
from photo_to_pattern.exporter import export_plan_bundle, export_planning_bundle
from photo_to_pattern.planning import PlanningOrchestrator
from photo_to_pattern.planning.gemini_adapter import GeminiAdapter
from photo_to_pattern.planning.models import PlanningOptions


class ExporterTests(unittest.TestCase):
    def test_exports_complete_bundle(self):
        image = Image.new("RGBA", (180, 220), (255, 255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((45, 30, 145, 155), fill=(250, 190, 12, 255))
        draw.ellipse((60, 55, 120, 115), fill=(45, 30, 18, 255))
        draw.ellipse((88, 68, 106, 92), fill=(245, 238, 150, 255))
        draw.rectangle((62, 150, 78, 200), fill=(50, 35, 18, 255))
        draw.rectangle((108, 150, 124, 200), fill=(50, 35, 18, 255))

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.png"
            output = Path(temp_dir) / "export"
            image.save(source)
            result = PhotoToPatternApp().from_image(source, title="source")

            export_plan_bundle(result, source, output, project_name="source")

            self.assertTrue((output / "source_original.png").exists())
            self.assertTrue((output / "source_preview.jpg").exists())
            self.assertTrue((output / "source_pattern.txt").exists())
            self.assertTrue((output / "source_details.json").exists())
            self.assertTrue((output / "source_pattern.strict").exists())
            self.assertTrue((output / "source_verification.json").exists())
            self.assertTrue((output / "source_stitch_simulation.jpg").exists())
            self.assertTrue((output / "source_stitch_graph.json").exists())

    def test_exports_planning_bundle_with_virtual_build(self):
        image = Image.new("RGBA", (180, 220), (255, 255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((45, 30, 145, 155), fill=(250, 190, 12, 255))
        draw.rectangle((62, 150, 78, 200), fill=(50, 35, 18, 255))

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.png"
            output = Path(temp_dir) / "export"
            image.save(source)

            with patch.object(GeminiAdapter, "analyze_character", return_value=_gemini_payload()):
                planning = PlanningOrchestrator(work_root=Path(temp_dir) / "plans").create_from_images(
                    [source],
                    title="source",
                    options=PlanningOptions(gemini_api_key="test-key"),
                )
            result = PhotoToPatternApp().from_image_with_plan(source, planning.model, title="source")
            export_planning_bundle(planning, output, project_name="source", crochet_result=result)

            self.assertTrue((output / "source_planning_card.jpg").exists())
            self.assertTrue((output / "source_virtual_build.jpg").exists())
            self.assertTrue((output / "source_design_proof.jpg").exists())
            self.assertTrue((output / "source_planning_model.json").exists())
            self.assertTrue((output / "source_planning_details.json").exists())
            self.assertTrue((output / "source_accuracy_report.json").exists())
            self.assertTrue((output / "source_clean_report.html").exists())
            self.assertTrue((output / "source_pattern_package.pdf").exists())
            
            pdf_path = output / "source_pattern_package.pdf"
            self.assertGreater(pdf_path.stat().st_size, 0)
            with open(pdf_path, "rb") as f:
                sig = f.read(5)
            self.assertEqual(sig, b"%PDF-")

            details = json.loads((output / "source_planning_details.json").read_text(encoding="utf-8"))
            self.assertIsNotNone(details["accuracy"])
            self.assertEqual(details["accuracy_report_path"], str(output / "source_accuracy_report.json"))
            self.assertEqual(details["clean_report_path"], str(output / "source_clean_report.html"))
            self.assertEqual(details["pdf_report_path"], str(output / "source_pattern_package.pdf"))
            report_html = (output / "source_clean_report.html").read_text(encoding="utf-8")
            self.assertIn("Planning Card", report_html)
            self.assertIn("Virtual Build", report_html)
            self.assertIn("Design Proof", report_html)
            self.assertIn("Accuracy Summary", report_html)
            self.assertIn("Process Steps", report_html)
            self.assertIn("Generated Pattern", report_html)
            self.assertIn("data:image/jpeg;base64,", report_html)
            self.assertNotIn("src=\"source_", report_html)
            accuracy = json.loads((output / "source_accuracy_report.json").read_text(encoding="utf-8"))
            self.assertFalse(
                any("Missing generated rounds" in issue["message"] for issue in accuracy["issues"]),
                accuracy["issues"],
            )


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
