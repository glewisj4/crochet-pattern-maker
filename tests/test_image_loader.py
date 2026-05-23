import struct
import tempfile
import unittest
from pathlib import Path

from photo_to_pattern.vision_voxelizer.image_loader import load_image


class ImageLoaderTests(unittest.TestCase):
    def test_reads_png_dimensions_without_decoder(self):
        png = (
            b"\x89PNG\r\n\x1a\n"
            + struct.pack(">I", 13)
            + b"IHDR"
            + struct.pack(">II", 32, 24)
            + b"\x08\x06\x00\x00\x00"
            + b"\x00\x00\x00\x00"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.png"
            path.write_bytes(png)

            frame = load_image(path)

        self.assertEqual(frame.width, 32)
        self.assertEqual(frame.height, 24)


if __name__ == "__main__":
    unittest.main()
