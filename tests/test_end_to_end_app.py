import unittest

from photo_to_pattern.app import PhotoToPatternApp
from photo_to_pattern.vision_voxelizer import ImageFrame


class EndToEndAppTests(unittest.TestCase):
    def test_generates_pattern_and_qa_from_frame(self):
        app = PhotoToPatternApp()

        result = app.from_frame(ImageFrame(width=120, height=160, source="synthetic.png"))
        rendered = result.render()

        self.assertIn("Style: Spiral rounds", rendered)
        self.assertIn("MR", rendered)
        self.assertIn("Inv Dec", rendered)
        self.assertIn("QA report:", rendered)
        self.assertTrue(result.pattern_map.rounds)


if __name__ == "__main__":
    unittest.main()

