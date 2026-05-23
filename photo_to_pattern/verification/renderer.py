"""Render stitch-profile simulations from generated rounds."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from photo_to_pattern.geometric_math import PatternMap, RoundSpec


def render_stitch_simulation(
    pattern_map: PatternMap,
    output_path: str | Path,
    title: str,
    size: tuple[int, int] = (1400, 900),
) -> Path:
    """Render a section-profile preview from the final generated crochet rounds."""

    destination = Path(output_path)
    canvas = Image.new("RGB", size, (248, 247, 243))
    draw = ImageDraw.Draw(canvas)
    fonts = _fonts()
    draw.text((34, 26), "Final Crochet Plan Simulation", fill=(35, 37, 35), font=fonts["title"])
    draw.text((34, 68), title, fill=(92, 96, 90), font=fonts["body"])

    grouped: dict[str, list[RoundSpec]] = defaultdict(list)
    for round_spec in pattern_map.rounds:
        grouped[round_spec.primitive_id].append(round_spec)

    items = list(sorted(grouped.items()))[:6]
    if not items:
        draw.text((34, 130), "No rounds to simulate.", fill=(120, 72, 42), font=fonts["body"])
    else:
        cols = 3
        panel_w = 420
        panel_h = 340
        for index, (primitive_id, rounds) in enumerate(items):
            col = index % cols
            row = index // cols
            x = 34 + col * 450
            y = 120 + row * 370
            _draw_piece(draw, primitive_id, sorted(rounds, key=lambda item: item.round_number), (x, y, panel_w, panel_h), fonts)

    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, quality=94)
    return destination


def _draw_piece(
    draw: ImageDraw.ImageDraw,
    primitive_id: str,
    rounds: list[RoundSpec],
    box: tuple[int, int, int, int],
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x + w, y + h), radius=8, fill=(255, 255, 252), outline=(221, 218, 210))
    draw.text((x + 16, y + 14), primitive_id.replace("_", " ").title(), fill=(38, 42, 38), font=fonts["heading"])
    if not rounds:
        return

    max_stitches = max(round_spec.stitch_count for round_spec in rounds)
    graph_x = x + 46
    graph_y = y + 62
    graph_w = w - 92
    graph_h = h - 112
    center_x = graph_x + graph_w / 2
    round_h = graph_h / max(1, len(rounds))
    scale = graph_w / max(1, max_stitches)

    profile_left = []
    profile_right = []
    for index, round_spec in enumerate(rounds):
        yy = graph_y + index * round_h + round_h / 2
        half = round_spec.stitch_count * scale / 2
        profile_left.append((center_x - half, yy))
        profile_right.append((center_x + half, yy))
        color = _action_color(round_spec.action)
        draw.line((center_x - half, yy, center_x + half, yy), fill=color, width=3)
        draw.text((x + 16, yy - 8), f"R{round_spec.round_number}", fill=(88, 91, 84), font=fonts["small"])
        draw.text((x + w - 64, yy - 8), str(round_spec.stitch_count), fill=(88, 91, 84), font=fonts["small"])

    outline = profile_left + list(reversed(profile_right))
    if len(outline) > 2:
        draw.line(outline + [outline[0]], fill=(55, 58, 54), width=2)

    legend_y = y + h - 34
    draw.text((x + 16, legend_y), f"{len(rounds)} rounds, max {max_stitches} sts", fill=(73, 77, 71), font=fonts["small"])


def _action_color(action: str) -> tuple[int, int, int]:
    return {
        "mr": (76, 122, 92),
        "inc": (48, 112, 160),
        "even": (126, 126, 116),
        "dec": (176, 92, 72),
    }.get(action, (126, 126, 116))


def _fonts() -> dict[str, ImageFont.ImageFont]:
    try:
        return {
            "title": ImageFont.truetype("segoeuib.ttf", 30),
            "heading": ImageFont.truetype("segoeuib.ttf", 18),
            "body": ImageFont.truetype("segoeui.ttf", 18),
            "small": ImageFont.truetype("segoeui.ttf", 14),
        }
    except OSError:
        base = ImageFont.load_default()
        return {"title": base, "heading": base, "body": base, "small": base}

