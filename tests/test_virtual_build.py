import tempfile
import unittest
from pathlib import Path

from PIL import Image

from photo_to_pattern.planning.models import (
    ConstructionPiece,
    DesignDetail,
    DesignPart,
    PlanningModel,
    PlanningOptions,
)
from photo_to_pattern.planning.virtual_build import render_virtual_build


class VirtualBuildRendererTests(unittest.TestCase):
    def test_renders_planned_colors_and_character_details(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "virtual_build.jpg"
            body_color = (88, 146, 211)
            cloak_color = (54, 132, 65)
            muzzle_color = (246, 214, 174)
            inner_ear_color = (255, 185, 196)
            tail_color = (188, 92, 47)
            model = PlanningModel(
                title="Leaf fox",
                options=PlanningOptions(),
                views=(),
                shape_guides=(),
                proportions=(),
                construction=(
                    ConstructionPiece("Leaf cloak wrap", 1, "applique", "wrap around shoulders"),
                ),
                parts=(
                    DesignPart("Body", "oval", (0.44, 0.62, 0.32), body_color, "center", "test", 0.9),
                    DesignPart("Head", "sphere", (0.50, 0.36, 0.40), body_color, "above body", "test", 0.9),
                    DesignPart("Ears", "triangles", (0.20, 0.18, 0.08), (96, 120, 185), "top head", "test", 0.9),
                    DesignPart("Arms", "capsules", (0.18, 0.28, 0.12), (231, 180, 82), "sides", "test", 0.9),
                    DesignPart("Legs", "capsules", (0.18, 0.28, 0.12), (112, 82, 168), "bottom", "test", 0.9),
                    DesignPart("Tail", "curled tail", (0.28, 0.22, 0.18), tail_color, "back right", "test", 0.9),
                ),
                details=(
                    DesignDetail("Leaf cloak", "crocheted leaf wrap", "around shoulders", cloak_color, "test", 0.9),
                    DesignDetail("Inner ear", "applique", "inside ears", inner_ear_color, "test", 0.9),
                    DesignDetail("Closed embroidered eyes", "embroidered closed eyes", "front head", (31, 28, 25), "test", 0.9),
                    DesignDetail("Snout muzzle", "oval applique", "lower face", muzzle_color, "test", 0.9),
                ),
            )

            render_virtual_build(model, output)

            image = Image.open(output).convert("RGB")
            self.assert_has_color_near(image, (260, 205, 395, 285), body_color, tolerance=24, minimum_pixels=1500)
            self.assert_has_color_near(image, (230, 405, 440, 575), cloak_color, tolerance=32, minimum_pixels=700)
            self.assert_close_color(image.getpixel((288, 181)), inner_ear_color, tolerance=38)
            self.assert_close_color(image.getpixel((320, 315)), muzzle_color, tolerance=35)
            self.assert_has_color_near(image, (470, 455, 520, 540), tail_color, tolerance=42, minimum_pixels=40)
            self.assert_has_color_near(image, (285, 260, 390, 292), (31, 28, 25), tolerance=32, minimum_pixels=30)

    def test_renders_leaf_veins_tail_tip_and_subordinate_inferred_limbs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "tiered_virtual_build.jpg"
            body_color = (234, 176, 54)
            cloak_color = (74, 134, 68)
            vein_color = (35, 72, 32)
            tail_tip = (242, 220, 185)
            model = PlanningModel(
                title="Yellow fox with leaf cloak",
                options=PlanningOptions(),
                views=(),
                shape_guides=(),
                proportions=(),
                construction=(),
                parts=(
                    DesignPart("Body", "ovoid", (0.44, 0.62, 0.32), body_color, "center", "tier:structural; body", 0.9),
                    DesignPart("Head", "sphere", (0.50, 0.36, 0.40), body_color, "above body", "tier:structural; head", 0.9),
                    DesignPart("Ears", "large fox cones", (0.22, 0.34, 0.12), body_color, "top head", "tier:structural; ears", 0.9),
                    DesignPart("Arms", "small optional cylinder", (0.08, 0.18, 0.07), body_color, "sides", "tier:structural; optional and visually subordinate", 0.18),
                    DesignPart("Legs", "cylinder", (0.12, 0.22, 0.10), body_color, "bottom", "tier:structural; keep subordinate", 0.24),
                    DesignPart("Tail", "tapered cone with color tip", (0.24, 0.50, 0.19), (139, 81, 43), "back", "tier:structural; tail", 0.8),
                    DesignPart("Leaf cloak/body wrap", "flat wrap applique", (0.72, 0.38, 0.04), cloak_color, "shoulders", "tier:flat applique; leaf", 0.8),
                ),
                details=(
                    DesignDetail("Leaf vein embroidery", "tier:embroidery guide; central vein and short branch veins", "on wrap", vein_color, "test", 0.9),
                    DesignDetail("Tail color/detail", "tier:color/overlay cue; add pale tail tip", "outer tail end", tail_tip, "test", 0.9),
                    DesignDetail("Inner ears", "tier:flat applique; inner ear appliques", "inside ears", (241, 178, 154), "test", 0.9),
                    DesignDetail("Embroidered closed eyes", "tier:embroidery guide; two curved backstitch lines", "upper front head", (35, 30, 28), "test", 0.9),
                    DesignDetail("Snout/muzzle", "tier:flat applique; oval muzzle", "lower face", (240, 218, 184), "test", 0.9),
                ),
            )

            render_virtual_build(model, output)

            image = Image.open(output).convert("RGB")
            self.assert_has_color_near(image, (275, 405, 395, 565), vein_color, tolerance=24, minimum_pixels=120)
            self.assert_has_color_near(image, (445, 405, 520, 510), tail_tip, tolerance=34, minimum_pixels=120)
            self.assert_has_color_near(image, (180, 345, 250, 500), body_color, tolerance=28, minimum_pixels=120)
            self.assert_has_color_near(image, (120, 355, 230, 540), body_color, tolerance=28, maximum_pixels=3200)

    def test_scaled_build_stays_inside_preview_area(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "large_virtual_build.jpg"
            model = PlanningModel(
                title="Tall toy",
                options=PlanningOptions(),
                views=(),
                shape_guides=(),
                proportions=(),
                construction=(),
                parts=(
                    DesignPart("Body", "oval", (0.80, 1.20, 0.35), (220, 96, 80), "center", "test", 0.9),
                    DesignPart("Head", "sphere", (0.72, 0.85, 0.45), (220, 96, 80), "above body", "test", 0.9),
                    DesignPart("Legs", "capsules", (0.24, 0.52, 0.16), (220, 96, 80), "bottom", "test", 0.9),
                ),
                details=(),
            )

            render_virtual_build(model, output)

            image = Image.open(output).convert("RGB")
            content = [
                (x, y)
                for y in range(120, 730)
                for x in range(80, 560)
                if image.getpixel((x, y)) != (249, 248, 244)
            ]
            self.assertTrue(content)
            self.assertGreaterEqual(min(x for x, _ in content), 80)
            self.assertLessEqual(max(x for x, _ in content), 560)
            self.assertGreaterEqual(min(y for _, y in content), 120)
            self.assertLessEqual(max(y for _, y in content), 730)

    def assert_close_color(self, actual, expected, tolerance):
        self.assertLessEqual(max(abs(a - b) for a, b in zip(actual, expected)), tolerance, f"{actual} != {expected}")

    def assert_has_color_near(self, image, box, expected, tolerance, minimum_pixels=0, maximum_pixels=None):
        x0, y0, x1, y1 = box
        matches = 0
        for y in range(y0, y1):
            for x in range(x0, x1):
                pixel = image.getpixel((x, y))
                if max(abs(a - b) for a, b in zip(pixel, expected)) <= tolerance:
                    matches += 1
        self.assertGreaterEqual(matches, minimum_pixels)
        if maximum_pixels is not None:
            self.assertLessEqual(matches, maximum_pixels)


if __name__ == "__main__":
    unittest.main()
