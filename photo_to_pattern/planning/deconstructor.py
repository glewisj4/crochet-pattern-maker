"""Vision-Deconstruction-Agent and Data Contracts."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from photo_to_pattern.image_regions import CharacterAnalysis
from photo_to_pattern.planning.gemini_adapter import GeminiVisionError
from photo_to_pattern.planning.models import PlanningOptions, PlanningView

logger = logging.getLogger(__name__)

MIN_PLANNING_CONFIDENCE = 0.75
SEMANTIC_CATEGORIES = {
    "Primary Body",
    "Accents",
    "Appendages",
    "Overlaid Garments",
    "Facial Embroidery",
    "Insets",
}


@dataclass(frozen=True)
class DeconstructedModel:
    title: str
    views: tuple[PlanningView, ...]
    component_tree: tuple[dict[str, str], ...]  # e.g., [{"name": "Head", "primitive": "sphere"}, ...]
    spatial_anchors: tuple[dict[str, object], ...]  # e.g., [{"name": "neck", "position": (x, y, z)}, ...]
    detected_colors: tuple[dict[str, object], ...]  # e.g., [{"name": "Body", "color": (R,G,B), "hex": "#hex"}, ...]
    confidences: tuple[dict[str, float], ...]
    uncertainties: tuple[dict[str, str], ...]
    warnings: tuple[str, ...]


class VisionDeconstructionAgent:
    """Agent that performs vision analysis to deconstruct a character into parts and details."""

    def deconstruct(
        self,
        image_paths: list[Path],
        options: PlanningOptions,
        views: tuple[PlanningView, ...],
        analysis: CharacterAnalysis,
        title: str | None = None,
    ) -> DeconstructedModel:
        """Deconstructs the character into parts and details using required Gemini VLM."""
        # Avoid circular imports at module load time by importing inside the method
        from photo_to_pattern.planning.agent import (
            GeminiAdapter,
            _parse_relative_size,
            _parse_hex_color,
            _scaled,
            _shape_guides,
            _feature_hints,
            _parts,
            _details,
            _uncertainties,
            DesignPart,
            DesignDetail,
        )
        front_path = image_paths[0] if image_paths else None
        if not front_path:
            front_view = next((v for v in views if v.kind == "front"), None) or (views[0] if views else None)
            if front_view:
                front_path = front_view.cleaned_path

        resolved_title = title or analysis.source or "character"
        parts_list: list[DesignPart] = []
        details_list: list[DesignDetail] = []
        warnings_list: list[str] = list(analysis.warnings)

        if not front_path:
            raise GeminiVisionError("A front/source image is required for Gemini semantic deconstruction.")

        adapter = GeminiAdapter()
        res = adapter.analyze_character(front_path, options.gemini_api_key)
        parsed_parts = []
        for p in res["parts"]:
            name = _required_string(p, "name")
            primitive = _required_string(p, "primitive")
            category = _semantic_category(p.get("category"))

            raw_size = p.get("relative_size")
            size_tuple = _parse_relative_size(raw_size)
            name_lower = name.lower()
            scale = 1.0
            if "head" in name_lower:
                scale = options.head_scale
            elif "body" in name_lower or "torso" in name_lower:
                scale = options.body_scale
            elif any(x in name_lower for x in ("arm", "leg", "ear", "tail")):
                scale = options.limb_scale
            else:
                scale = options.detail_scale
            scaled_size = _scaled(size_tuple, scale)

            color_hex = _required_string(p, "color_hex")
            if not color_hex.startswith("#"):
                color_hex = "#" + color_hex
            color_rgb = _parse_hex_color(color_hex)
            if color_rgb is None:
                raise GeminiVisionError(f"Invalid part color_hex for {name!r}: {color_hex!r}.")

            pose_pos = p.get("pose_position", (0.0, 0.0, 0.0))
            if isinstance(pose_pos, list):
                pose_pos = tuple(pose_pos)
            rot_deg = float(p.get("rotation_degrees", 0.0))
            confidence = float(p.get("confidence", 0.0))

            parsed_parts.append(
                DesignPart(
                    name=name,
                    primitive=primitive,
                    relative_size=scaled_size,
                    color=color_rgb,
                    color_hex=color_hex,
                    attachment=_required_string(p, "attachment"),
                    source=f"tier:{_tier_for_category(category)}; Gemini VLM segment; category:{category}",
                    confidence=confidence,
                    pose_position=pose_pos,
                    rotation_degrees=rot_deg,
                    category=category,
                )
            )

        parsed_details = []
        for d in res["details"]:
            name = _required_string(d, "name")
            category = _semantic_category(d.get("category"))
            method = _required_string(d, "method")
            if not method.startswith("tier:"):
                method = f"tier:{_tier_for_category(category)}; {method}"

            color_hex = _required_string(d, "color_hex")
            if not color_hex.startswith("#"):
                color_hex = "#" + color_hex
            color_rgb = _parse_hex_color(color_hex)
            if color_rgb is None:
                raise GeminiVisionError(f"Invalid detail color_hex for {name!r}: {color_hex!r}.")

            pose_pos = d.get("pose_position", (0.0, 0.0, 0.0))
            if isinstance(pose_pos, list):
                pose_pos = tuple(pose_pos)
            rot_deg = float(d.get("rotation_degrees", 0.0))
            confidence = float(d.get("confidence", 0.0))

            parsed_details.append(
                DesignDetail(
                    name=name,
                    method=method,
                    placement=_required_string(d, "placement"),
                    color=color_rgb,
                    color_hex=color_hex,
                    source=f"tier:{_tier_for_category(category)}; Gemini VLM segment; category:{category}",
                    confidence=confidence,
                    pose_position=pose_pos,
                    rotation_degrees=rot_deg,
                    category=category,
                )
            )

        _enforce_confidence_floor(parsed_parts, parsed_details)
        parts_list = parsed_parts
        details_list = parsed_details
        warnings_list.append("Turnaround features extracted via Gemini 1.5 Flash VLM.")

        # Build tuples from parsed components
        component_tree_list = []
        spatial_anchors_list = []
        detected_colors_list = []
        confidences_list = []

        for p in parts_list:
            size_str = f"{p.relative_size[0]},{p.relative_size[1]},{p.relative_size[2]}"
            component_tree_list.append({
                "name": p.name,
                "primitive": p.primitive,
                "type": "part",
                "relative_size": size_str,
                "attachment": p.attachment,
                "source": p.source,
                "category": p.category,
            })
            spatial_anchors_list.append({
                "name": p.name,
                "position": p.pose_position,
                "rotation_degrees": p.rotation_degrees,
            })
            detected_colors_list.append({
                "name": p.name,
                "color": p.color,
                "hex": p.color_hex,
            })
            confidences_list.append({
                "name": p.name,
                "confidence": p.confidence,
            })

        for d in details_list:
            component_tree_list.append({
                "name": d.name,
                "primitive": d.method,
                "type": "detail",
                "placement": d.placement,
                "source": d.source,
                "category": d.category,
            })
            spatial_anchors_list.append({
                "name": d.name,
                "position": d.pose_position,
                "rotation_degrees": d.rotation_degrees,
            })
            detected_colors_list.append({
                "name": d.name,
                "color": d.color,
                "hex": d.color_hex,
            })
            confidences_list.append({
                "name": d.name,
                "confidence": d.confidence,
            })

        uncs = _uncertainties(views, analysis, tuple(parts_list))
        uncertainties_list = []
        for u in uncs:
            uncertainties_list.append({
                "field": u.field,
                "reason": u.reason,
                "recommendation": u.recommendation,
                "severity": u.severity,
            })

        inferred = [view.kind for view in views if view.inferred]
        if inferred:
            warnings_list.append("AI/local inferred views need human review: " + ", ".join(inferred))

        return DeconstructedModel(
            title=resolved_title,
            views=views,
            component_tree=tuple(component_tree_list),
            spatial_anchors=tuple(spatial_anchors_list),
            detected_colors=tuple(detected_colors_list),
            confidences=tuple(confidences_list),
            uncertainties=tuple(uncertainties_list),
            warnings=tuple(warnings_list),
        )


def _semantic_category(value: object) -> str:
    if isinstance(value, str) and value in SEMANTIC_CATEGORIES:
        return value
    raise GeminiVisionError(f"Invalid or missing semantic category: {value!r}.")


def _required_string(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise GeminiVisionError(f"Gemini semantic item is missing required string field {key!r}.")


def _tier_for_category(category: str) -> str:
    return {
        "Primary Body": "structural",
        "Appendages": "structural",
        "Overlaid Garments": "flat applique",
        "Insets": "flat applique",
        "Facial Embroidery": "embroidery guide",
        "Accents": "color/overlay cue",
    }.get(category, "color/overlay cue")


def _enforce_confidence_floor(parts: list["DesignPart"], details: list["DesignDetail"]) -> None:
    confidences = [item.confidence for item in [*parts, *details]]
    if not confidences:
        raise GeminiVisionError("Gemini semantic deconstruction returned no confidence-bearing items.")
    minimum = min(confidences)
    if minimum < MIN_PLANNING_CONFIDENCE:
        raise GeminiVisionError(
            f"Planning confidence {minimum:.2f} is below required {MIN_PLANNING_CONFIDENCE:.2f}; aborting."
        )
