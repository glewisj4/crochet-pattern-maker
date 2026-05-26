import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from photo_to_pattern.core import (
    Face,
    Mesh,
    MeshValidationError,
    OrthoProcessingError,
    Vertex,
    build_watertight_mesh_from_orthographic,
    load_orthographic_views,
)


class Phase1VisionPipelineTests(unittest.TestCase):
    def test_orthographic_ingestion_extracts_normalized_silhouettes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            front = _synthetic_view(root / "front.png", (220, 260), (50, 22, 170, 238))
            side = _synthetic_view(root / "side.png", (180, 260), (64, 24, 116, 236))

            views = load_orthographic_views(front=front, side=side, mask_size=48)

            self.assertEqual(views.front.kind, "front")
            self.assertEqual(views.side.kind, "side")
            self.assertEqual(len(views.front.mask), 48)
            self.assertEqual(len(views.front.mask[0]), 48)
            self.assertGreater(views.front.width, views.side.width)
            self.assertGreater(views.front.confidence, 0.4)

    def test_empty_view_raises_processing_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            front = root / "front.png"
            side = _synthetic_view(root / "side.png", (180, 260), (64, 24, 116, 236))
            Image.new("RGBA", (220, 260), (255, 255, 255, 255)).save(front)

            with self.assertRaises(OrthoProcessingError):
                load_orthographic_views(front=front, side=side)

    def test_builds_watertight_low_poly_mesh_from_pair(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            front = _synthetic_view(root / "front.png", (220, 260), (50, 22, 170, 238))
            side = _synthetic_view(root / "side.png", (180, 260), (64, 24, 116, 236))
            views = load_orthographic_views(front=front, side=side, mask_size=64)

            mesh = build_watertight_mesh_from_orthographic(views, radial_segments=16, height_segments=8)

            mesh.validate()
            self.assertEqual(len(mesh.vertices), 2 + (8 - 1) * 16)
            self.assertEqual(len(mesh.faces), 16 * 2 * (8 - 1))
            self.assertGreater(mesh.signed_volume(), 0.0)
            lower, upper = mesh.bounds()
            self.assertGreater(upper.x - lower.x, upper.y - lower.y)
            self.assertGreater(upper.z - lower.z, upper.y - lower.y)

    def test_mesh_rings_remain_inside_front_and_side_silhouettes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            front = _waisted_view(root / "front.png", (180, 240), wide=True)
            side = _waisted_view(root / "side.png", (180, 240), wide=False)
            views = load_orthographic_views(front=front, side=side, mask_size=64)

            mesh = build_watertight_mesh_from_orthographic(views, radial_segments=16, height_segments=8)

            radius_z = (views.front.height + views.side.height) / 4.0
            tolerance = 1.5
            for vertex in mesh.vertices[1:-1]:
                normalized_height = (radius_z - vertex.z) / (2.0 * radius_z)
                allowed_front_width = views.front.width * _mask_width_at(views.front.mask, normalized_height)
                allowed_side_depth = views.side.width * _mask_width_at(views.side.mask, normalized_height)
                self.assertLessEqual(abs(vertex.x) * 2.0, allowed_front_width + tolerance)
                self.assertLessEqual(abs(vertex.y) * 2.0, allowed_side_depth + tolerance)

    def test_mesh_exports_obj(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            front = _synthetic_view(root / "front.png", (160, 200), (42, 24, 118, 176))
            side = _synthetic_view(root / "side.png", (140, 200), (56, 24, 84, 176))
            mesh = build_watertight_mesh_from_orthographic(
                load_orthographic_views(front=front, side=side),
                radial_segments=12,
                height_segments=6,
            )

            output = mesh.export_obj(root / "mesh.obj")

            text = output.read_text(encoding="utf-8")
            self.assertIn("v ", text)
            self.assertIn("f ", text)

    def test_broken_mesh_fails_validation(self):
        mesh = Mesh(
            vertices=(
                Vertex(0.0, 0.0, 0.0),
                Vertex(1.0, 0.0, 0.0),
                Vertex(0.0, 1.0, 0.0),
                Vertex(0.0, 0.0, 1.0),
            ),
            faces=(Face(0, 1, 2), Face(0, 1, 3)),
        )

        with self.assertRaises(MeshValidationError):
            mesh.validate()


def _synthetic_view(path: Path, size: tuple[int, int], bbox: tuple[int, int, int, int]) -> Path:
    image = Image.new("RGBA", size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse(bbox, fill=(220, 120, 60, 255))
    image.save(path)
    return path


def _waisted_view(path: Path, size: tuple[int, int], *, wide: bool) -> Path:
    image = Image.new("RGBA", size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    if wide:
        draw.rectangle((30, 30, 150, 95), fill=(220, 120, 60, 255))
        draw.rectangle((70, 95, 110, 145), fill=(220, 120, 60, 255))
        draw.rectangle((30, 145, 150, 210), fill=(220, 120, 60, 255))
    else:
        draw.rectangle((65, 30, 115, 95), fill=(220, 120, 60, 255))
        draw.rectangle((30, 95, 150, 145), fill=(220, 120, 60, 255))
        draw.rectangle((65, 145, 115, 210), fill=(220, 120, 60, 255))
    image.save(path)
    return path


def _mask_width_at(mask: tuple[tuple[bool, ...], ...], normalized_height: float) -> float:
    row_index = max(0, min(len(mask) - 1, round(normalized_height * (len(mask) - 1))))
    row = mask[row_index]
    columns = [index for index, value in enumerate(row) if value]
    if not columns:
        return 0.0
    return (max(columns) - min(columns) + 1) / max(1, len(row))


if __name__ == "__main__":
    unittest.main()
