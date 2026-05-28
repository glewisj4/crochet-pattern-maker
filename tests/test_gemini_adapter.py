"""Unit tests for Pluggable Gemini VLM API Adapter and Fallback Planning."""

from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from photo_to_pattern.image_regions import CharacterAnalysis, ColorRegion
from photo_to_pattern.planning.agent import HeuristicPlanningAgent
from photo_to_pattern.planning.gemini_adapter import GeminiAdapter, GeminiVisionError
from photo_to_pattern.planning.models import PlanningOptions, PlanningView


class GeminiAdapterTests(unittest.TestCase):

    def test_adapter_success_parsing(self):
        adapter = GeminiAdapter()
        mock_response_data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "parts": [
                                        {
                                            "name": "Head",
                                            "primitive": "sphere",
                                            "category": "Primary Body",
                                            "relative_size": [0.8, 0.8, 0.8],
                                            "color_hex": "#e87e40",
                                            "attachment": "neck",
                                            "confidence": 0.95
                                        }
                                    ],
                                    "details": [
                                        {
                                            "name": "Eyes",
                                            "method": "safety eyes",
                                            "category": "Facial Embroidery",
                                            "placement": "face",
                                            "color_hex": "000000",
                                            "confidence": 0.90
                                        }
                                    ]
                                })
                            }
                        ]
                    }
                }
            ]
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_response_data).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            with tempfile.TemporaryDirectory() as temp_dir:
                img_path = Path(temp_dir) / "dummy.png"
                img_path.write_bytes(b"dummy image data")

                res = adapter.analyze_character(img_path, "dummy_api_key")
                self.assertIsNotNone(res)
                self.assertIn("parts", res)
                self.assertIn("details", res)
                self.assertEqual(res["parts"][0]["name"], "Head")
                self.assertEqual(res["details"][0]["name"], "Eyes")

    def test_adapter_markdown_codeblock_cleaning(self):
        adapter = GeminiAdapter()
        mock_response_data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "```json\n{\n  \"parts\": [{\"name\":\"Head\",\"category\":\"Primary Body\",\"primitive\":\"sphere\",\"relative_size\":[0.5,0.5,0.5],\"color_hex\":\"#e87e40\",\"attachment\":\"root\",\"confidence\":0.9}],\n  \"details\": []\n}\n```"
                            }
                        ]
                    }
                }
            ]
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_response_data).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            with tempfile.TemporaryDirectory() as temp_dir:
                img_path = Path(temp_dir) / "dummy.png"
                img_path.write_bytes(b"dummy image data")

                res = adapter.analyze_character(img_path, "dummy_api_key")
                self.assertIsNotNone(res)
                self.assertEqual(res["parts"][0]["category"], "Primary Body")

    def test_adapter_http_error(self):
        adapter = GeminiAdapter()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                "https://example.com", 500, "Internal Error", {}, None
            )

            with tempfile.TemporaryDirectory() as temp_dir:
                img_path = Path(temp_dir) / "dummy.png"
                img_path.write_bytes(b"dummy image data")

                with self.assertRaises(GeminiVisionError):
                    adapter.analyze_character(img_path, "dummy_api_key")

    def test_adapter_url_error(self):
        adapter = GeminiAdapter()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("timeout")

            with tempfile.TemporaryDirectory() as temp_dir:
                img_path = Path(temp_dir) / "dummy.png"
                img_path.write_bytes(b"dummy image data")

                with self.assertRaises(GeminiVisionError):
                    adapter.analyze_character(img_path, "dummy_api_key")

    def test_adapter_missing_key_raises(self):
        adapter = GeminiAdapter()
        with tempfile.TemporaryDirectory() as temp_dir:
            img_path = Path(temp_dir) / "dummy.png"
            img_path.write_bytes(b"dummy image data")

            with self.assertRaises(GeminiVisionError):
                adapter.analyze_character(img_path, "")

    def test_adapter_rejects_missing_semantic_category(self):
        adapter = GeminiAdapter()
        mock_response_data = {
            "candidates": [{"content": {"parts": [{"text": json.dumps({"parts": [{"name": "Head"}], "details": []})}]}}]
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_response_data).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp
            with tempfile.TemporaryDirectory() as temp_dir:
                img_path = Path(temp_dir) / "dummy.png"
                img_path.write_bytes(b"dummy image data")
                with self.assertRaises(GeminiVisionError):
                    adapter.analyze_character(img_path, "dummy_api_key")

    def test_planning_agent_gemini_success(self):
        agent = HeuristicPlanningAgent()
        options = PlanningOptions(gemini_api_key="valid_key", head_scale=1.5)

        # Set up a mock analysis and front view image
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
                source="test",
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
                        "color_hex": "e87e40",  # test parsing hex without '#'
                        "attachment": "body top",
                        "confidence": 0.95
                    },
                    {
                        "name": "Body",
                        "primitive": "ovoid",
                        "category": "Primary Body",
                        "relative_size": {"width_ratio": 0.5, "height_ratio": 0.7, "depth_ratio": 0.5},  # test dict format
                        "color_hex": "#e87e40",
                        "attachment": "root",
                        "confidence": 0.90
                    }
                ],
                "details": [
                    {
                        "name": "Snout",
                        "method": "crochet applique snout",
                        "category": "Accents",
                        "placement": "front center",
                        "color_hex": "#ffffff",
                        "confidence": 0.88
                    }
                ]
            }

            with patch.object(GeminiAdapter, "analyze_character", return_value=mock_gemini_res):
                model = agent.build_model(
                    title="test_fox",
                    options=options,
                    views=(view,),
                    analysis=analysis
                )

                self.assertTrue(any("Turnaround features extracted via Gemini 1.5 Flash VLM." in w for w in model.warnings))
                self.assertEqual(len(model.parts), 2)
                
                # Verify Head part is scaled and mapped correctly
                head_part = next(p for p in model.parts if p.name == "Head")
                self.assertEqual(head_part.primitive, "sphere")
                self.assertEqual(head_part.color, (232, 126, 64))
                # head scale is 1.5. raw is 0.6. scaled is 0.9
                self.assertEqual(head_part.relative_size, (0.9, 0.9, 0.9))
                self.assertEqual(head_part.confidence, 0.95)

                # Verify Body dict parsed correctly
                body_part = next(p for p in model.parts if p.name == "Body")
                self.assertEqual(body_part.relative_size, (0.5, 0.7, 0.5))

                # Verify snout mapped and tier prefix appended
                snout_detail = next(d for d in model.details if d.name == "Snout")
                self.assertTrue(snout_detail.method.startswith("tier:"))
                self.assertEqual(snout_detail.color, (255, 255, 255))
                self.assertEqual(snout_detail.color_hex, "#ffffff")

    def test_planning_agent_raises_on_absent_key(self):
        agent = HeuristicPlanningAgent()
        options = PlanningOptions(gemini_api_key="")  # absent key

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
                source="test",
                image_size=(100, 100),
                foreground_bbox=(10, 10, 80, 80),
                regions=(region,),
                warnings=(),
            )

            with self.assertRaises(GeminiVisionError):
                agent.build_model(title="test_fox", options=options, views=(view,), analysis=analysis)

    def test_planning_agent_raises_on_adapter_failure(self):
        agent = HeuristicPlanningAgent()
        options = PlanningOptions(gemini_api_key="some_key")

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
                source="test",
                image_size=(100, 100),
                foreground_bbox=(10, 10, 80, 80),
                regions=(region,),
                warnings=(),
            )

            with patch.object(GeminiAdapter, "analyze_character", side_effect=GeminiVisionError("boom")):
                with self.assertRaises(GeminiVisionError):
                    agent.build_model(title="test_fox", options=options, views=(view,), analysis=analysis)

    def test_planning_agent_rejects_low_confidence_vlm(self):
        agent = HeuristicPlanningAgent()
        options = PlanningOptions(gemini_api_key="valid_key")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_img = root / "front.png"
            Image.new("RGBA", (100, 100), (255, 255, 255, 255)).save(source_img)
            view = PlanningView("front", source_img, source_img)
            analysis = CharacterAnalysis(source="test", image_size=(100, 100), foreground_bbox=(10, 10, 80, 80), regions=(), warnings=())
            mock_gemini_res = {
                "parts": [{"name": "Head", "primitive": "sphere", "category": "Primary Body", "relative_size": [0.6, 0.6, 0.6], "confidence": 0.74}],
                "details": [],
            }
            with patch.object(GeminiAdapter, "analyze_character", return_value=mock_gemini_res):
                with self.assertRaises(GeminiVisionError):
                    agent.build_model(title="test", options=options, views=(view,), analysis=analysis)


if __name__ == "__main__":
    unittest.main()
