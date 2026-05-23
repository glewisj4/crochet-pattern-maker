import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from photo_to_pattern.app import PhotoToPatternApp
from photo_to_pattern.part_generator import generate_planned_part_pattern_map
from photo_to_pattern.planning import PlanningOrchestrator
from photo_to_pattern.planning.models import PlanningModel
from photo_to_pattern.verification import validate_pattern_map


class PlannedPartGeneratorTests(unittest.TestCase):
    def test_generates_rounds_for_every_structural_planned_part(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "front.png"
            image = Image.new("RGBA", (220, 280), (255, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.ellipse((55, 30, 165, 140), fill=(230, 125, 52, 255))
            draw.rectangle((78, 132, 142, 250), fill=(230, 125, 52, 255))
            image.save(source)

            plan = PlanningOrchestrator(work_root=Path(temp_dir) / "out").create_from_images([source], title="fox").model
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

            plan = PlanningOrchestrator(work_root=Path(temp_dir) / "out").create_from_images([source], title="fox").model
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


if __name__ == "__main__":
    unittest.main()
