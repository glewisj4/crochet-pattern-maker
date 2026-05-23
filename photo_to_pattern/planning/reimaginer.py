"""Amigurumi-reference re-imagining boundary."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


class AmigurumiReimaginer:
    """Create amigurumi-friendly references from uploaded images.

    The default implementation is an offline simplification fallback. A future
    model-backed implementation should preserve identity while generating a
    plush/amigurumi orthographic turnaround.
    """

    def reimagine(self, image_path: str | Path, output_path: str | Path) -> Path:
        source = Path(image_path)
        destination = Path(output_path)
        image = Image.open(source).convert("RGBA")
        simplified = _posterize_subject(image)
        destination.parent.mkdir(parents=True, exist_ok=True)
        simplified.save(destination)
        return destination


def _posterize_subject(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    rgb = image.convert("RGB").filter(ImageFilter.SMOOTH_MORE)
    rgb = ImageOps.posterize(rgb, 4)
    rgb = ImageOps.autocontrast(rgb)
    result = rgb.convert("RGBA")
    result.putalpha(alpha)
    return result

