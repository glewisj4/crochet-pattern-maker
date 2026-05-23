import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from photo_to_pattern.image_regions import CharacterRegionAnalyzer


class ImageRegionTests(unittest.TestCase):
    def test_detects_body_mask_eye_and_legs(self):
        image = Image.new("RGBA", (180, 220), (255, 255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((45, 30, 145, 155), fill=(250, 190, 12, 255))
        draw.ellipse((60, 55, 120, 115), fill=(45, 30, 18, 255))
        draw.ellipse((88, 68, 106, 92), fill=(245, 238, 150, 255))
        draw.rectangle((62, 150, 78, 200), fill=(50, 35, 18, 255))
        draw.rectangle((108, 150, 124, 200), fill=(50, 35, 18, 255))

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "character.png"
            image.save(path)
            analysis = CharacterRegionAnalyzer(max_dimension=220).analyze(path)

        self.assertTrue(analysis.regions_of_kind("body"))
        self.assertTrue(analysis.regions_of_kind("face_mask"))
        self.assertTrue(analysis.regions_of_kind("eye"))
        self.assertGreaterEqual(len(analysis.regions_of_kind("leg")), 2)
        first_leg = analysis.regions_of_kind("leg")[0]
        self.assertTrue(first_leg.contour)
        self.assertIsNotNone(first_leg.major_axis)
        self.assertGreaterEqual(len(first_leg.centerline), 2)
        self.assertIsNotNone(first_leg.median_thickness)

    def test_bent_leg_region_preserves_polyline_centerline(self):
        image = Image.new("RGBA", (220, 220), (255, 255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((50, 20, 170, 140), fill=(250, 190, 12, 255))
        draw.ellipse((75, 45, 135, 105), fill=(45, 30, 18, 255))
        draw.ellipse((95, 60, 115, 85), fill=(245, 238, 150, 255))
        draw.line((90, 135, 65, 165, 40, 165), fill=(50, 35, 18, 255), width=18)
        draw.line((135, 135, 160, 170, 185, 170), fill=(50, 35, 18, 255), width=18)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bent.png"
            image.save(path)
            analysis = CharacterRegionAnalyzer(max_dimension=220).analyze(path)

        legs = analysis.regions_of_kind("leg")
        self.assertGreaterEqual(len(legs), 2)
        longest = max(legs, key=lambda region: len(region.centerline))
        self.assertGreaterEqual(len(longest.centerline), 4)


if __name__ == "__main__":
    unittest.main()
