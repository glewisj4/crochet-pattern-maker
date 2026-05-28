"""Unit tests for VisionDeconstructionAgent and DeconstructedModel."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from photo_to_pattern.image_regions import CharacterAnalysis, ColorRegion
from photo_to_pattern.planning.deconstructor import (
    DeconstructedModel,
    VisionDeconstructionAgent,
)
from photo_to_pattern.planning.gemini_adapter import GeminiAdapter, GeminiVisionError
from photo_to_pattern.planning.models import PlanningOptions, PlanningView


class DeconstructorTests(unittest.TestCase):

    def test_deconstructor_gemini_success(self):
        agent = VisionDeconstructionAgent()
        options = PlanningOptions(gemini_api_key="valid_key", head_scale=1.5)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_img = root / "front.png"
            image = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
            image.save(source_img)

            view = PlanningView("front", source_img, source_img)
            region = ColorRegion(
                kind="body",
                bbox=(10, 10, 80, 80),
                area=6400,
                centroid=(50.0, 50.0),
                average_color=(232, 126, 64),
                confidence=1.0,
            )
            analysis = CharacterAnalysis(
                source="test_fox",
                image_size=(100, 100),
                foreground_bbox=(10, 10, 80, 80),
                regions=(region,),
                warnings=(),
            )

            mock_gemini_res = {
                "parts": [
                    {
                        "name": "Head",
                        "primitive": "sphere",
                        "category": "Primary Body",
                        "relative_size": [0.6, 0.6, 0.6],
                        "color_hex": "e87e40",
                        "attachment": "body top",
                        "confidence": 0.95,
                        "pose_position": [1.0, 2.0, 3.0],
                        "rotation_degrees": 45.0,
                    },
                    {
                        "name": "Body",
                        "primitive": "ovoid",
                        "category": "Primary Body",
                        "relative_size": {"width_ratio": 0.5, "height_ratio": 0.7, "depth_ratio": 0.5},
                        "color_hex": "#e87e40",
                        "attachment": "root",
                        "confidence": 0.90,
                    }
                ],
                "details": [
                    {
                        "name": "Snout",
                        "method": "crochet applique snout",
                        "category": "Accents",
                        "placement": "front center",
                        "color_hex": "#ffffff",
                        "confidence": 0.88,
                    }
                ]
            }

            with patch.object(GeminiAdapter, "analyze_character", return_value=mock_gemini_res):
                deconstructed = agent.deconstruct(
                    image_paths=[source_img],
                    options=options,
                    views=(view,),
                    analysis=analysis,
                    title="test_fox",
                )

                self.assertIsInstance(deconstructed, DeconstructedModel)
                self.assertEqual(deconstructed.title, "test_fox")
                self.assertIn("Turnaround features extracted via Gemini 1.5 Flash VLM.", deconstructed.warnings)

                # Verify component tree has 3 items
                self.assertEqual(len(deconstructed.component_tree), 3)
                head_node = next(n for n in deconstructed.component_tree if n["name"] == "Head")
                self.assertEqual(head_node["primitive"], "sphere")
                self.assertEqual(head_node["type"], "part")
                self.assertEqual(head_node["category"], "Primary Body")

                # Verify spatial anchors
                head_anchor = next(sa for sa in deconstructed.spatial_anchors if sa["name"] == "Head")
                self.assertEqual(head_anchor["position"], (1.0, 2.0, 3.0))
                self.assertEqual(head_anchor["rotation_degrees"], 45.0)

                # Verify detected colors
                head_color = next(c for c in deconstructed.detected_colors if c["name"] == "Head")
                self.assertEqual(head_color["color"], (232, 126, 64))
                self.assertEqual(head_color["hex"], "#e87e40")

                snout_color = next(c for c in deconstructed.detected_colors if c["name"] == "Snout")
                self.assertEqual(snout_color["color"], (255, 255, 255))
                self.assertEqual(snout_color["hex"], "#ffffff")

    def test_deconstructor_raises_without_gemini_key(self):
        agent = VisionDeconstructionAgent()
        options = PlanningOptions(gemini_api_key="")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_img = root / "front.png"
            image = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
            image.save(source_img)

            view = PlanningView("front", source_img, source_img)
            region = ColorRegion(
                kind="body",
                bbox=(10, 10, 80, 80),
                area=6400,
                centroid=(50.0, 50.0),
                average_color=(232, 126, 64),
                confidence=1.0,
            )
            analysis = CharacterAnalysis(
                source="test_fox",
                image_size=(100, 100),
                foreground_bbox=(10, 10, 80, 80),
                regions=(region,),
                warnings=(),
            )

            with self.assertRaises(GeminiVisionError):
                agent.deconstruct(
                    image_paths=[source_img],
                    options=options,
                    views=(view,),
                    analysis=analysis,
                    title="test_fox",
                )


if __name__ == "__main__":
    unittest.main()
