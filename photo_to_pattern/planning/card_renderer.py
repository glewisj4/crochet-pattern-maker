"""Deterministic planning-card renderer."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import PlanningModel, PlanningView, ShapeGuide


@dataclass(frozen=True)
class PasteFit:
    display_box: tuple[int, int, int, int]
    source_size: tuple[int, int]
    crop_box: tuple[int, int, int, int]


def render_planning_card(model: PlanningModel, output_path: str | Path, size: tuple[int, int] = (1800, 1200)) -> Path:
    destination = Path(output_path)
    canvas = Image.new("RGB", size, (250, 249, 246))
    draw = ImageDraw.Draw(canvas)
    fonts = _fonts()
    margin = 36

    draw.text((margin, 24), model.title, fill=(36, 36, 34), font=fonts["title"])
    draw.text((margin, 68), "Amigurumi planning output", fill=(93, 98, 91), font=fonts["body"])

    panels = {
        "turnaround": (36, 112, 852, 492),
        "shapes": (888, 112, 876, 492),
        "proportions": (36, 632, 520, 506),
        "construction": (588, 632, 560, 506),
        "assembly": (1180, 632, 584, 506),
    }
    _panel(draw, panels["turnaround"], "1 Complete Single-Object References", fonts)
    _panel(draw, panels["shapes"], "2 Complete Object Shape Breakdown", fonts)
    _panel(draw, panels["proportions"], "3 Proportion Map", fonts)
    _panel(draw, panels["construction"], "4 Crochet Construction Plan", fonts)
    _panel(draw, panels["assembly"], "5 Assembly Diagram", fonts)

    _draw_turnaround(canvas, draw, panels["turnaround"], model.views, fonts)
    _draw_shape_breakdown(canvas, draw, panels["shapes"], model.views, model.shape_guides, fonts)
    _draw_proportions(draw, panels["proportions"], model, fonts)
    _draw_construction(draw, panels["construction"], model, fonts)
    _draw_assembly(canvas, draw, panels["assembly"], model.views, fonts)

    if model.warnings:
        warning = " | ".join(model.warnings[:2])
        draw.text((36, 1166), warning, fill=(126, 87, 22), font=fonts["small"])
    elif model.compromises:
        compromise = "Compromises: " + "; ".join(item.feature for item in model.compromises[:3])
        draw.text((36, 1166), compromise, fill=(126, 87, 22), font=fonts["small"])

    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, quality=94)
    return destination


def _draw_turnaround(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    views: tuple[PlanningView, ...],
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    x, y, w, h = box
    order = ("front", "side", "back", "top")
    slot_w = (w - 64) // 4
    draw.text(
        (x + 18, y + 48),
        "Target is one complete object; each view is labeled Uploaded, Extracted, or Inferred.",
        fill=(93, 98, 91),
        font=fonts["small"],
    )
    for index, kind in enumerate(order):
        slot_x = x + 18 + index * slot_w
        slot_y = y + 88
        view = next((item for item in views if item.kind == kind), None)
        _slot(draw, (slot_x, slot_y, slot_w - 16, h - 122))
        if view:
            _paste_fit(canvas, view.cleaned_path, (slot_x + 8, slot_y + 12, slot_w - 32, h - 184))
            label = f"{kind.title()} - {_view_source_label(view)}"
        else:
            label = kind.title() + " missing"
        draw.text((slot_x + 10, y + h - 46), label, fill=(54, 58, 54), font=fonts["small"])


def _draw_shape_breakdown(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    views: tuple[PlanningView, ...],
    guides: tuple[ShapeGuide, ...],
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    x, y, w, h = box
    front = next((item for item in views if item.kind == "front"), views[0])
    image_box = (x + 26, y + 68, 360, h - 110)
    pasted = _paste_fit_info(canvas, front.cleaned_path, image_box)
    if pasted:
        px, py, pw, ph = pasted.display_box
        crop_left, crop_top, crop_right, crop_bottom = pasted.crop_box
        crop_w = max(1, crop_right - crop_left)
        crop_h = max(1, crop_bottom - crop_top)
        for guide in guides[:7]:
            gx, gy, gw, gh = guide.bbox
            clipped_left = max(gx, crop_left)
            clipped_top = max(gy, crop_top)
            clipped_right = min(gx + gw, crop_right)
            clipped_bottom = min(gy + gh, crop_bottom)
            if clipped_right <= clipped_left or clipped_bottom <= clipped_top:
                continue
            sx = px + (clipped_left - crop_left) / crop_w * pw
            sy = py + (clipped_top - crop_top) / crop_h * ph
            sw = (clipped_right - clipped_left) / crop_w * pw
            sh = (clipped_bottom - clipped_top) / crop_h * ph
            color = guide.color
            draw.ellipse((sx, sy, sx + sw, sy + sh), outline=color, width=3)
    list_x = x + 430
    for index, guide in enumerate(guides[:8]):
        yy = y + 78 + index * 42
        draw.rounded_rectangle((list_x, yy, x + w - 28, yy + 30), radius=6, fill=(244, 242, 236), outline=(222, 218, 207))
        draw.text((list_x + 10, yy + 7), f"{guide.name}: {guide.primitive}", fill=(43, 45, 43), font=fonts["small"])


def _draw_proportions(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    model: PlanningModel,
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    x, y, w, h = box
    cx = x + w // 2
    draw.line((cx, y + 76, cx, y + h - 54), fill=(143, 153, 139), width=3)
    for index, prop in enumerate(model.proportions):
        yy = y + 92 + index * 54
        draw.ellipse((cx - 6, yy - 6, cx + 6, yy + 6), fill=(87, 124, 96))
        draw.text((x + 28, yy - 12), prop.label, fill=(48, 52, 49), font=fonts["body"])
        draw.text((cx + 22, yy - 12), prop.value, fill=(48, 52, 49), font=fonts["body"])


def _draw_construction(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    model: PlanningModel,
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    x, y, w, _h = box
    headers = ("Piece", "Qty", "Primitive", "Round hint")
    col = (x + 24, x + 204, x + 270, x + 386)
    yy = y + 70
    for text, xx in zip(headers, col):
        draw.text((xx, yy), text, fill=(82, 87, 80), font=fonts["small_bold"])
    for index, piece in enumerate(model.construction[:10]):
        row_y = y + 104 + index * 36
        fill = (247, 246, 242) if index % 2 == 0 else (239, 237, 230)
        draw.rectangle((x + 18, row_y - 6, x + w - 18, row_y + 26), fill=fill)
        values = (piece.name, str(piece.quantity), piece.primitive, piece.round_hint)
        for text, xx in zip(values, col):
            draw.text((xx, row_y), text, fill=(43, 45, 43), font=fonts["small"])


def _draw_assembly(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    views: tuple[PlanningView, ...],
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    x, y, w, h = box
    front = next((item for item in views if item.kind == "front"), views[0])
    side = next((item for item in views if item.kind == "side"), front)
    left = _paste_fit(canvas, front.cleaned_path, (x + 38, y + 76, 210, h - 130))
    right = _paste_fit(canvas, side.cleaned_path, (x + 314, y + 76, 210, h - 130))
    for pasted, label in ((left, "front joins"), (right, "side depth")):
        if not pasted:
            continue
        px, py, pw, ph = pasted
        draw.line((px + pw * 0.5, py + ph * 0.22, px + pw * 0.5, py + ph * 0.74), fill=(40, 40, 40), width=2)
        draw.line((px + pw * 0.2, py + ph * 0.52, px + pw * 0.8, py + ph * 0.52), fill=(40, 40, 40), width=2)
        draw.text((px, py + ph + 12), label, fill=(56, 61, 55), font=fonts["small"])


def _panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, fonts: dict[str, ImageFont.ImageFont]) -> None:
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x + w, y + h), radius=8, fill=(255, 255, 252), outline=(220, 216, 206), width=2)
    draw.text((x + 18, y + 18), title, fill=(35, 37, 35), font=fonts["heading"])


def _slot(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x + w, y + h), radius=6, fill=(248, 247, 243), outline=(224, 221, 213))


def _paste_fit(canvas: Image.Image, image_path: Path, box: tuple[int, int, int, int]) -> tuple[int, int, int, int] | None:
    result = _paste_fit_info(canvas, image_path, box)
    return result.display_box if result else None


def _paste_fit_info(canvas: Image.Image, image_path: Path, box: tuple[int, int, int, int]) -> PasteFit | None:
    image = Image.open(image_path).convert("RGBA")
    source_size = image.size
    bbox = _foreground_bbox(image)
    if bbox is not None:
        image = image.crop(bbox)
    else:
        bbox = (0, 0, image.width, image.height)
    x, y, w, h = box
    scale = min(w / image.width, h / image.height)
    resized = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))))
    px = x + (w - resized.width) // 2
    py = y + (h - resized.height) // 2
    canvas.paste(resized, (px, py), resized)
    return PasteFit((px, py, resized.width, resized.height), source_size, bbox)


def _foreground_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Find the subject bbox while treating transparent and near-white gutters as empty."""

    rgba = image.convert("RGBA")
    alpha_bbox = rgba.getchannel("A").point(lambda value: 255 if value > 24 else 0).getbbox()
    if alpha_bbox is None:
        return None

    components = _foreground_components(rgba, alpha_bbox)
    if not components:
        return _padded_bbox(alpha_bbox, rgba.size)

    largest_area = max(component[4] for component in components)
    kept = [
        component
        for component in components
        if component[4] >= max(24, largest_area * 0.06) and not _looks_like_caption_component(component, rgba.size)
    ]
    if not kept:
        kept = [max(components, key=lambda component: component[4])]

    min_x = min(component[0] for component in kept)
    min_y = min(component[1] for component in kept)
    max_x = max(component[2] for component in kept)
    max_y = max(component[3] for component in kept)
    return _padded_bbox((min_x, min_y, max_x, max_y), rgba.size)


def _foreground_components(
    image: Image.Image,
    search_box: tuple[int, int, int, int],
) -> list[tuple[int, int, int, int, int]]:
    pixels = image.load()
    visited: set[tuple[int, int]] = set()
    components: list[tuple[int, int, int, int, int]] = []
    left, top, right, bottom = search_box

    for yy in range(top, bottom):
        for xx in range(left, right):
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
                    if not (left <= nx < right and top <= ny < bottom) or (nx, ny) in visited:
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
    return not (red >= 245 and green >= 245 and blue >= 245)


def _looks_like_caption_component(component: tuple[int, int, int, int, int], size: tuple[int, int]) -> bool:
    left, top, right, bottom, area = component
    width = right - left
    height = bottom - top
    image_width, image_height = size
    in_caption_band = top > image_height * 0.70 or bottom < image_height * 0.18
    small_glyph = area < image_width * image_height * 0.012 and height < image_height * 0.16
    return in_caption_band and small_glyph and width < image_width * 0.45


def _padded_bbox(bbox: tuple[int, int, int, int], size: tuple[int, int]) -> tuple[int, int, int, int]:
    left, top, right, bottom = bbox
    width = right - left
    height = bottom - top
    pad_x = max(2, round(width * 0.04))
    pad_y = max(2, round(height * 0.04))
    return (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(size[0], right + pad_x),
        min(size[1], bottom + pad_y),
    )


def _view_source_label(view: PlanningView) -> str:
    if view.inferred:
        return "Inferred"
    if "extracted" in view.note.lower() or view.source_path.parent.name == "contact_sheet_views":
        return "Extracted"
    return "Uploaded"


def _fonts() -> dict[str, ImageFont.ImageFont]:
    try:
        return {
            "title": ImageFont.truetype("segoeui.ttf", 34),
            "heading": ImageFont.truetype("segoeuib.ttf", 23),
            "body": ImageFont.truetype("segoeui.ttf", 20),
            "small": ImageFont.truetype("segoeui.ttf", 16),
            "small_bold": ImageFont.truetype("segoeuib.ttf", 16),
        }
    except OSError:
        base = ImageFont.load_default()
        return {"title": base, "heading": base, "body": base, "small": base, "small_bold": base}
