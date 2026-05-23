"""Design proof rendering from final crochet instructions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import math

from PIL import Image, ImageDraw, ImageFont

from photo_to_pattern.geometric_math import PatternMap, RoundSpec
from photo_to_pattern.planning.models import DesignPart, PlanningModel
from photo_to_pattern.verification.graph_validator import GraphValidationReport, validate_stitch_graph
from photo_to_pattern.verification.stitch_graph import to_stitch_graph


@dataclass(frozen=True)
class PieceMetric:
    primitive_id: str
    rounds: int
    max_stitches: int
    height_units: float
    width_units: float


def render_design_proof(
    pattern_map: PatternMap,
    planning_model: PlanningModel | None,
    output_path: str | Path,
    title: str,
    size: tuple[int, int] = (1400, 1000),
) -> Path:
    """Render a proof image of what the final instructions currently build."""

    destination = Path(output_path)
    canvas = Image.new("RGB", size, (248, 247, 243))
    draw = ImageDraw.Draw(canvas)
    fonts = _fonts()
    metrics = _metrics(pattern_map)

    draw.text((34, 26), "Design Proof From Final Instructions", fill=(35, 37, 35), font=fonts["title"])
    draw.text((34, 68), title, fill=(92, 96, 90), font=fonts["body"])
    draw.text(
        (34, 98),
        _proof_note(planning_model),
        fill=(105, 91, 63),
        font=fonts["small"],
    )

    graph = to_stitch_graph(pattern_map, title)
    graph_report = validate_stitch_graph(graph)
    _draw_graph_projection_panels(draw, graph, planning_model, graph_report, (42, 150, 820, 700), fonts)
    _draw_instruction_inventory(draw, metrics, planning_model, (910, 150, 440, 700), fonts)

    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, quality=94)
    return destination


def _draw_graph_projection_panels(
    draw: ImageDraw.ImageDraw,
    graph: dict[str, object],
    model: PlanningModel | None,
    graph_report: GraphValidationReport,
    box: tuple[int, int, int, int],
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x + w, y + h), radius=8, fill=(255, 255, 252), outline=(221, 218, 210))
    draw.text((x + 20, y + 18), "Graph-Driven Instruction Proof", fill=(38, 42, 38), font=fonts["heading"])
    _draw_graph_validation_summary(draw, graph_report, (x + 20, y + h - 50, w - 40, 30), fonts)
    panels = [
        ("front projection", "front", (x + 22, y + 62, 360, 285)),
        ("side projection", "side", (x + 432, y + 62, 360, 285)),
        ("top projection", "top", (x + 226, y + 372, 360, 250)),
    ]
    parts = graph.get("parts", [])
    for label, projection, panel in panels:
        _draw_projection_panel(draw, parts, model, label, projection, panel, fonts)


def _draw_graph_validation_summary(
    draw: ImageDraw.ImageDraw,
    report: GraphValidationReport,
    box: tuple[int, int, int, int],
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    x, y, w, h = box
    fill = (232, 241, 232) if report.passed else (248, 229, 224)
    outline = (114, 151, 112) if report.passed else (178, 98, 82)
    draw.rounded_rectangle((x, y, x + w, y + h), radius=6, fill=fill, outline=outline)
    status = "passes graph checks" if report.passed else f"{report.error_count} graph error(s)"
    suffix = f", {report.warning_count} warning(s)" if report.warning_count else ""
    draw.text(
        (x + 12, y + 6),
        f"Graph-derived shape, heuristic assembly: {status}{suffix}",
        fill=(50, 63, 48),
        font=fonts["small"],
    )


def _draw_projection_panel(
    draw: ImageDraw.ImageDraw,
    parts: object,
    model: PlanningModel | None,
    label: str,
    projection: str,
    box: tuple[int, int, int, int],
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x + w, y + h), radius=6, fill=(248, 247, 243), outline=(224, 221, 213))
    draw.text((x + 12, y + 10), label, fill=(70, 74, 68), font=fonts["small"])
    if not isinstance(parts, list):
        return

    for part in parts:
        if not isinstance(part, dict):
            continue
        part_id = str(part.get("id", "part"))
        nodes = part.get("nodes", [])
        edges = part.get("edges", [])
        if not isinstance(nodes, list) or not nodes:
            continue
        positions = _projected_points(nodes, projection)
        if not positions:
            continue
        tx, ty, scale = _part_transform(part_id, projection, (x + 18, y + 36, w - 36, h - 54))
        color = _part_color_for_id(model, part_id, (214, 136, 74))
        shadow = tuple(max(0, channel - 42) for channel in color)
        node_lookup = {str(node.get("id")): _screen_point(point, tx, ty, scale) for node, point in zip(nodes, positions) if isinstance(node, dict)}

        if isinstance(edges, list):
            for edge in edges:
                if not isinstance(edge, dict) or edge.get("type") not in {"round_neighbor", "worked_into", "increase_split", "decrease_merge"}:
                    continue
                start = node_lookup.get(str(edge.get("from")))
                end = node_lookup.get(str(edge.get("to")))
                if start and end:
                    draw.line((start[0], start[1], end[0], end[1]), fill=(*shadow,)[0:3], width=1)
        for point in node_lookup.values():
            draw.ellipse((point[0] - 1.8, point[1] - 1.8, point[0] + 1.8, point[1] + 1.8), fill=color, outline=shadow)


def _projected_points(nodes: list[object], projection: str) -> list[tuple[float, float]]:
    points = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        position = node.get("position")
        if not isinstance(position, dict):
            continue
        px = float(position.get("x", 0.0))
        py = float(position.get("y", 0.0))
        pz = float(position.get("z", 0.0))
        if projection == "side":
            points.append((py, pz))
        elif projection == "top":
            points.append((px, py))
        else:
            points.append((px, pz))
    return points


def _screen_point(point: tuple[float, float], tx: float, ty: float, scale: float) -> tuple[float, float]:
    return tx + point[0] * scale, ty - point[1] * scale


def _part_transform(
    part_id: str,
    projection: str,
    box: tuple[int, int, int, int],
) -> tuple[float, float, float]:
    x, y, w, h = box
    base = part_id.split("_")[0]
    positions = {
        "head": (0.50, 0.25, 54),
        "body": (0.50, 0.54, 60),
        "arms": (0.26 if part_id.endswith("_1") else 0.74, 0.55, 30),
        "legs": (0.42 if part_id.endswith("_1") else 0.58, 0.80, 28),
        "ears": (0.38 if part_id.endswith("_1") else 0.62, 0.08, 24),
        "tail": (0.78 if projection != "side" else 0.62, 0.58, 34),
    }
    rx, ry, scale = positions.get(base, (0.50, 0.50, 32))
    if projection == "top":
        ry = min(0.82, ry + 0.08)
    return x + w * rx, y + h * ry, scale


def _part_color_for_id(
    model: PlanningModel | None,
    part_id: str,
    fallback: tuple[int, int, int],
) -> tuple[int, int, int]:
    if model is None:
        return fallback
    base = part_id.split("_")[0]
    for part in model.parts:
        normalized = "".join(char.lower() if char.isalnum() else "_" for char in part.name).strip("_")
        if normalized == base:
            return part.color if part.color else fallback
    return fallback


def _draw_finished_front(
    draw: ImageDraw.ImageDraw,
    metrics: dict[str, PieceMetric],
    model: PlanningModel | None,
    box: tuple[int, int, int, int],
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    x, y, w, h = box
    body_metric = _metric(metrics, "body")
    leg_metrics = [metric for key, metric in metrics.items() if key.startswith("leg")]
    body_color = _part_color(model, "Body", (226, 130, 70))
    head_color = _part_color(model, "Head", body_color)
    limb_color = _part_color(model, "Legs", body_color)

    body_scale = _metric_scale(body_metric, 1.0)
    body_box = _scaled_box((x + w * 0.32, y + h * 0.36, x + w * 0.68, y + h * 0.76), body_scale, body_scale)
    _solid_piece(draw, body_box, body_color, bool(body_metric), "body")

    head_metric = _metric(metrics, "head")
    head_box = _scaled_box((x + w * 0.25, y + h * 0.10, x + w * 0.75, y + h * 0.42), _metric_scale(head_metric, 1.0), _metric_scale(head_metric, 1.0))
    _solid_piece(draw, head_box, head_color, bool(head_metric), "head")

    arms_metric = _metric(metrics, "arm")
    _solid_capsule(draw, (x + w * 0.15, y + h * 0.40, x + w * 0.34, y + h * 0.64), body_color, bool(arms_metric), "arm")
    _solid_capsule(draw, (x + w * 0.66, y + h * 0.40, x + w * 0.85, y + h * 0.64), body_color, bool(arms_metric), "arm")

    leg_drawn = bool(leg_metrics)
    _solid_capsule(draw, (x + w * 0.34, y + h * 0.72, x + w * 0.48, y + h * 0.98), limb_color, leg_drawn, "leg")
    _solid_capsule(draw, (x + w * 0.52, y + h * 0.72, x + w * 0.66, y + h * 0.98), limb_color, leg_drawn, "leg")

    if model and any(part.name == "Ears" for part in model.parts):
        _planned_triangle(draw, ((x + w * 0.31, y + h * 0.13), (x + w * 0.39, y), (x + w * 0.47, y + h * 0.16)), _part_color(model, "Ears", head_color), bool(_metric(metrics, "ear")))
        _planned_triangle(draw, ((x + w * 0.53, y + h * 0.16), (x + w * 0.61, y), (x + w * 0.69, y + h * 0.13)), _part_color(model, "Ears", head_color), bool(_metric(metrics, "ear")))

    _face(draw, head_box, solid=bool(head_metric))
    draw.text((x + w * 0.21, y + h + 36), "assembled proof from current generated rounds", fill=(70, 74, 68), font=fonts["small"])


def _draw_instruction_inventory(
    draw: ImageDraw.ImageDraw,
    metrics: dict[str, PieceMetric],
    model: PlanningModel | None,
    box: tuple[int, int, int, int],
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x + w, y + h), radius=8, fill=(255, 255, 252), outline=(221, 218, 210))
    draw.text((x + 22, y + 20), "Instruction Coverage", fill=(38, 42, 38), font=fonts["heading"])
    expected = [part.name for part in model.parts] if model else []
    if not expected:
        expected = ["Body", "Legs"]

    yy = y + 70
    for name in expected[:12]:
        generated = _has_generated_piece(metrics, name)
        fill = (87, 124, 96) if generated else (174, 123, 64)
        label = "generated rounds" if generated else "planned only"
        draw.ellipse((x + 24, yy + 2, x + 42, yy + 20), fill=fill)
        draw.text((x + 54, yy), f"{name}: {label}", fill=(48, 51, 47), font=fonts["body"])
        yy += 38

    yy += 18
    draw.text((x + 22, yy), "Generated primitive metrics", fill=(38, 42, 38), font=fonts["heading"])
    yy += 40
    for metric in list(metrics.values())[:9]:
        draw.text(
            (x + 24, yy),
            f"{metric.primitive_id}: {metric.rounds} rounds, max {metric.max_stitches} sts",
            fill=(62, 66, 60),
            font=fonts["small"],
        )
        yy += 28


def _metrics(pattern_map: PatternMap) -> dict[str, PieceMetric]:
    grouped: dict[str, list[RoundSpec]] = defaultdict(list)
    for round_spec in pattern_map.rounds:
        grouped[round_spec.primitive_id].append(round_spec)
    metrics = {}
    for primitive_id, rounds in grouped.items():
        max_stitches = max(round_spec.stitch_count for round_spec in rounds)
        metrics[primitive_id] = PieceMetric(
            primitive_id=primitive_id,
            rounds=len(rounds),
            max_stitches=max_stitches,
            height_units=len(rounds) * 0.8,
            width_units=max_stitches / 6,
        )
    return metrics


def _proof_note(model: PlanningModel | None) -> str:
    base = "Solid pieces come from generated crochet rounds. Dashed pieces are planned but not yet fully generated as rounds."
    if model and model.compromises:
        return base + " Compromises: " + ", ".join(item.feature for item in model.compromises[:3])
    return base


def _solid_piece(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    color: tuple[int, int, int],
    solid: bool,
    label: str,
) -> None:
    if solid:
        _crochet_ellipse(draw, box, color)
    else:
        _dashed_ellipse(draw, box, color)
    draw.text((box[0], box[3] + 4), label, fill=(70, 74, 68))


def _solid_capsule(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    color: tuple[int, int, int],
    solid: bool,
    label: str,
) -> None:
    shadow = tuple(max(0, channel - 35) for channel in color)
    if solid:
        draw.rounded_rectangle(box, radius=round((box[2] - box[0]) / 2), fill=color, outline=shadow, width=3)
        _stitch_marks(draw, box, shadow, count=12)
    else:
        _dashed_rect(draw, box, shadow)


def _crochet_ellipse(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], color: tuple[int, int, int]) -> None:
    shadow = tuple(max(0, channel - 35) for channel in color)
    draw.ellipse(box, fill=color, outline=shadow, width=3)
    _stitch_marks(draw, box, shadow)


def _dashed_ellipse(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], color: tuple[int, int, int]) -> None:
    shadow = tuple(max(0, channel - 35) for channel in color)
    for angle in range(0, 360, 18):
        draw.arc(box, angle, angle + 10, fill=shadow, width=3)


def _dashed_rect(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], color: tuple[int, int, int]) -> None:
    x0, y0, x1, y1 = box
    points = [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]
    for x_start, y_start, x_end, y_end in points:
        _dashed_line(draw, (x_start, y_start), (x_end, y_end), color)


def _dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    color: tuple[int, int, int],
    dash: int = 10,
) -> None:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = max(1, (dx * dx + dy * dy) ** 0.5)
    steps = int(length // dash)
    for index in range(0, steps, 2):
        a = index / steps
        b = min(1.0, (index + 1) / steps)
        draw.line((start[0] + dx * a, start[1] + dy * a, start[0] + dx * b, start[1] + dy * b), fill=color, width=3)


def _planned_triangle(draw: ImageDraw.ImageDraw, points: tuple[tuple[float, float], ...], color: tuple[int, int, int], solid: bool) -> None:
    shadow = tuple(max(0, channel - 35) for channel in color)
    if solid:
        draw.polygon(points, fill=color, outline=shadow)
    else:
        for start, end in zip(points, points[1:] + points[:1]):
            _dashed_line(draw, start, end, shadow)


def _face(draw: ImageDraw.ImageDraw, head_box: tuple[float, float, float, float], solid: bool) -> None:
    x0, y0, x1, y1 = head_box
    eye_y = y0 + (y1 - y0) * 0.45
    for eye_x in (x0 + (x1 - x0) * 0.38, x0 + (x1 - x0) * 0.62):
        if solid:
            draw.ellipse((eye_x - 7, eye_y - 7, eye_x + 7, eye_y + 7), fill=(25, 25, 25))
        else:
            draw.ellipse((eye_x - 7, eye_y - 7, eye_x + 7, eye_y + 7), outline=(25, 25, 25), width=2)


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


def _metric(metrics: dict[str, PieceMetric], key: str) -> PieceMetric | None:
    return next((metric for name, metric in metrics.items() if key in name.lower()), None)


def _metric_scale(metric: PieceMetric | None, fallback: float) -> float:
    if metric is None:
        return fallback
    return max(0.65, min(1.45, metric.width_units / 6))


def _part_color(model: PlanningModel | None, part_name: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    if model is None:
        return fallback
    part = next((item for item in model.parts if item.name == part_name), None)
    return part.color if part and part.color else fallback


def _has_generated_piece(metrics: dict[str, PieceMetric], name: str) -> bool:
    key = name.lower().rstrip("s")
    if key == "body":
        return _metric(metrics, "body") is not None
    if key in {"leg", "arm", "ear", "tail", "head"}:
        return _metric(metrics, key) is not None
    if "snout" in key or "mask" in key or "eye" in key:
        return False
    return any(key in primitive_id.lower() for primitive_id in metrics)


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


def _fonts() -> dict[str, ImageFont.ImageFont]:
    try:
        return {
            "title": ImageFont.truetype("segoeuib.ttf", 30),
            "heading": ImageFont.truetype("segoeuib.ttf", 20),
            "body": ImageFont.truetype("segoeui.ttf", 18),
            "small": ImageFont.truetype("segoeui.ttf", 15),
        }
    except OSError:
        base = ImageFont.load_default()
        return {"title": base, "heading": base, "body": base, "small": base}
