import tempfile
import unittest
import json
from pathlib import Path

from PIL import Image, ImageDraw

from photo_to_pattern.planning import PlanningOrchestrator
from photo_to_pattern.planning.models import PlanningOptions


class PlanningOrchestratorTests(unittest.TestCase):
    def test_creates_card_and_fills_missing_views_from_one_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "front_character.png"
            image = Image.new("RGBA", (260, 320), (255, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.ellipse((70, 35, 190, 165), fill=(230, 125, 52, 255))
            draw.ellipse((88, 72, 172, 132), fill=(54, 42, 35, 255))
            draw.rectangle((95, 158, 122, 265), fill=(230, 125, 52, 255))
            draw.rectangle((138, 158, 165, 265), fill=(230, 125, 52, 255))
            image.save(source)

            result = PlanningOrchestrator(work_root=root / "out").create_from_images([source], title="fox")

            self.assertTrue(result.card_path.exists())
            self.assertIsNotNone(result.virtual_build_path)
            self.assertTrue(result.virtual_build_path.exists())
            self.assertIsNotNone(result.model_json_path)
            self.assertTrue(result.model_json_path.exists())
            self.assertEqual({view.kind for view in result.model.views}, {"front", "side", "back", "top"})
            self.assertEqual(len([view for view in result.model.views if view.inferred]), 3)
            self.assertTrue(result.model.construction)
            self.assertTrue(result.model.parts)
            self.assertTrue(result.model.uncertainties)

            model_json = json.loads(result.model_json_path.read_text(encoding="utf-8"))
            self.assertIn("parts", model_json)
            self.assertIn("details", model_json)
            self.assertIn("uncertainties", model_json)
            self.assertEqual(model_json["title"], "fox")
            self.assertIn("compromises", model_json)

    def test_applies_size_and_proportion_options(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "front_character.png"
            image = Image.new("RGBA", (240, 300), (255, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.ellipse((65, 35, 175, 155), fill=(230, 125, 52, 255))
            draw.rectangle((90, 145, 150, 260), fill=(230, 125, 52, 255))
            image.save(source)

            options = PlanningOptions(target_height_inches=12.0, stitches_per_inch=4.5, head_scale=1.25, body_scale=0.9, limb_scale=1.1, detail_scale=1.2)
            result = PlanningOrchestrator(work_root=root / "out").create_from_images([source], title="fox", options=options)

            self.assertEqual(result.model.options.target_height_inches, 12.0)
            self.assertEqual(result.model.options.stitches_per_inch, 4.5)
            head = next(part for part in result.model.parts if part.name == "Head")
            self.assertGreater(head.relative_size[1], 0.36)

    def test_reimagines_sources_when_enabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "front_character.png"
            image = Image.new("RGBA", (220, 260), (255, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.ellipse((55, 35, 165, 145), fill=(230, 125, 52, 255))
            draw.rectangle((82, 140, 138, 230), fill=(230, 125, 52, 255))
            image.save(source)

            options = PlanningOptions(reimagine_as_amigurumi=True)
            result = PlanningOrchestrator(work_root=root / "out").create_from_images([source], title="fox", options=options)

            self.assertTrue(result.model.options.reimagine_as_amigurumi)
            self.assertTrue((result.work_dir / "reimagined_views" / "upload_1_amigurumi_reference.png").exists())
            self.assertTrue(any(item.feature == "Source reference" for item in result.model.compromises))

    def test_promotes_distinctive_fox_leaf_features(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "fox_leaf_front.png"
            image = Image.new("RGBA", (320, 360), (255, 255, 255, 255))
            draw = ImageDraw.Draw(image)

            draw.ellipse((105, 78, 215, 188), fill=(224, 116, 48, 255))
            draw.polygon(((112, 92), (126, 28), (154, 96)), fill=(224, 116, 48, 255))
            draw.polygon(((166, 96), (194, 28), (208, 92)), fill=(224, 116, 48, 255))
            draw.polygon(((124, 88), (130, 52), (145, 90)), fill=(238, 174, 154, 255))
            draw.polygon(((175, 90), (190, 52), (196, 88)), fill=(238, 174, 154, 255))
            draw.ellipse((130, 122, 190, 165), fill=(238, 211, 178, 255))
            draw.arc((124, 117, 148, 130), 10, 170, fill=(35, 29, 26, 255), width=4)
            draw.arc((172, 117, 196, 130), 10, 170, fill=(35, 29, 26, 255), width=4)

            draw.ellipse((112, 178, 208, 294), fill=(224, 116, 48, 255))
            draw.polygon(((88, 184), (232, 184), (205, 275), (116, 275)), fill=(86, 139, 75, 255))
            draw.line((160, 188, 160, 272), fill=(52, 83, 45, 255), width=4)
            draw.line((160, 218, 128, 198), fill=(52, 83, 45, 255), width=3)
            draw.line((160, 238, 196, 210), fill=(52, 83, 45, 255), width=3)
            draw.rectangle((120, 280, 142, 330), fill=(224, 116, 48, 255))
            draw.rectangle((178, 280, 200, 330), fill=(224, 116, 48, 255))
            draw.polygon(((214, 218), (300, 176), (280, 246)), fill=(224, 116, 48, 255))
            draw.polygon(((274, 188), (300, 176), (290, 208)), fill=(242, 220, 185, 255))
            image.save(source)

            result = PlanningOrchestrator(work_root=root / "out").create_from_images([source], title="fox leaf")
            detail_text = " ".join(f"{item.name} {item.method} {item.placement}" for item in result.model.details).lower()
            part_text = " ".join(f"{item.name} {item.primitive} {item.source}" for item in result.model.parts).lower()
            construction_names = {item.name for item in result.model.construction}
            compromise_text = " ".join(item.feature for item in result.model.compromises).lower()
            part_names = {item.name for item in result.model.parts}
            arms = next(item for item in result.model.parts if item.name == "Arms")
            legs = next(item for item in result.model.parts if item.name == "Legs")

            self.assertIn("Leaf cloak/body wrap", part_names)
            self.assertIn("tier:structural", part_text)
            self.assertIn("tier:flat applique", part_text)
            self.assertIn("tier:embroidery guide", detail_text)
            self.assertIn("tier:color/overlay cue", detail_text)
            self.assertIn("leaf vein embroidery", detail_text)
            self.assertIn("inner ears", detail_text)
            self.assertIn("snout/muzzle", detail_text)
            self.assertIn("closed eyes", detail_text)
            self.assertIn("tail color/detail", detail_text)
            self.assertLessEqual(arms.relative_size[1], 0.18)
            self.assertLessEqual(legs.relative_size[1], 0.22)
            self.assertIn("Leaf cloak/body wrap", construction_names)
            self.assertIn("Embroidered closed eyes", construction_names)
            self.assertIn("Leaf vein embroidery", construction_names)
            self.assertIn("leaf cloak/body wrap", compromise_text)
            self.assertIn("tail color/detail", compromise_text)

    def test_splits_single_orthographic_contact_sheet_into_one_design_views(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "orthographic_sheet.png"
            image = Image.new("RGBA", (1600, 980), (255, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            panels = [
                ((48, 30, 800, 337), "1. FRONT VIEW", (320, 95, 500, 285)),
                ((822, 30, 1552, 337), "4. TOP VIEW", (1040, 110, 1350, 260)),
                ((48, 383, 421, 700), "1. FRONT VIEW", (150, 455, 310, 660)),
                ((437, 383, 803, 700), "2. SIDE VIEW", (540, 455, 700, 660)),
                ((822, 383, 1190, 700), "3. BACK VIEW", (930, 455, 1090, 660)),
                ((1210, 383, 1552, 700), "4. TOP VIEW", (1280, 455, 1480, 640)),
            ]
            for panel, label, subject in panels:
                draw.rectangle(panel, fill=(246, 246, 248, 255))
                draw.ellipse(subject, fill=(230, 125, 52, 255))
                draw.text((panel[0] + 120, panel[3] + 20), label, fill=(0, 0, 0, 255))
            draw.rectangle((620, 348, 980, 365), fill=(0, 0, 0, 255))
            draw.rectangle((560, 724, 1040, 741), fill=(0, 0, 0, 255))
            image.save(source)

            result = PlanningOrchestrator(work_root=root / "out").create_from_images([source], title="sheet")

            self.assertEqual({view.kind for view in result.model.views}, {"front", "side", "back", "top"})
            self.assertEqual(len([view for view in result.model.views if view.inferred]), 0)
            self.assertTrue((result.work_dir / "contact_sheet_views" / "front_view.png").exists())
            self.assertTrue(all("orthographic contact sheet" in view.note for view in result.model.views))

    def test_rejects_more_than_four_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = []
            for index in range(5):
                path = root / f"image_{index}.png"
                Image.new("RGBA", (20, 20), (255, 255, 255, 255)).save(path)
                paths.append(path)

            with self.assertRaises(ValueError):
                PlanningOrchestrator(work_root=root / "out").create_from_images(paths)


if __name__ == "__main__":
    unittest.main()
