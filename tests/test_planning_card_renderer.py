import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from photo_to_pattern.planning.card_renderer import _foreground_bbox, _paste_fit, _paste_fit_info, _view_source_label
from photo_to_pattern.planning.models import PlanningView


class PlanningCardRendererTests(unittest.TestCase):
    def test_paste_fit_uses_foreground_bbox_for_white_padding(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "padded.png"
            image = Image.new("RGBA", (400, 400), (255, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.ellipse((150, 100, 250, 300), fill=(220, 80, 40, 255))
            image.save(source)

            canvas = Image.new("RGB", (240, 240), (250, 249, 246))
            pasted = _paste_fit(canvas, source, (20, 20, 200, 200))

            self.assertIsNotNone(pasted)
            _x, _y, width, height = pasted
            self.assertGreaterEqual(height, 190)
            self.assertGreaterEqual(width, 90)

    def test_foreground_bbox_prefers_colored_subject_over_transparent_and_white_gutters(self):
        image = Image.new("RGBA", (300, 220), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 20, 280, 200), fill=(255, 255, 255, 255))
        draw.rectangle((110, 60, 190, 170), fill=(70, 130, 180, 255))

        bbox = _foreground_bbox(image)

        self.assertIsNotNone(bbox)
        left, top, right, bottom = bbox
        self.assertLessEqual(left, 110)
        self.assertLessEqual(top, 60)
        self.assertGreaterEqual(right, 191)
        self.assertGreaterEqual(bottom, 171)
        self.assertGreater(left, 20)
        self.assertGreater(top, 20)
        self.assertLess(right, 280)
        self.assertLess(bottom, 200)

    def test_foreground_bbox_ignores_contact_sheet_caption_text(self):
        image = Image.new("RGBA", (320, 260), (255, 255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((105, 42, 215, 188), fill=(230, 125, 52, 255))
        draw.text((110, 226), "T VIEW", fill=(0, 0, 0, 255))

        bbox = _foreground_bbox(image)

        self.assertIsNotNone(bbox)
        assert bbox is not None
        left, top, right, bottom = bbox
        self.assertLessEqual(left, 105)
        self.assertLessEqual(top, 42)
        self.assertGreaterEqual(right, 216)
        self.assertGreaterEqual(bottom, 189)
        self.assertLess(bottom, 210)

    def test_shape_overlay_coordinates_account_for_foreground_crop(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "offset_subject.png"
            image = Image.new("RGBA", (520, 520), (255, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.rectangle((300, 120, 420, 340), fill=(70, 130, 180, 255))
            image.save(source)

            canvas = Image.new("RGB", (500, 500), (250, 249, 246))
            pasted = _paste_fit_info(canvas, source, (20, 20, 360, 360))

            self.assertIsNotNone(pasted)
            assert pasted is not None
            px, py, pw, ph = pasted.display_box
            crop_left, crop_top, crop_right, crop_bottom = pasted.crop_box
            crop_w = crop_right - crop_left
            crop_h = crop_bottom - crop_top
            guide = (300, 120, 120, 220)
            overlay_x = px + (guide[0] - crop_left) / crop_w * pw
            overlay_y = py + (guide[1] - crop_top) / crop_h * ph
            overlay_w = guide[2] / crop_w * pw
            overlay_h = guide[3] / crop_h * ph

            self.assertGreaterEqual(overlay_x, px - 1)
            self.assertGreaterEqual(overlay_y, py - 1)
            self.assertLessEqual(overlay_x + overlay_w, px + pw + 1)
            self.assertLessEqual(overlay_y + overlay_h, py + ph + 1)
            self.assertGreater(overlay_w, pw * 0.80)
            self.assertGreater(overlay_h, ph * 0.80)

    def test_view_source_labels_are_uploaded_extracted_or_inferred(self):
        source = Path("source.png")
        uploaded = PlanningView(kind="front", source_path=source, cleaned_path=source)
        extracted = PlanningView(
            kind="side",
            source_path=Path("contact_sheet_views/side_view.png"),
            cleaned_path=source,
            note="extracted from one orthographic contact sheet",
        )
        inferred = PlanningView(kind="back", source_path=source, cleaned_path=source, inferred=True)

        self.assertEqual(_view_source_label(uploaded), "Uploaded")
        self.assertEqual(_view_source_label(extracted), "Extracted")
        self.assertEqual(_view_source_label(inferred), "Inferred")


if __name__ == "__main__":
    unittest.main()
