import tempfile
import unittest
import json
from pathlib import Path

from PIL import Image, ImageDraw

from photo_to_pattern.app import PhotoToPatternApp
from photo_to_pattern.exporter import export_plan_bundle, export_planning_bundle
from photo_to_pattern.planning import PlanningOrchestrator


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

            planning = PlanningOrchestrator(work_root=Path(temp_dir) / "plans").create_from_images([source], title="source")
            result = PhotoToPatternApp().from_image_with_plan(source, planning.model, title="source")
            export_planning_bundle(planning, output, project_name="source", crochet_result=result)

            self.assertTrue((output / "source_planning_card.jpg").exists())
            self.assertTrue((output / "source_virtual_build.jpg").exists())
            self.assertTrue((output / "source_design_proof.jpg").exists())
            self.assertTrue((output / "source_planning_model.json").exists())
            self.assertTrue((output / "source_planning_details.json").exists())
            self.assertTrue((output / "source_accuracy_report.json").exists())
            self.assertTrue((output / "source_clean_report.html").exists())
            details = json.loads((output / "source_planning_details.json").read_text(encoding="utf-8"))
            self.assertIsNotNone(details["accuracy"])
            self.assertEqual(details["accuracy_report_path"], str(output / "source_accuracy_report.json"))
            self.assertEqual(details["clean_report_path"], str(output / "source_clean_report.html"))
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


if __name__ == "__main__":
    unittest.main()
