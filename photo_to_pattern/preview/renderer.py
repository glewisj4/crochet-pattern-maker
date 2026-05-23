"""Render an annotated preview of the app's image understanding."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from photo_to_pattern.image_regions import CharacterAnalysis, ColorRegion


class PreviewUnavailableError(RuntimeError):
    """Raised when a preview cannot be rendered."""


REGION_COLORS = {
    "body": (255, 190, 0),
    "face_mask": (35, 20, 10),
    "eye": (80, 150, 255),
    "leg": (180, 60, 255),
    "unknown": (120, 120, 120),
}


def render_analysis_preview(
    image_path: str | Path,
    analysis: CharacterAnalysis,
    output_path: str | Path,
    max_dimension: int = 1400,
) -> Path:
    """Draw foreground and semantic-region boxes over the source image."""

    source = Path(image_path)
    destination = Path(output_path)
    if not source.exists():
        raise PreviewUnavailableError(f"Source image does not exist: {source}")

    image = Image.open(source).convert("RGBA")
    scale = min(1.0, max_dimension / max(image.width, image.height))
    if scale < 1.0:
        canvas = image.resize((round(image.width * scale), round(image.height * scale)))
    else:
        canvas = image.copy()

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default()

    label_slots: list[tuple[int, int, int, int]] = []
    _draw_box(
        draw,
        _scale_bbox(analysis.foreground_bbox, scale),
        "foreground",
        (255, 255, 255),
        font,
        width=4,
        label_slots=label_slots,
    )

    for region in sorted(analysis.regions, key=lambda item: item.area, reverse=True):
        if region.kind == "unknown":
            continue
        color = REGION_COLORS[region.kind]
        label = _label(region)
        _draw_box(draw, _scale_bbox(region.bbox, scale), label, color, font, width=3, label_slots=label_slots)
        _draw_shape_fit(draw, region, scale, color)

    composed = Image.alpha_composite(canvas, overlay).convert("RGB")
    destination.parent.mkdir(parents=True, exist_ok=True)
    composed.save(destination)
    return destination


def _draw_box(
    draw: ImageDraw.ImageDraw,
    bbox: tuple[int, int, int, int],
    label: str,
    color: tuple[int, int, int],
    font: ImageFont.ImageFont,
    width: int,
    label_slots: list[tuple[int, int, int, int]],
) -> None:
    x, y, box_width, box_height = bbox
    x2 = x + box_width
    y2 = y + box_height
    rgba = (*color, 230)
    fill = (*color, 42)
    draw.rectangle((x, y, x2, y2), outline=rgba, width=width, fill=fill)

    text_bbox = draw.textbbox((x, y), label, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    label_x, label_y = _label_position(x, y, x2, y2, text_w + 8, text_h + 6, label_slots)
    label_box = (label_x, label_y, label_x + text_w + 8, label_y + text_h + 6)
    label_slots.append(label_box)
    draw.rectangle(label_box, fill=(0, 0, 0, 185))
    draw.text((label_x + 4, label_y + 3), label, fill=(255, 255, 255, 255), font=font)


def _label(region: ColorRegion) -> str:
    _x, _y, width, height = region.bbox
    short = {
        "body": "body",
        "face_mask": "mask",
        "eye": "eye",
        "leg": "leg",
        "unknown": "unknown",
    }[region.kind]
    return f"{short} {width}x{height}"


def _scale_bbox(bbox: tuple[int, int, int, int], scale: float) -> tuple[int, int, int, int]:
    x, y, width, height = bbox
    return round(x * scale), round(y * scale), round(width * scale), round(height * scale)


def _draw_shape_fit(
    draw: ImageDraw.ImageDraw,
    region: ColorRegion,
    scale: float,
    color: tuple[int, int, int],
) -> None:
    if region.kind == "leg" and len(region.contour) > 2:
        points = [(round(x * scale), round(y * scale)) for x, y in region.contour]
        draw.line(points + [points[0]], fill=(255, 255, 255, 230), width=4)
        draw.line(points + [points[0]], fill=(*color, 255), width=2)
    if region.kind == "leg" and len(region.centerline) > 1:
        points = [(round(x * scale), round(y * scale)) for x, y in region.centerline]
        draw.line(points, fill=(0, 0, 0, 255), width=8, joint="curve")
        draw.line(points, fill=(0, 255, 180, 255), width=4, joint="curve")
        for x, y in points:
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(0, 255, 180, 255))
    elif region.kind == "leg" and region.major_axis:
        start, end = region.major_axis
        draw.line(
            (
                round(start[0] * scale),
                round(start[1] * scale),
                round(end[0] * scale),
                round(end[1] * scale),
            ),
            fill=(0, 0, 0, 255),
            width=7,
        )
        draw.line(
            (
                round(start[0] * scale),
                round(start[1] * scale),
                round(end[0] * scale),
                round(end[1] * scale),
            ),
            fill=(0, 255, 180, 255),
            width=4,
        )


def _label_position(
    x: int,
    y: int,
    x2: int,
    y2: int,
    label_width: int,
    label_height: int,
    occupied: list[tuple[int, int, int, int]],
) -> tuple[int, int]:
    candidates = [
        (x, max(0, y - label_height - 4)),
        (x, y + 4),
        (x2 - label_width, y + 4),
        (x, y2 - label_height - 4),
        (x2 - label_width, y2 + 4),
    ]
    for candidate in candidates:
        box = (candidate[0], candidate[1], candidate[0] + label_width, candidate[1] + label_height)
        if not any(_intersects(box, other) for other in occupied):
            return candidate
    return candidates[-1]


def _intersects(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])
