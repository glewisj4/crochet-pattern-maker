"""Image loading boundary for future Pillow/OpenCV adapters."""

import struct
from pathlib import Path

from .models import ImageFrame


class UnsupportedImageBackendError(RuntimeError):
    """Raised when no decoding backend is available for the requested image."""


def load_image(path: str | Path) -> ImageFrame:
    """Load image metadata and pixels when a backend is available."""

    image_path = Path(path)
    source = str(image_path)
    suffix = image_path.suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        raise UnsupportedImageBackendError(f"Unsupported image type: {suffix}")

    try:
        from PIL import Image

        image = Image.open(image_path).convert("RGBA")
        return ImageFrame(width=image.width, height=image.height, source=source, pixels=image)
    except Exception:
        width, height = _read_dimensions(image_path, suffix)
        return ImageFrame(width=width, height=height, source=source, pixels=None)


def _read_dimensions(path: Path, suffix: str) -> tuple[int, int]:
    data = path.read_bytes()
    if suffix == ".png":
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise UnsupportedImageBackendError("Invalid PNG header.")
        return struct.unpack(">II", data[16:24])
    if suffix == ".bmp":
        if data[:2] != b"BM":
            raise UnsupportedImageBackendError("Invalid BMP header.")
        width, height = struct.unpack("<ii", data[18:26])
        return abs(width), abs(height)
    if suffix in {".jpg", ".jpeg"}:
        return _read_jpeg_dimensions(data)
    if suffix == ".webp":
        return _read_webp_dimensions(data)
    raise UnsupportedImageBackendError(f"Unsupported image type: {suffix}")


def _read_jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if data[:2] != b"\xff\xd8":
        raise UnsupportedImageBackendError("Invalid JPEG header.")
    index = 2
    while index < len(data):
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(data):
            break
        length = struct.unpack(">H", data[index : index + 2])[0]
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if index + 7 > len(data):
                break
            height, width = struct.unpack(">HH", data[index + 3 : index + 7])
            return width, height
        index += length
    raise UnsupportedImageBackendError("Could not read JPEG dimensions.")


def _read_webp_dimensions(data: bytes) -> tuple[int, int]:
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise UnsupportedImageBackendError("Invalid WebP header.")
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    if chunk == b"VP8 ":
        width, height = struct.unpack("<HH", data[26:30])
        return width & 0x3FFF, height & 0x3FFF
    if chunk == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    raise UnsupportedImageBackendError("Unsupported WebP encoding.")
