"""Detect and split orthographic multi-view contact sheets."""

from __future__ import annotations

from pathlib import Path

from collections import deque

from PIL import Image, ImageStat


def looks_like_orthographic_contact_sheet(image_path: str | Path) -> bool:
    """Return true for one-image sheets containing front/side/back/top panels."""

    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    aspect = width / max(1, height)
    if width < 1000 or height < 700 or not 1.35 <= aspect <= 1.95:
        return False

    lower_band = image.crop((0, round(height * 0.70), width, round(height * 0.78)))
    top_gap = image.crop((0, round(height * 0.34), width, round(height * 0.40)))
    label_evidence = (
        _dark_pixel_ratio(lower_band) > 0.004
        or _dark_pixel_ratio(top_gap) > 0.002
        or _panel_caption_evidence(image)
    )
    gutter_score = _pale_gutter_score(image)
    if _layout_panels_have_subjects(image) and label_evidence and gutter_score > 0.78:
        return True

    # Contact sheets usually have dark labels/borders in otherwise pale gutters.
    return _dark_pixel_ratio(lower_band) > 0.004 and (
        _dark_pixel_ratio(top_gap) > 0.002 or gutter_score > 0.78
    )


def split_orthographic_contact_sheet(image_path: str | Path, output_dir: str | Path) -> list[Path]:
    """Split a common orthographic sheet layout into canonical view images."""

    source = Path(image_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    image = Image.open(source).convert("RGBA")
    width, height = image.size

    # Supports the common AI/contact-sheet layout:
    # top row: large front + large top
    # bottom row: front, side, back, top thumbnails.
    boxes = {
        "front": (0.030, 0.030, 0.500, 0.344),
        "side": (0.273, 0.391, 0.502, 0.714),
        "back": (0.514, 0.391, 0.744, 0.714),
        "top": (0.514, 0.030, 0.970, 0.344),
    }

    outputs: list[Path] = []
    for kind, box in boxes.items():
        crop = image.crop(_scale_box(box, width, height))
        crop = _clean_view_crop(crop)
        path = destination / f"{kind}_view.png"
        crop.save(path)
        outputs.append(path)
    return outputs


def _scale_box(box: tuple[float, float, float, float], width: int, height: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    return round(x0 * width), round(y0 * height), round(x1 * width), round(y1 * height)


def _layout_panels_have_subjects(image: Image.Image) -> bool:
    width, height = image.size
    boxes = (
        (0.030, 0.030, 0.500, 0.344),
        (0.273, 0.391, 0.502, 0.714),
        (0.514, 0.391, 0.744, 0.714),
        (0.514, 0.030, 0.970, 0.344),
    )
    hits = 0
    for box in boxes:
        crop = image.crop(_scale_box(box, width, height)).convert("RGBA")
        if _largest_subject_touches_panel_edges(crop):
            continue
        cleaned = _clean_view_crop(crop)
        components = _foreground_components(cleaned)
        if not components:
            continue
        largest = max(components, key=lambda component: component[4])
        crop_area = max(1, cleaned.width * cleaned.height)
        if largest[4] / crop_area >= 0.035 and not _looks_like_caption_component(largest, cleaned.size):
            hits += 1
    return hits >= 3


def _panel_caption_evidence(image: Image.Image) -> bool:
    width, height = image.size
    boxes = (
        (0.030, 0.030, 0.500, 0.344),
        (0.273, 0.391, 0.502, 0.714),
        (0.514, 0.391, 0.744, 0.714),
        (0.514, 0.030, 0.970, 0.344),
    )
    hits = 0
    for box in boxes:
        x0, y0, x1, y1 = _scale_box(box, width, height)
        panel = image.crop((x0, y0, x1, y1)).convert("RGB")
        band_top = round(panel.height * 0.72)
        lower = panel.crop((0, band_top, panel.width, panel.height))
        upper = panel.crop((0, 0, panel.width, round(panel.height * 0.20)))
        if _dark_pixel_ratio(lower) > 0.0015 or _dark_pixel_ratio(upper) > 0.0015:
            hits += 1
    return hits >= 2


def _largest_subject_touches_panel_edges(crop: Image.Image) -> bool:
    rgba = crop.convert("RGBA")
    _erase_caption_band_glyphs(rgba)
    components = _foreground_components(rgba)
    if not components:
        return False
    left, top, right, bottom, area = max(components, key=lambda component: component[4])
    if area < max(64, rgba.width * rgba.height * 0.02):
        return False
    margin_x = rgba.width * 0.02
    margin_y = rgba.height * 0.02
    touches = 0
    touches += int(left <= margin_x)
    touches += int(top <= margin_y)
    touches += int(right >= rgba.width - margin_x)
    touches += int(bottom >= rgba.height - margin_y)
    return touches >= 2


def _pale_gutter_score(image: Image.Image) -> float:
    width, height = image.size
    gutters = (
        image.crop((round(width * 0.49), 0, round(width * 0.52), height)),
        image.crop((0, round(height * 0.34), width, round(height * 0.40))),
        image.crop((0, round(height * 0.72), width, round(height * 0.78))),
    )
    pale = 0
    total = 0
    for gutter in gutters:
        rgb = gutter.convert("RGB")
        pixels = rgb.load()
        for yy in range(rgb.height):
            for xx in range(rgb.width):
                red, green, blue = pixels[xx, yy]
                total += 1
                if red >= 225 and green >= 225 and blue >= 225:
                    pale += 1
    return pale / max(1, total)


def _dark_pixel_ratio(image: Image.Image) -> float:
    gray = image.convert("L")
    histogram = gray.histogram()
    dark = sum(histogram[:70])
    total = max(1, image.width * image.height)
    # Guard against uniformly dark photos passing because the whole band is content.
    mean = ImageStat.Stat(gray).mean[0]
    if mean < 180:
        return 0.0
    return dark / total


def _clean_view_crop(image: Image.Image) -> Image.Image:
    """Trim panel labels/gutters so the extracted view is subject-first."""

    rgba = image.convert("RGBA")
    _erase_caption_band_glyphs(rgba)
    components = _foreground_components(rgba)
    if not components:
        return rgba

    largest_area = max(component[4] for component in components)
    kept = [
        component
        for component in components
        if component[4] >= max(64, largest_area * 0.08) and not _looks_like_caption_component(component, rgba.size)
    ]
    if not kept:
        kept = [max(components, key=lambda component: component[4])]

    left = min(component[0] for component in kept)
    top = min(component[1] for component in kept)
    right = max(component[2] for component in kept)
    bottom = max(component[3] for component in kept)
    return rgba.crop(_padded_box((left, top, right, bottom), rgba.size, 0.10))


def _erase_caption_band_glyphs(image: Image.Image) -> None:
    pixels = image.load()
    top_limit = round(image.height * 0.18)
    bottom_start = round(image.height * 0.70)
    for yy in list(range(0, top_limit)) + list(range(bottom_start, image.height)):
        for xx in range(image.width):
            red, green, blue, alpha = pixels[xx, yy]
            if alpha > 24 and red < 90 and green < 90 and blue < 90:
                pixels[xx, yy] = (255, 255, 255, 0)


def _foreground_components(image: Image.Image) -> list[tuple[int, int, int, int, int]]:
    pixels = image.load()
    width, height = image.size
    visited: set[tuple[int, int]] = set()
    components: list[tuple[int, int, int, int, int]] = []

    for yy in range(height):
        for xx in range(width):
            if (xx, yy) in visited or not _is_subject_pixel(pixels[xx, yy]):
                continue
            queue: deque[tuple[int, int]] = deque([(xx, yy)])
            visited.add((xx, yy))
            min_x = max_x = xx
            min_y = max_y = yy
            area = 0
            while queue:
                x, y = queue.popleft()
                area += 1
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if not (0 <= nx < width and 0 <= ny < height) or (nx, ny) in visited:
                        continue
                    if _is_subject_pixel(pixels[nx, ny]):
                        visited.add((nx, ny))
                        queue.append((nx, ny))
            components.append((min_x, min_y, max_x + 1, max_y + 1, area))
    return components


def _is_subject_pixel(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = pixel
    if alpha <= 24:
        return False
    return not (red >= 242 and green >= 242 and blue >= 242)


def _looks_like_caption_component(component: tuple[int, int, int, int, int], size: tuple[int, int]) -> bool:
    left, top, right, bottom, area = component
    width, height = right - left, bottom - top
    image_width, image_height = size
    in_caption_band = top > image_height * 0.70 or bottom < image_height * 0.18
    small_glyph = area < image_width * image_height * 0.015 and height < image_height * 0.18
    return in_caption_band and small_glyph and width < image_width * 0.45


def _padded_box(box: tuple[int, int, int, int], size: tuple[int, int], ratio: float) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    pad_x = max(4, round(width * ratio))
    pad_y = max(4, round(height * ratio))
    return (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(size[0], right + pad_x),
        min(size[1], bottom + pad_y),
    )
