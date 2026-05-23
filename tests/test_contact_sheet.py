import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from photo_to_pattern.planning.contact_sheet import looks_like_orthographic_contact_sheet, split_orthographic_contact_sheet


class ContactSheetTests(unittest.TestCase):
    def test_split_removes_panel_captions_and_fits_subject(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "labeled_sheet.png"
            image = Image.new("RGBA", (1600, 980), (255, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            panels = [
                ((48, 30, 800, 337), "1. FRONT VIEW", (322, 78, 498, 282)),
                ((822, 30, 1552, 337), "4. TOI", (1050, 92, 1342, 262)),
                ((48, 383, 421, 700), "1. FRONT VIEW", (148, 438, 312, 666)),
                ((437, 383, 803, 700), "T VIEW", (540, 438, 700, 666)),
                ((822, 383, 1190, 700), "3. BACK VIEW", (930, 438, 1090, 666)),
                ((1210, 383, 1552, 700), "4. TOP VIEW", (1280, 438, 1482, 642)),
            ]
            for panel, label, subject in panels:
                draw.rectangle(panel, fill=(246, 246, 248, 255))
                draw.ellipse(subject, fill=(230, 125, 52, 255))
                draw.text((panel[0] + 105, panel[3] - 34), label, fill=(0, 0, 0, 255))
            image.save(source)

            self.assertTrue(looks_like_orthographic_contact_sheet(source))
            outputs = split_orthographic_contact_sheet(source, root / "views")

            self.assertEqual(len(outputs), 4)
            for output in outputs:
                extracted = Image.open(output).convert("RGBA")
                bbox = _non_white_bbox(extracted)
                self.assertIsNotNone(bbox, output.name)
                assert bbox is not None
                left, top, right, bottom = bbox
                width = right - left
                height = bottom - top
                self.assertGreater(width, extracted.width * 0.70, output.name)
                self.assertGreater(height, extracted.height * 0.70, output.name)
                self.assertLess(_dark_pixel_ratio(extracted), 0.002, output.name)

    def test_detection_rejects_single_wide_character_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "single_character.png"
            image = Image.new("RGBA", (1600, 980), (255, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.ellipse((360, 120, 1240, 870), fill=(230, 125, 52, 255))
            draw.ellipse((620, 280, 720, 380), fill=(30, 30, 30, 255))
            draw.ellipse((880, 280, 980, 380), fill=(30, 30, 30, 255))
            image.save(source)

            self.assertFalse(looks_like_orthographic_contact_sheet(source))


def _non_white_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    mask = image.convert("RGBA").point(lambda value: value)
    pixels = mask.load()
    min_x, min_y = image.width, image.height
    max_x = max_y = -1
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha > 24 and not (red >= 242 and green >= 242 and blue >= 242):
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x < min_x:
        return None
    return min_x, min_y, max_x + 1, max_y + 1


def _dark_pixel_ratio(image: Image.Image) -> float:
    pixels = image.convert("RGBA").load()
    dark = 0
    total = max(1, image.width * image.height)
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha > 24 and red < 70 and green < 70 and blue < 70:
                dark += 1
    return dark / total


if __name__ == "__main__":
    unittest.main()
