"""Virtual build preview from the structured crochet plan."""

from __future__ import annotations

from pathlib import Path
import math

from PIL import Image, ImageDraw, ImageFont

from .models import ConstructionPiece, DesignDetail, DesignPart, PlanningModel


def render_virtual_build(
    model: PlanningModel,
    output_path: str | Path,
    size: tuple[int, int] = (1200, 900),
) -> Path:
    """Render an approximate stuffed-toy build from the final structured plan.

    This is not a physics solver. It is a deterministic reconstruction preview
    that helps catch obvious part, proportion, color, and attachment mistakes.
    """

    destination = Path(output_path)
    canvas = Image.new("RGB", size, (249, 248, 244))
    draw = ImageDraw.Draw(canvas)
    fonts = _fonts()

    draw.text((34, 26), "Virtual Build Accuracy Check", fill=(35, 37, 35), font=fonts["title"])
    draw.text((34, 68), model.title, fill=(94, 98, 92), font=fonts["body"])

    _draw_reference_notes(draw, model, fonts)
    _draw_front_build(draw, model, (120, 132, 430, 575), fonts)
    _draw_side_build(draw, model, (650, 152, 320, 575), fonts)
    _draw_checklist(draw, model, (34, 760, 1132, 108), fonts)

    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, quality=94)
    return destination


def _draw_front_build(
    draw: ImageDraw.ImageDraw,
    model: PlanningModel,
    box: tuple[int, int, int, int],
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    x, y, w, h = box
    body = _part(model.parts, "Body")
    head = _part(model.parts, "Head")
    arms = _part(model.parts, "Arms")
    legs = _part(model.parts, "Legs")
    ears = _part(model.parts, "Ears")
    tail = _part(model.parts, "Tail")
    body_color = _color(body, (226, 130, 70))
    head_color = _color(head, body_color)
    head_scale = _clamp((head.relative_size[1] / 0.36) if head else 1.0, 0.55, 1.55)
    body_scale = _clamp((body.relative_size[1] / 0.62) if body else 1.0, 0.55, 1.55)
    limb_scale = _clamp((legs.relative_size[1] / 0.32) if legs else 1.0, 0.55, 1.55)
    arm_scale = _visual_part_scale(arms, limb_scale)
    leg_scale = _visual_part_scale(legs, limb_scale)

    body_box = _fit_box(_scaled_box((x + w * 0.29, y + h * 0.35, x + w * 0.71, y + h * 0.78), body_scale, body_scale), box, 8)
    head_box = _fit_box(_scaled_box((x + w * 0.23, y + h * 0.08, x + w * 0.77, y + h * 0.44), head_scale, head_scale), box, 8)

    if tail:
        _draw_tail(draw, model, tail, (x + w * 0.66, y + h * 0.48, x + w * 0.91, y + h * 0.72), body_color, side=False)

    limb_color = _color(arms, body_color)
    leg_color = _color(legs, body_color)
    _crochet_capsule(draw, _fit_box(_scaled_box((x + w * 0.18, y + h * 0.47, x + w * 0.30, y + h * 0.63), arm_scale, arm_scale), box, 8), limb_color)
    _crochet_capsule(draw, _fit_box(_scaled_box((x + w * 0.70, y + h * 0.47, x + w * 0.82, y + h * 0.63), arm_scale, arm_scale), box, 8), limb_color)
    _crochet_capsule(draw, _fit_box(_scaled_box((x + w * 0.36, y + h * 0.73, x + w * 0.47, y + h * 0.91), leg_scale, leg_scale), box, 8), leg_color)
    _crochet_capsule(draw, _fit_box(_scaled_box((x + w * 0.53, y + h * 0.73, x + w * 0.64, y + h * 0.91), leg_scale, leg_scale), box, 8), leg_color)

    _crochet_ellipse(draw, body_box, body_color)
    _crochet_ellipse(draw, head_box, head_color)
    if _has_feature(model, ("leaf", "cloak", "wrap")):
        _draw_leaf_cloak(draw, model, body_box, head_box, front=True)

    if ears:
        ear_color = _color(_part(model.parts, "Ears"), head_color)
        left_ear = ((x + w * 0.31, y + h * 0.13), (x + w * 0.39, y + h * 0.01), (x + w * 0.47, y + h * 0.16))
        right_ear = ((x + w * 0.53, y + h * 0.16), (x + w * 0.61, y + h * 0.01), (x + w * 0.69, y + h * 0.13))
        _crochet_polygon(draw, left_ear, ear_color)
        _crochet_polygon(draw, right_ear, ear_color)
        inner_color = _detail_color(model.details, ("inner ear", "ear"), _blend(ear_color, (255, 210, 205), 0.62))
        _crochet_polygon(draw, _inset_triangle(left_ear, 0.34), inner_color, outline_width=2)
        _crochet_polygon(draw, _inset_triangle(right_ear, 0.34), inner_color, outline_width=2)

    _draw_details(draw, model.details, head_box)
    draw.text((x + w * 0.35, y + h + 26), "front virtual build", fill=(71, 76, 70), font=fonts["small"])


def _draw_side_build(
    draw: ImageDraw.ImageDraw,
    model: PlanningModel,
    box: tuple[int, int, int, int],
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    x, y, w, h = box
    body = _part(model.parts, "Body")
    head = _part(model.parts, "Head")
    tail = _part(model.parts, "Tail")
    legs = _part(model.parts, "Legs")
    body_color = _color(body, (226, 130, 70))
    head_color = _color(head, body_color)

    body_box = (x + w * 0.28, y + h * 0.35, x + w * 0.76, y + h * 0.78)
    head_box = (x + w * 0.16, y + h * 0.09, x + w * 0.74, y + h * 0.43)
    if tail:
        _draw_tail(draw, model, tail, (x + w * 0.66, y + h * 0.43, x + w * 0.98, y + h * 0.70), body_color, side=True)
    _crochet_ellipse(draw, body_box, body_color)
    _crochet_ellipse(draw, head_box, head_color)
    if _has_feature(model, ("leaf", "cloak", "wrap")):
        _draw_leaf_cloak(draw, model, body_box, head_box, front=False)
    _crochet_capsule(draw, (x + w * 0.42, y + h * 0.72, x + w * 0.56, y + h * 0.98), _color(legs, body_color))
    draw.text((x + w * 0.28, y + h + 26), "side/depth check", fill=(71, 76, 70), font=fonts["small"])


def _draw_reference_notes(
    draw: ImageDraw.ImageDraw,
    model: PlanningModel,
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    uploaded = len([view for view in model.views if not view.inferred])
    inferred = len([view for view in model.views if view.inferred])
    text = f"{uploaded} uploaded view(s), {inferred} inferred view(s). Low-confidence parts are shown but must be reviewed."
    draw.rounded_rectangle((700, 30, 1166, 92), radius=8, fill=(255, 255, 252), outline=(221, 218, 210))
    draw.text((718, 52), text, fill=(67, 71, 65), font=fonts["small"])


def _draw_checklist(
    draw: ImageDraw.ImageDraw,
    model: PlanningModel,
    box: tuple[int, int, int, int],
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x + w, y + h), radius=8, fill=(255, 255, 252), outline=(221, 218, 210))
    checks = [
        f"Parts: {len(model.parts)} planned",
        f"Details: {len(model.details)} planned",
        f"Review items: {len(model.uncertainties)}",
    ]
    low_conf = [part.name for part in model.parts if part.confidence < 0.35]
    if low_conf:
        checks.append("Low confidence: " + ", ".join(low_conf[:4]))
    for index, check in enumerate(checks[:4]):
        xx = x + 22 + index * 270
        draw.ellipse((xx, y + 39, xx + 18, y + 57), fill=(87, 124, 96))
        draw.text((xx + 28, y + 37), check, fill=(45, 48, 44), font=fonts["small"])


def _draw_details(draw: ImageDraw.ImageDraw, details: tuple[DesignDetail, ...], head_box: tuple[float, float, float, float]) -> None:
    x0, y0, x1, y1 = head_box
    eye_y = y0 + (y1 - y0) * 0.45
    left_x = x0 + (x1 - x0) * 0.38
    right_x = x0 + (x1 - x0) * 0.62
    eye_color = _detail_color(details, ("eye",), (25, 25, 25))
    closed_eyes = any(_contains(detail, ("closed", "embroider", "embroidered", "sleep", "sleepy")) and _contains(detail, ("eye",)) for detail in details)
    if closed_eyes:
        draw.arc((left_x - 19, eye_y - 7, left_x + 19, eye_y + 18), 15, 165, fill=eye_color, width=4)
        draw.arc((right_x - 19, eye_y - 7, right_x + 19, eye_y + 18), 15, 165, fill=eye_color, width=4)
    else:
        draw.ellipse((left_x - 8, eye_y - 8, left_x + 8, eye_y + 8), fill=eye_color)
        draw.ellipse((right_x - 8, eye_y - 8, right_x + 8, eye_y + 8), fill=eye_color)

    if any(_contains(detail, ("mask", "face", "muzzle", "snout")) for detail in details):
        muzzle_color = _detail_color(details, ("muzzle", "snout", "mask", "face"), (245, 220, 180))
        mask_box = (x0 + (x1 - x0) * 0.34, y0 + (y1 - y0) * 0.51, x0 + (x1 - x0) * 0.66, y0 + (y1 - y0) * 0.74)
        _crochet_ellipse(draw, mask_box, muzzle_color)
        nose_color = _detail_color(details, ("nose",), (45, 38, 34))
        nx = (mask_box[0] + mask_box[2]) / 2
        ny = mask_box[1] + (mask_box[3] - mask_box[1]) * 0.38
        draw.ellipse((nx - 7, ny - 5, nx + 7, ny + 6), fill=nose_color)
    draw.arc((left_x, eye_y + 30, right_x, eye_y + 67), 10, 170, fill=(45, 38, 34), width=3)


def _crochet_ellipse(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], color: tuple[int, int, int]) -> None:
    shadow = tuple(max(0, channel - 35) for channel in color)
    draw.ellipse(box, fill=color, outline=shadow, width=3)
    x0, y0, x1, y1 = box
    for i in range(1, 6):
        yy = y0 + (y1 - y0) * i / 7
        inset = abs(i - 3.5) / 3.5 * (x1 - x0) * 0.15
        draw.arc((x0 + inset, yy - 9, x1 - inset, yy + 9), 0, 180, fill=shadow, width=1)
    _stitch_marks(draw, box, shadow)


def _crochet_capsule(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], color: tuple[int, int, int]) -> None:
    shadow = tuple(max(0, channel - 35) for channel in color)
    draw.rounded_rectangle(box, radius=round((box[2] - box[0]) / 2), fill=color, outline=shadow, width=3)
    _stitch_marks(draw, box, shadow, count=12)


def _crochet_polygon(
    draw: ImageDraw.ImageDraw,
    points: tuple[tuple[float, float], ...],
    color: tuple[int, int, int],
    outline_width: int = 3,
) -> None:
    shadow = tuple(max(0, channel - 35) for channel in color)
    draw.polygon(points, fill=color, outline=shadow)
    draw.line(points + (points[0],), fill=shadow, width=outline_width)


def _stitch_marks(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    color: tuple[int, int, int],
    count: int = 18,
) -> None:
    x0, y0, x1, y1 = box
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    rx = (x1 - x0) / 2 * 0.82
    ry = (y1 - y0) / 2 * 0.82
    for index in range(count):
        angle = 2 * math.pi * index / count
        x = cx + math.cos(angle) * rx
        y = cy + math.sin(angle) * ry
        draw.arc((x - 5, y - 3, x + 5, y + 7), 200, 340, fill=color, width=1)


def _part(parts: tuple[DesignPart, ...], name: str) -> DesignPart | None:
    needle = name.lower()
    return next((part for part in parts if needle in part.name.lower()), None)


def _color(part: DesignPart | None, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    return part.color if part and part.color else fallback


def _scaled_box(
    box: tuple[float, float, float, float],
    x_scale: float,
    y_scale: float,
) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = box
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    half_w = (x1 - x0) * x_scale / 2
    half_h = (y1 - y0) * y_scale / 2
    return (cx - half_w, cy - half_h, cx + half_w, cy + half_h)


def _fit_box(
    box: tuple[float, float, float, float],
    bounds: tuple[int, int, int, int],
    margin: float,
) -> tuple[float, float, float, float]:
    x, y, w, h = bounds
    x0, y0, x1, y1 = box
    dx = max(x + margin - x0, 0) + min(x + w - margin - x1, 0)
    dy = max(y + margin - y0, 0) + min(y + h - margin - y1, 0)
    return (x0 + dx, y0 + dy, x1 + dx, y1 + dy)


def _draw_leaf_cloak(
    draw: ImageDraw.ImageDraw,
    model: PlanningModel,
    body_box: tuple[float, float, float, float],
    head_box: tuple[float, float, float, float],
    front: bool,
) -> None:
    cloak_color = _detail_color(model.details, ("leaf", "cloak", "wrap"), (72, 132, 77))
    x0, y0, x1, y1 = body_box
    hx0, hy0, hx1, hy1 = head_box
    top_y = hy0 + (hy1 - hy0) * 0.72
    if front:
        points = (
            (hx0 + (hx1 - hx0) * 0.16, top_y),
            (hx1 - (hx1 - hx0) * 0.16, top_y),
            (x1 + (x1 - x0) * 0.28, y1 - (y1 - y0) * 0.04),
            ((x0 + x1) / 2, y1 + (y1 - y0) * 0.14),
            (x0 - (x1 - x0) * 0.28, y1 - (y1 - y0) * 0.04),
        )
    else:
        points = (
            (hx0 + (hx1 - hx0) * 0.22, top_y),
            (hx1 - (hx1 - hx0) * 0.05, top_y + 5),
            (x1 + (x1 - x0) * 0.33, y1 - (y1 - y0) * 0.08),
            (x0 + (x1 - x0) * 0.18, y1 + (y1 - y0) * 0.08),
        )
    _crochet_polygon(draw, points, cloak_color)
    vein = _detail_color(model.details, ("vein",), tuple(max(0, channel - 45) for channel in cloak_color))
    center_x = sum(point[0] for point in points) / len(points)
    bottom_y = max(point[1] for point in points) - 8
    draw.line((center_x, top_y + 5, center_x, bottom_y), fill=vein, width=3)
    for offset, side_sign in ((0.35, -1), (0.55, 1), (0.72, -1)):
        yy = top_y + (bottom_y - top_y) * offset
        draw.line((center_x, yy, center_x + side_sign * (x1 - x0) * 0.26, yy - (y1 - y0) * 0.12), fill=vein, width=2)


def _draw_tail(
    draw: ImageDraw.ImageDraw,
    model: PlanningModel,
    tail: DesignPart,
    box: tuple[float, float, float, float],
    fallback: tuple[int, int, int],
    side: bool,
) -> None:
    color = _color(tail, fallback)
    primitive = (tail.primitive + " " + tail.name).lower()
    if "curl" in primitive or "spiral" in primitive:
        shadow = tuple(max(0, channel - 35) for channel in color)
        draw.arc(box, 205 if side else 250, 565 if side else 540, fill=shadow, width=16)
        draw.arc(box, 205 if side else 250, 565 if side else 540, fill=color, width=10)
    elif "sphere" in primitive or "pom" in primitive or "ball" in primitive:
        _crochet_ellipse(draw, box, color)
    elif "capsule" in primitive or "cylinder" in primitive:
        _crochet_capsule(draw, box, color)
    else:
        x0, y0, x1, y1 = box
        if side:
            points = ((x0, y0 + (y1 - y0) * 0.46), (x1, y0), (x0 + (x1 - x0) * 0.64, y1))
        else:
            points = ((x0, y0 + (y1 - y0) * 0.35), (x1, y0 + (y1 - y0) * 0.18), (x0 + (x1 - x0) * 0.62, y1))
        _crochet_polygon(draw, points, color)
        tip_color = _detail_color(model.details, ("tail", "tip", "color"), None)
        if tip_color:
            tip = _tail_tip(points, 0.36)
            _crochet_polygon(draw, tip, tip_color, outline_width=2)


def _detail_color(
    details: tuple[DesignDetail, ...],
    keywords: tuple[str, ...],
    fallback: tuple[int, int, int] | None,
) -> tuple[int, int, int] | None:
    for detail in details:
        if detail.color and _contains(detail, keywords):
            return detail.color
    return fallback


def _has_feature(model: PlanningModel, keywords: tuple[str, ...]) -> bool:
    parts = " ".join(part.name + " " + part.primitive + " " + part.attachment for part in model.parts)
    details = " ".join(detail.name + " " + detail.method + " " + detail.placement for detail in model.details)
    construction = " ".join(piece.name + " " + piece.primitive + " " + piece.round_hint for piece in model.construction)
    haystack = f"{parts} {details} {construction}".lower()
    return any(keyword in haystack for keyword in keywords)


def _contains(item: DesignDetail | ConstructionPiece, keywords: tuple[str, ...]) -> bool:
    if isinstance(item, DesignDetail):
        haystack = f"{item.name} {item.method} {item.placement} {item.source}".lower()
    else:
        haystack = f"{item.name} {item.primitive} {item.round_hint}".lower()
    return any(keyword in haystack for keyword in keywords)


def _inset_triangle(points: tuple[tuple[float, float], ...], amount: float) -> tuple[tuple[float, float], ...]:
    cx = sum(point[0] for point in points) / len(points)
    cy = sum(point[1] for point in points) / len(points)
    return tuple((cx + (px - cx) * (1 - amount), cy + (py - cy) * (1 - amount)) for px, py in points)


def _blend(
    first: tuple[int, int, int],
    second: tuple[int, int, int],
    amount: float,
) -> tuple[int, int, int]:
    return tuple(round(a * (1 - amount) + b * amount) for a, b in zip(first, second))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _visual_part_scale(part: DesignPart | None, fallback: float) -> float:
    if part is None:
        return _clamp(fallback, 0.55, 1.0)
    scale = min(fallback, (part.relative_size[1] / 0.32) if part.relative_size[1] else fallback)
    if part.confidence < 0.35 or "subordinate" in part.source.lower() or "optional" in part.primitive.lower():
        scale *= 0.72
    return _clamp(scale, 0.38, 1.0)


def _tail_tip(points: tuple[tuple[float, float], ...], amount: float) -> tuple[tuple[float, float], ...]:
    tip = max(points, key=lambda point: point[0])
    return tuple((tip[0] + (px - tip[0]) * amount, tip[1] + (py - tip[1]) * amount) for px, py in points)


def _fonts() -> dict[str, ImageFont.ImageFont]:
    try:
        return {
            "title": ImageFont.truetype("segoeuib.ttf", 30),
            "body": ImageFont.truetype("segoeui.ttf", 19),
            "small": ImageFont.truetype("segoeui.ttf", 16),
        }
    except OSError:
        base = ImageFont.load_default()
        return {"title": base, "body": base, "small": base}
