"""Planning agents that convert analyzed views into a structured design model."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Protocol

from PIL import Image

from photo_to_pattern.image_regions import CharacterAnalysis

from .background import foreground_bbox
from .models import (
    ConstructionPiece,
    DesignDetail,
    FeatureCompromise,
    DesignPart,
    DesignUncertainty,
    PlanningModel,
    PlanningOptions,
    PlanningView,
    ProportionGuide,
    ShapeGuide,
)


class PlanningModelAgent(Protocol):
    """Boundary for future model-backed image understanding."""

    def build_model(
        self,
        *,
        title: str,
        options: PlanningOptions,
        views: tuple[PlanningView, ...],
        analysis: CharacterAnalysis,
    ) -> PlanningModel:
        """Return structured planning JSON data for rendering and export."""


class HeuristicPlanningAgent:
    """Offline planning model builder used when no image AI backend is configured."""

    def build_model(
        self,
        *,
        title: str,
        options: PlanningOptions,
        views: tuple[PlanningView, ...],
        analysis: CharacterAnalysis,
    ) -> PlanningModel:
        shape_guides = _shape_guides(analysis)
        feature_hints = _feature_hints(title, views, analysis)
        parts = _parts(shape_guides, analysis, options, feature_hints)
        details = _details(shape_guides, options, feature_hints)
        proportions = _proportions(_view(views, "front") or views[0], _view(views, "side"), options)
        construction = _construction(parts, details)
        uncertainties = list(_uncertainties(views, analysis, parts))
        compromises = _compromises(parts, details, views, options, feature_hints)
        warnings = list(analysis.warnings)
        inferred = [view.kind for view in views if view.inferred]
        if inferred:
            warnings.append("AI/local inferred views need human review: " + ", ".join(inferred))
        return PlanningModel(
            title=title,
            options=options,
            views=views,
            shape_guides=shape_guides,
            proportions=proportions,
            construction=construction,
            parts=parts,
            details=details,
            uncertainties=tuple(uncertainties),
            compromises=compromises,
            warnings=tuple(warnings),
        )


def write_planning_model_json(model: PlanningModel, output_path: str | Path) -> Path:
    """Write the structured planning model that drives the card and export."""

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(_jsonable(asdict(model)), indent=2, sort_keys=True), encoding="utf-8")
    return destination


def _shape_guides(analysis: CharacterAnalysis) -> tuple[ShapeGuide, ...]:
    guides: list[ShapeGuide] = []
    for region in sorted(analysis.regions, key=lambda item: item.area, reverse=True):
        if region.kind == "unknown":
            continue
        primitive = {
            "body": "ovoid/cylinder",
            "face_mask": "oval applique",
            "eye": "safety eye/embroidery",
            "leg": "capsule/cylinder",
        }.get(region.kind, "surface detail")
        name = region.kind.replace("_", " ").title()
        guides.append(ShapeGuide(name=name, primitive=primitive, bbox=region.bbox, color=region.average_color or _guide_color(region.kind)))

    if not guides:
        x, y, width, height = analysis.foreground_bbox
        guides.append(ShapeGuide(name="Main Body", primitive="ovoid", bbox=(x, y, width, height), color=(232, 126, 64)))
    return tuple(guides[:9])


def _parts(
    guides: tuple[ShapeGuide, ...],
    analysis: CharacterAnalysis,
    options: PlanningOptions,
    feature_hints: "_FeatureHints",
) -> tuple[DesignPart, ...]:
    _x, _y, width, height = analysis.foreground_bbox
    base = max(1.0, float(max(width, height)))
    parts = [
        DesignPart(
            name="Head",
            primitive="sphere/ovoid",
            relative_size=_scaled((round(width / base, 2), 0.36, round(width / base * 0.85, 2)), options.head_scale),
            color=_first_color(guides, "Body"),
            attachment="Body top / neck line",
            source=_tier_source("structural", "foreground proportions"),
            confidence=0.48,
        ),
        DesignPart(
            name="Body",
            primitive="ovoid/cylinder",
            relative_size=_scaled((round(width / base, 2), round(height / base * 0.62, 2), round(width / base * 0.75, 2)), options.body_scale),
            color=_first_color(guides, "Body"),
            attachment="Primary root piece",
            source=_tier_source("structural", "largest foreground/body region"),
            confidence=0.62 if any(guide.name == "Body" for guide in guides) else 0.42,
        ),
    ]
    if any(guide.name == "Leg" for guide in guides):
        parts.append(
            DesignPart(
                name="Legs",
                primitive="capsule/cylinder",
                relative_size=_scaled((0.18, 0.42, 0.16), options.limb_scale),
                color=_first_color(guides, "Leg"),
                attachment="Lower body, left and right",
                source=_tier_source("structural", "detected leg regions"),
                confidence=0.66,
            )
        )
    else:
        parts.append(
            DesignPart(
                name="Legs",
                primitive="cylinder",
                relative_size=_scaled((0.12, 0.22, 0.10), options.limb_scale),
                color=_first_color(guides, "Body"),
                attachment="Lower body, small supporting nubs, inferred",
                source=_tier_source("structural", "amigurumi default; keep subordinate to silhouette"),
                confidence=0.24,
            )
        )
    tail_color = feature_hints.tail_color or _first_color(guides, "Body")
    tail_source = _tier_source("structural", "detected fox/tail color cue") if feature_hints.has_tail_detail else _tier_source("structural", "amigurumi default")
    tail_confidence = 0.48 if feature_hints.has_tail_detail else 0.22
    parts.extend(
        [
            DesignPart("Arms", "small optional cylinder", _scaled((0.08, 0.18, 0.07), options.limb_scale), _first_color(guides, "Body"), "Body sides, tuck partly under wrap if present", _tier_source("structural", "amigurumi default; optional and visually subordinate"), 0.18),
            DesignPart("Ears", "large fox cones", _scaled((0.22, 0.34, 0.12), options.head_scale), _first_color(guides, "Body"), "Top of head, prominent silhouette feature", _tier_source("structural", "fox head silhouette cue"), 0.46 if feature_hints.has_inner_ears else 0.30),
            DesignPart("Tail", "tapered cone with color tip", _scaled((0.24, 0.50, 0.19), options.limb_scale), tail_color, "Back body, confirm from side/back view", tail_source, tail_confidence),
        ]
    )
    if feature_hints.has_leaf_wrap:
        parts.append(
            DesignPart(
                name="Leaf cloak/body wrap",
                primitive="flat wrap applique",
                relative_size=_scaled((0.72, 0.38, 0.04), options.detail_scale),
                color=feature_hints.leaf_color,
                attachment="Around shoulders and upper body",
                source=_tier_source("flat applique", "detected green wrap/leaf mass"),
                confidence=0.64,
            )
        )
    return tuple(parts)


def _details(
    guides: tuple[ShapeGuide, ...],
    options: PlanningOptions,
    feature_hints: "_FeatureHints",
) -> tuple[DesignDetail, ...]:
    details = []
    scale_note = "" if abs(options.detail_scale - 1.0) < 0.01 else f", scaled {options.detail_scale:.2f}x"
    for guide in guides:
        if guide.name == "Face Mask":
            details.append(DesignDetail("Snout/muzzle", _tier_method("flat applique", "crocheted or felt oval applique with embroidered nose"), _bbox_placement(guide.bbox) + scale_note, guide.color, "detected face-mask region", 0.74))
        elif guide.name == "Eye":
            method = "embroidered closed eyes" if feature_hints.has_closed_eyes else "safety eyes or embroidery"
            tier = "embroidery guide" if feature_hints.has_closed_eyes else "color/overlay cue"
            details.append(DesignDetail("Eyes", _tier_method(tier, method), _bbox_placement(guide.bbox) + scale_note, guide.color, "detected eye/detail region", 0.70))
    if feature_hints.has_inner_ears:
        details.append(DesignDetail("Inner ears", _tier_method("flat applique", "small contrasting inner-ear appliques"), "inside both ear cones" + scale_note, feature_hints.inner_ear_color, "detected pale/pink upper-head accents", 0.58))
    if feature_hints.has_closed_eyes and not any("eye" in detail.name.lower() for detail in details):
        details.append(DesignDetail("Embroidered closed eyes", _tier_method("embroidery guide", "two dark curved backstitch lines"), "upper front of head" + scale_note, (35, 30, 28), "detected dark stitch-like marks", 0.56))
    if feature_hints.has_snout and not any("snout" in detail.name.lower() or "muzzle" in detail.name.lower() for detail in details):
        details.append(DesignDetail("Snout/muzzle", _tier_method("flat applique", "small oval muzzle applique with stitched nose"), "lower front face" + scale_note, feature_hints.snout_color, "detected pale lower-face patch", 0.60))
    if feature_hints.has_leaf_wrap:
        details.append(DesignDetail("Leaf vein embroidery", _tier_method("embroidery guide", "embroider central vein and short branch veins"), "on leaf cloak/body wrap" + scale_note, feature_hints.vein_color, "detected leaf/body wrap cue", 0.62))
    if feature_hints.has_tail_detail:
        details.append(DesignDetail("Tail color/detail", _tier_method("color/overlay cue", "change yarn color at tail tip or add tip applique"), "outer tail end" + scale_note, feature_hints.tail_tip_color, "detected fox/tail color cue", 0.55))
    if not details:
        details.append(DesignDetail("Face", _tier_method("embroidery guide", "embroider after stuffing"), "front head center", None, "inferred default", 0.25))
    return tuple(details)


def _proportions(
    front: PlanningView,
    side: PlanningView | None,
    options: PlanningOptions,
) -> tuple[ProportionGuide, ...]:
    _fx, _fy, fw, fh = foreground_bbox(front.cleaned_path)
    side_width = None
    if side is not None:
        _sx, _sy, sw, _sh = foreground_bbox(side.cleaned_path)
        side_width = sw
    head_unit = max(1, round(fh * 0.36))
    body_ratio = fh / head_unit
    width_ratio = fw / head_unit
    depth_ratio = (side_width / head_unit) if side_width else 0.7
    return (
        ProportionGuide("Head/unit estimate", "1 unit"),
        ProportionGuide("Total height", f"{body_ratio:.1f} units"),
        ProportionGuide("Front width", f"{width_ratio:.1f} units"),
        ProportionGuide("Side depth", f"{depth_ratio:.1f} units"),
        ProportionGuide("Finished height", f"{options.target_height_inches:.1f} in"),
        ProportionGuide("Gauge", f"{options.stitches_per_inch:.1f} sts/in"),
        ProportionGuide("Scales", f"H {options.head_scale:.2f} B {options.body_scale:.2f} L {options.limb_scale:.2f} D {options.detail_scale:.2f}"),
        ProportionGuide("Attachment review", "arms/legs after stuffing"),
    )


def _construction(parts: tuple[DesignPart, ...], details: tuple[DesignDetail, ...]) -> tuple[ConstructionPiece, ...]:
    pieces = []
    for part in parts:
        qty = 2 if part.name in {"Arms", "Legs", "Ears"} else 1
        hint = {
            "Head": "MR 6, inc to widest",
            "Body": "even rounds at belly",
            "Legs": "small tube + foot",
            "Arms": "narrow even rounds",
            "Ears": "decrease to point",
            "Tail": "stuff lightly",
            "Leaf cloak/body wrap": "flat leaf panel, sew around shoulders",
        }.get(part.name, "shape to match reference")
        pieces.append(ConstructionPiece(part.name, qty, part.primitive, hint))
    for detail in details:
        name = detail.name.lower()
        if "closed eye" in name or ("eye" in name and "embroidered" in detail.method.lower()):
            pieces.append(ConstructionPiece("Embroidered closed eyes", 2, "embroidery detail", "backstitch after stuffing"))
        elif "eye" in name:
            pieces.append(ConstructionPiece("Eyes", 2, "detail", "place before closing"))
        elif "snout" in name or "muzzle" in name or "mask" in name or "face" in name:
            pieces.append(ConstructionPiece("Snout/Mask", 1, "oval applique", "flat oval rows"))
        elif "inner ear" in name:
            pieces.append(ConstructionPiece("Inner ears", 2, "small applique", "sew inside ear cones"))
        elif "leaf vein" in name:
            pieces.append(ConstructionPiece("Leaf vein embroidery", 1, "embroidery detail", "straight stitches before final assembly"))
        elif "tail color" in name:
            pieces.append(ConstructionPiece("Tail color/detail", 1, "color-change detail", "cream/light tip at outer end"))
    return tuple(pieces)


def _uncertainties(
    views: tuple[PlanningView, ...],
    analysis: CharacterAnalysis,
    parts: tuple[DesignPart, ...],
) -> tuple[DesignUncertainty, ...]:
    issues: list[DesignUncertainty] = []
    if any(view.inferred for view in views):
        issues.append(
            DesignUncertainty(
                field="views",
                reason="One or more views were inferred rather than uploaded.",
                recommendation="Review generated side/back/top views before trusting attachment placement.",
            )
        )
    if analysis.warnings:
        issues.append(
            DesignUncertainty(
                field="segmentation",
                reason="Image-region analysis reported missing or weak regions.",
                recommendation="Use cleaner orthographic artwork or manually adjust the parts list.",
            )
        )
    low_conf = [part.name for part in parts if part.confidence < 0.35]
    if low_conf:
        issues.append(
            DesignUncertainty(
                field="parts",
                reason="Some parts were inferred from amigurumi defaults: " + ", ".join(low_conf),
                recommendation="Confirm whether these pieces exist and where they attach.",
            )
        )
    return tuple(issues)


def _compromises(
    parts: tuple[DesignPart, ...],
    details: tuple[DesignDetail, ...],
    views: tuple[PlanningView, ...],
    options: PlanningOptions,
    feature_hints: "_FeatureHints",
) -> tuple[FeatureCompromise, ...]:
    compromises: list[FeatureCompromise] = []
    if options.reimagine_as_amigurumi:
        compromises.append(
            FeatureCompromise(
                feature="Source reference",
                original_treatment="Uploaded image",
                crochet_treatment="Amigurumi-friendly simplified reference",
                reason="The image was intentionally simplified before planning to improve crochet feasibility.",
                severity="info",
            )
        )
    if any(view.inferred for view in views):
        compromises.append(
            FeatureCompromise(
                feature="Missing views",
                original_treatment="Not visible in upload",
                crochet_treatment="Inferred turnaround views",
                reason="Hidden side/back/top details cannot be proven from the uploaded references.",
            )
        )
    for part in parts:
        if part.confidence < 0.35:
            compromises.append(
                FeatureCompromise(
                    feature=part.name,
                    original_treatment="Unclear or not directly detected",
                    crochet_treatment=f"Simplified {part.primitive}",
                    reason="The feature is inferred from amigurumi defaults and should be reviewed.",
                )
            )
    for detail in details:
        name = detail.name.lower()
        if any(marker in name for marker in ("eye", "face", "mask", "snout", "muzzle", "inner ear", "leaf vein", "tail color")):
            compromises.append(
                FeatureCompromise(
                    feature=detail.name,
                    original_treatment="Surface visual detail",
                    crochet_treatment=detail.method,
                    reason="Small surface details usually need applique, embroidery, felt, or safety hardware rather than structural crochet.",
                    severity="info",
                )
            )
    if feature_hints.has_leaf_wrap:
        compromises.append(
            FeatureCompromise(
                feature="Leaf cloak/body wrap",
                original_treatment="Thin overlapping leaf shape around the body",
                crochet_treatment="Separate flat wrap applique sewn over the stuffed body",
                reason="A flat leaf layer keeps the body stable while preserving the distinctive cloak silhouette.",
                severity="info",
            )
        )
    return tuple(compromises)


class _FeatureHints:
    def __init__(
        self,
        *,
        has_leaf_wrap: bool = False,
        has_inner_ears: bool = False,
        has_snout: bool = False,
        has_closed_eyes: bool = False,
        has_tail_detail: bool = False,
        leaf_color: tuple[int, int, int] | None = None,
        inner_ear_color: tuple[int, int, int] | None = None,
        snout_color: tuple[int, int, int] | None = None,
        vein_color: tuple[int, int, int] | None = None,
        tail_color: tuple[int, int, int] | None = None,
        tail_tip_color: tuple[int, int, int] | None = None,
    ) -> None:
        self.has_leaf_wrap = has_leaf_wrap
        self.has_inner_ears = has_inner_ears
        self.has_snout = has_snout
        self.has_closed_eyes = has_closed_eyes
        self.has_tail_detail = has_tail_detail
        self.leaf_color = leaf_color
        self.inner_ear_color = inner_ear_color
        self.snout_color = snout_color
        self.vein_color = vein_color
        self.tail_color = tail_color
        self.tail_tip_color = tail_tip_color


def _feature_hints(title: str, views: tuple[PlanningView, ...], analysis: CharacterAnalysis) -> _FeatureHints:
    front = _view(views, "front") or views[0]
    context = " ".join([title, analysis.source, str(front.source_path), str(front.cleaned_path)]).lower()
    filename_hint = "fox" in context or "leaf" in context
    try:
        image = Image.open(front.cleaned_path).convert("RGBA")
    except OSError:
        return _FeatureHints(has_tail_detail=filename_hint)

    fg_x, fg_y, fg_w, fg_h = analysis.foreground_bbox
    total = max(1, fg_w * fg_h)
    samples = _scan_feature_pixels(image, analysis.foreground_bbox)
    green_ratio = len(samples["green"]) / total
    pale_lower_ratio = len(samples["pale_lower_face"]) / total
    pale_upper_ratio = len(samples["pale_upper_head"]) / total
    dark_upper_ratio = len(samples["dark_upper_head"]) / total
    right_orange_ratio = len(samples["right_orange"]) / total
    right_pale_ratio = len(samples["right_pale"]) / total

    has_leaf_wrap = green_ratio > 0.035 or ("leaf" in context and green_ratio > 0.008)
    has_inner_ears = pale_upper_ratio > 0.004 or ("fox" in context and pale_upper_ratio > 0.0015)
    has_snout = pale_lower_ratio > 0.006 or any(region.kind == "face_mask" for region in analysis.regions)
    dark_upper_count = len(samples["dark_upper_head"])
    has_closed_eyes = (dark_upper_ratio > 0.001 or dark_upper_count >= 12) and (filename_hint or not _has_round_eye_regions(analysis))
    has_tail_detail = right_orange_ratio > 0.012 or right_pale_ratio > 0.003 or filename_hint
    body_color = _dominant_region_color(analysis, "body") or (232, 126, 64)

    return _FeatureHints(
        has_leaf_wrap=has_leaf_wrap,
        has_inner_ears=has_inner_ears,
        has_snout=has_snout,
        has_closed_eyes=has_closed_eyes,
        has_tail_detail=has_tail_detail,
        leaf_color=_average_color(samples["green"]) or (88, 132, 96),
        inner_ear_color=_average_color(samples["pale_upper_head"]) or (238, 178, 156),
        snout_color=_average_color(samples["pale_lower_face"]) or (242, 218, 184),
        vein_color=_average_color(samples["dark_green"]) or (67, 92, 55),
        tail_color=body_color,
        tail_tip_color=_average_color(samples["right_pale"]) or (244, 221, 185),
    )


def _scan_feature_pixels(
    image: Image.Image,
    bbox: tuple[int, int, int, int],
) -> dict[str, list[tuple[int, int, int]]]:
    fg_x, fg_y, fg_w, fg_h = bbox
    x1 = min(image.width, fg_x + fg_w)
    y1 = min(image.height, fg_y + fg_h)
    pixels = image.load()
    samples: dict[str, list[tuple[int, int, int]]] = {
        "green": [],
        "dark_green": [],
        "pale_lower_face": [],
        "pale_upper_head": [],
        "dark_upper_head": [],
        "right_orange": [],
        "right_pale": [],
    }
    for y in range(max(0, fg_y), y1):
        y_rel = (y - fg_y) / max(1, fg_h)
        for x in range(max(0, fg_x), x1):
            r, g, b, a = pixels[x, y]
            if a < 32 or _is_near_background(r, g, b):
                continue
            x_rel = (x - fg_x) / max(1, fg_w)
            color = (r, g, b)
            if _is_leaf_green(r, g, b):
                samples["green"].append(color)
            if _is_dark_green(r, g, b):
                samples["dark_green"].append(color)
            if _is_pale_muzzle(r, g, b) and 0.22 <= x_rel <= 0.78 and 0.28 <= y_rel <= 0.62:
                samples["pale_lower_face"].append(color)
            if _is_pale_muzzle(r, g, b) and 0.08 <= y_rel <= 0.36:
                samples["pale_upper_head"].append(color)
            if _is_dark_stitch(r, g, b) and 0.12 <= y_rel <= 0.48:
                samples["dark_upper_head"].append(color)
            if x_rel >= 0.70 and _is_fox_orange(r, g, b):
                samples["right_orange"].append(color)
            if x_rel >= 0.70 and _is_pale_muzzle(r, g, b):
                samples["right_pale"].append(color)
    return samples


def _has_round_eye_regions(analysis: CharacterAnalysis) -> bool:
    for region in analysis.regions:
        if region.kind != "eye":
            continue
        _x, _y, width, height = region.bbox
        if width and height and 0.55 <= width / height <= 1.8 and region.area > 30:
            return True
    return False


def _dominant_region_color(analysis: CharacterAnalysis, kind: str) -> tuple[int, int, int] | None:
    regions = [region for region in analysis.regions if region.kind == kind]
    if not regions:
        return None
    return max(regions, key=lambda region: region.area).average_color


def _average_color(colors: list[tuple[int, int, int]]) -> tuple[int, int, int] | None:
    if not colors:
        return None
    count = len(colors)
    return (
        round(sum(color[0] for color in colors) / count),
        round(sum(color[1] for color in colors) / count),
        round(sum(color[2] for color in colors) / count),
    )


def _is_near_background(r: int, g: int, b: int) -> bool:
    return r > 238 and g > 238 and b > 238 and max(r, g, b) - min(r, g, b) < 16


def _is_leaf_green(r: int, g: int, b: int) -> bool:
    return 45 <= r <= 170 and 75 <= g <= 190 and 25 <= b <= 140 and g >= r - 5 and g >= b + 18


def _is_dark_green(r: int, g: int, b: int) -> bool:
    return 25 <= r <= 105 and 45 <= g <= 130 and b <= 95 and g >= r - 10


def _is_pale_muzzle(r: int, g: int, b: int) -> bool:
    return r >= 190 and g >= 150 and b >= 120 and max(r, g, b) - min(r, g, b) < 85


def _is_dark_stitch(r: int, g: int, b: int) -> bool:
    return (r + g + b) / 3 < 88 and max(r, g, b) - min(r, g, b) < 45


def _is_fox_orange(r: int, g: int, b: int) -> bool:
    return r > 145 and 70 <= g <= 165 and b < 110 and r > g + 30


def _view(views: tuple[PlanningView, ...], kind: str) -> PlanningView | None:
    return next((view for view in views if view.kind == kind), None)


def _guide_color(kind: str) -> tuple[int, int, int]:
    return {
        "body": (232, 126, 64),
        "face_mask": (84, 73, 63),
        "eye": (48, 98, 137),
        "leg": (109, 84, 160),
    }.get(kind, (88, 132, 96))


def _first_color(guides: tuple[ShapeGuide, ...], name: str) -> tuple[int, int, int] | None:
    guide = next((item for item in guides if item.name == name), None)
    return guide.color if guide else None


def _bbox_placement(bbox: tuple[int, int, int, int]) -> str:
    x, y, width, height = bbox
    return f"bbox {width}x{height} at {x},{y}"


def _jsonable(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _scaled(values: tuple[float, float, float], scale: float) -> tuple[float, float, float]:
    return tuple(round(max(0.05, value * scale), 2) for value in values)  # type: ignore[return-value]


def _tier_source(tier: str, source: str) -> str:
    return f"tier:{tier}; {source}"


def _tier_method(tier: str, method: str) -> str:
    return f"tier:{tier}; {method}"
