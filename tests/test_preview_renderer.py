import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from photo_to_pattern.image_regions import CharacterRegionAnalyzer
from photo_to_pattern.preview import render_analysis_preview


class PreviewRendererTests(unittest.TestCase):
    def test_renders_preview_image(self):
        image = Image.new("RGBA", (180, 220), (255, 255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((45, 30, 145, 155), fill=(250, 190, 12, 255))
        draw.ellipse((60, 55, 120, 115), fill=(45, 30, 18, 255))
        draw.ellipse((88, 68, 106, 92), fill=(245, 238, 150, 255))
        draw.rectangle((62, 150, 78, 200), fill=(50, 35, 18, 255))
        draw.rectangle((108, 150, 124, 200), fill=(50, 35, 18, 255))

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.png"
            output = Path(temp_dir) / "preview.jpg"
            image.save(source)
            analysis = CharacterRegionAnalyzer(max_dimension=220).analyze(source)
            rendered = render_analysis_preview(source, analysis, output)

            self.assertTrue(rendered.exists())
            self.assertGreater(rendered.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
