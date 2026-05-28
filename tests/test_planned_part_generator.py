import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from photo_to_pattern.app import PhotoToPatternApp
from photo_to_pattern.part_generator import generate_planned_part_pattern_map
from photo_to_pattern.planning import PlanningOrchestrator
from photo_to_pattern.planning.gemini_adapter import GeminiAdapter
from photo_to_pattern.planning.models import PlanningModel
from photo_to_pattern.planning.models import PlanningOptions
from photo_to_pattern.verification import validate_pattern_map
from unittest.mock import patch


class PlannedPartGeneratorTests(unittest.TestCase):
    def test_generates_rounds_for_every_structural_planned_part(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "front.png"
            image = Image.new("RGBA", (220, 280), (255, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.ellipse((55, 30, 165, 140), fill=(230, 125, 52, 255))
            draw.rectangle((78, 132, 142, 250), fill=(230, 125, 52, 255))
            image.save(source)

            with patch.object(GeminiAdapter, "analyze_character", return_value=_gemini_payload()):
                plan = PlanningOrchestrator(work_root=Path(temp_dir) / "out").create_from_images(
                    [source],
                    title="fox",
                    options=PlanningOptions(gemini_api_key="test-key"),
                ).model
            pattern_map = generate_planned_part_pattern_map(plan)
            ids = {round_spec.primitive_id for round_spec in pattern_map.rounds}

            for expected in _expected_structural_ids(plan):
                self.assertIn(expected, ids)
            self.assertTrue(validate_pattern_map(pattern_map).passed)

    def test_app_uses_planned_part_rounds_with_plan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "front.png"
            image = Image.new("RGBA", (220, 280), (255, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.ellipse((55, 30, 165, 140), fill=(230, 125, 52, 255))
            draw.rectangle((78, 132, 142, 250), fill=(230, 125, 52, 255))
            image.save(source)

            with patch.object(GeminiAdapter, "analyze_character", return_value=_gemini_payload()):
                plan = PlanningOrchestrator(work_root=Path(temp_dir) / "out").create_from_images(
                    [source],
                    title="fox",
                    options=PlanningOptions(gemini_api_key="test-key"),
                ).model
            result = PhotoToPatternApp().from_image_with_plan(source, plan, title="fox")
            rendered = result.render()
            ids = {round_spec.primitive_id for round_spec in result.pattern_map.rounds}

            self.assertIn("Planned Design Overview", rendered)
            self.assertIn("Head", rendered)
            self.assertIn("Tail", rendered)
            self.assertIn("Ears 1", rendered)
            for expected in _expected_structural_ids(plan):
                self.assertIn(expected, ids)


def _expected_structural_ids(plan: PlanningModel) -> set[str]:
    ids = set()
    quantities = {piece.name: piece.quantity for piece in plan.construction}
    for part in plan.parts:
        primitive = part.primitive.lower()
        if "detail" in primitive or "applique" in primitive or "embroidery" in primitive:
            continue
        base = "".join(char.lower() if char.isalnum() else "_" for char in part.name).strip("_")
        quantity = max(1, quantities.get(part.name, 1))
        if quantity == 1:
            ids.add(base)
        else:
            ids.update(f"{base}_{index}" for index in range(1, quantity + 1))
    return ids


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
