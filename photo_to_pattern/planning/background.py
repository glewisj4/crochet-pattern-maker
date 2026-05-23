"""Local background removal for planning views."""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image


def remove_background(
    image_path: str | Path,
    output_path: str | Path,
    *,
    tolerance: int = 34,
    padding: int = 36,
) -> Path:
    """Remove a mostly-flat background using border flood fill and crop to subject."""

    source = Path(image_path)
    destination = Path(output_path)
    image = Image.open(source).convert("RGBA")
    pixels = image.load()
    width, height = image.size
    bg = _median_border_color(image)

    transparent: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.popleft()
        if (x, y) in transparent or not (0 <= x < width and 0 <= y < height):
            continue
        r, g, b, a = pixels[x, y]
        if a < 20 or _distance((r, g, b), bg) <= tolerance:
            transparent.add((x, y))
            queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    for x, y in transparent:
        pixels[x, y] = (255, 255, 255, 0)

    cropped = _crop_to_alpha(image, padding)
    destination.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(destination)
    return destination


def normalize_canvas(image_path: str | Path, output_path: str | Path, size: tuple[int, int] = (520, 520)) -> Path:
    """Center a transparent image on a fixed canvas."""

    image = Image.open(image_path).convert("RGBA")
    canvas = Image.new("RGBA", size, (255, 255, 255, 0))
    scale = min((size[0] - 36) / image.width, (size[1] - 36) / image.height, 1.0)
    resized = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))))
    x = (size[0] - resized.width) // 2
    y = (size[1] - resized.height) // 2
    canvas.alpha_composite(resized, (x, y))
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination)
    return destination


def foreground_bbox(image_path: str | Path) -> tuple[int, int, int, int]:
    image = Image.open(image_path).convert("RGBA")
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return (0, 0, image.width, image.height)
    x0, y0, x1, y1 = bbox
    return (x0, y0, x1 - x0, y1 - y0)


def _crop_to_alpha(image: Image.Image, padding: int) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return image
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - padding)
    y0 = max(0, y0 - padding)
    x1 = min(image.width, x1 + padding)
    y1 = min(image.height, y1 + padding)
    return image.crop((x0, y0, x1, y1))


def _median_border_color(image: Image.Image) -> tuple[int, int, int]:
    samples = []
    pixels = image.load()
    width, height = image.size
    step = max(1, min(width, height) // 80)
    for x in range(0, width, step):
        samples.append(pixels[x, 0][:3])
        samples.append(pixels[x, height - 1][:3])
    for y in range(0, height, step):
        samples.append(pixels[0, y][:3])
        samples.append(pixels[width - 1, y][:3])
    channels = list(zip(*samples))
    return tuple(sorted(channel)[len(channel) // 2] for channel in channels)  # type: ignore[return-value]


def _distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return sum((left - right) ** 2 for left, right in zip(a, b)) ** 0.5

