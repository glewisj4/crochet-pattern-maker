"""Proportion-Scaling-Agent and Aesthetic Genre Modifiers."""

from __future__ import annotations

import logging
import math
from dataclasses import replace
from typing import Any

from photo_to_pattern.image_regions import CharacterAnalysis
from photo_to_pattern.planning.deconstructor import DeconstructedModel
from photo_to_pattern.planning.models import (
    ConstructionPiece,
    DesignDetail,
    DesignPart,
    DesignUncertainty,
    FeatureCompromise,
    PlanningModel,
    PlanningOptions,
    PlanningView,
    ProportionGuide,
    ShapeGuide,
    snap_part_to_parent,
)

logger = logging.getLogger(__name__)


class ProportionScalingAgent:
    """Agent that applies aesthetic scaling multipliers and joint snap constraints."""

    def scale(
        self,
        deconstructed: DeconstructedModel,
        options: PlanningOptions,
        analysis: CharacterAnalysis,
    ) -> PlanningModel:
        # Avoid circular imports at module load time
        from photo_to_pattern.planning.agent import (
            _parse_relative_size,
            _shape_guides,
            _proportions,
            _construction,
            _compromises,
            _feature_hints,
            _FeatureHints,
            _view,
        )

        parts_list: list[DesignPart] = []
        details_list: list[DesignDetail] = []

        style = (options.aesthetic_style or "classic").lower().strip()

        # Determine scaling factors based on aesthetic style
        if "chibi" in style:
            head_mult = 1.45
            body_mult = 1.0
            limb_mult = 0.65
            eye_spacing_mult = 1.3
            kawaii_mode = False
        elif "kawaii" in style:
            head_mult = 1.2
            body_mult = 0.75
            limb_mult = 0.7
            eye_spacing_mult = 1.4
            kawaii_mode = True
        else:  # classic or default
            head_mult = 1.0
            body_mult = 1.0
            limb_mult = 1.0
            eye_spacing_mult = 1.0
            kawaii_mode = False

        # 1. Parse and apply style scale factors to parts
        for item in deconstructed.component_tree:
            name = item["name"]
            primitive = item["primitive"]
            item_type = item.get("type", "part")
            category = item.get("category", "Primary Body" if item_type == "part" else "Accents")

            # Find matching color
            color_info = next((c for c in deconstructed.detected_colors if c["name"] == name), {})
            color_rgb = color_info.get("color")
            color_hex = color_info.get("hex", "#e87e40")

            # Find matching confidence
            conf_info = next((c for c in deconstructed.confidences if c["name"] == name), {})
            confidence = conf_info.get("confidence", 0.85)

            # Find matching spatial anchor
            anchor_info = next((sa for sa in deconstructed.spatial_anchors if sa["name"] == name), {})
            position = anchor_info.get("position", (0.0, 0.0, 0.0))
            rotation = anchor_info.get("rotation_degrees", 0.0)

            name_lower = name.lower()

            if item_type == "part":
                raw_size = item.get("relative_size", "0.5,0.5,0.5")
                size_tuple = _parse_relative_size(raw_size)

                # Determine multiplier for the specific part type
                part_mult = 1.0
                if "head" in name_lower:
                    part_mult = head_mult
                elif "body" in name_lower or "torso" in name_lower:
                    part_mult = body_mult
                elif any(x in name_lower for x in ("arm", "leg", "ear", "tail")):
                    part_mult = limb_mult

                scaled_size = tuple(round(max(0.05, s * part_mult), 2) for s in size_tuple)

                # For Kawaii mode, limbs are placed tightly at torso baseline
                if kawaii_mode and any(x in name_lower for x in ("arm", "leg", "tail")):
                    px, py, pz = position
                    # Shift vertically towards the bottom of the body/baseline
                    py = py + 0.15
                    position = (px, py, pz)

                dp = DesignPart(
                    name=name,
                    primitive=primitive,
                    relative_size=scaled_size,  # type: ignore[arg-type]
                    color=color_rgb,
                    color_hex=color_hex,
                    attachment=item.get("attachment", "unknown"),
                    source=item.get("source", ""),
                    confidence=confidence,
                    pose_position=position,
                    rotation_degrees=rotation,
                    category=category,
                )
                parts_list.append(dp)
            else:
                # Apply eye spacing modifier to details
                if "eye" in name_lower and eye_spacing_mult != 1.0:
                    px, py, pz = position
                    # Adjust X coordinate relative to center (typically 0.0 or 0.5) to widen eyes
                    px = px * eye_spacing_mult
                    position = (px, py, pz)

                dd = DesignDetail(
                    name=name,
                    method=primitive,
                    placement=item.get("placement", "unknown"),
                    color=color_rgb,
                    color_hex=color_hex,
                    source=item.get("source", ""),
                    confidence=confidence,
                    pose_position=position,
                    rotation_degrees=rotation,
                    category=category,
                )
                details_list.append(dd)

        # 2. Joint Snapping math (sticky parent boundary snaps)
        # Find Body/Torso and Head to serve as parents
        body_part = next((p for p in parts_list if "body" in p.name.lower() or "torso" in p.name.lower()), None)
        head_part = next((p for p in parts_list if "head" in p.name.lower()), None)

        snapped_parts: list[DesignPart] = []
        for p in parts_list:
            name_lower = p.name.lower()
            if any(x in name_lower for x in ("arm", "leg", "tail", "cloak", "wrap")) and body_part:
                # Snap limb to Torso/Body parent
                parent_w, parent_h = body_part.relative_size[0], body_part.relative_size[1]
                snapped_pos = snap_part_to_parent(p.pose_position, body_part.pose_position, parent_w, parent_h)
                p = replace(p, pose_position=snapped_pos)
            elif "ear" in name_lower and head_part:
                # Snap ears to Head parent
                parent_w, parent_h = head_part.relative_size[0], head_part.relative_size[1]
                snapped_pos = snap_part_to_parent(p.pose_position, head_part.pose_position, parent_w, parent_h)
                p = replace(p, pose_position=snapped_pos)
            snapped_parts.append(p)

        snapped_details: list[DesignDetail] = []
        for d in details_list:
            name_lower = d.name.lower()
            if any(x in name_lower for x in ("eye", "snout", "muzzle", "face")) and head_part:
                # Snap facial details to Head parent
                parent_w, parent_h = head_part.relative_size[0], head_part.relative_size[1]
                snapped_pos = snap_part_to_parent(d.pose_position, head_part.pose_position, parent_w, parent_h)
                d = replace(d, pose_position=snapped_pos)
            elif "vein" in name_lower and body_part:
                # Snap leaf vein to Body parent
                parent_w, parent_h = body_part.relative_size[0], body_part.relative_size[1]
                snapped_pos = snap_part_to_parent(d.pose_position, body_part.pose_position, parent_w, parent_h)
                d = replace(d, pose_position=snapped_pos)
            snapped_details.append(d)

        parts = tuple(snapped_parts)
        details = tuple(snapped_details)

        # 3. Reconstruct other attributes required by PlanningModel
        shape_guides = _shape_guides(analysis)
        views = deconstructed.views
        proportions = _proportions(_view(views, "front") or views[0], _view(views, "side"), options)
        construction = _construction(parts, details)

        gemini_success = any(
            "Turnaround features extracted via Gemini 1.5 Flash VLM." in w
            for w in deconstructed.warnings
        )
        if gemini_success:
            has_leaf = any("leaf" in p.name.lower() for p in parts) or any(
                "leaf" in d.name.lower() for d in details
            )
            gemini_hints = _FeatureHints(has_leaf_wrap=has_leaf)
            compromises = _compromises(parts, details, views, options, gemini_hints)
        else:
            feature_hints = _feature_hints(deconstructed.title, views, analysis)
            compromises = _compromises(parts, details, views, options, feature_hints)

        # Reconstruct DesignUncertainty objects
        uncertainties_list = []
        for u in deconstructed.uncertainties:
            uncertainties_list.append(
                DesignUncertainty(
                    field=u["field"],
                    reason=u["reason"],
                    recommendation=u["recommendation"],
                    severity=u.get("severity", "review"),
                )
            )
        uncertainties = tuple(uncertainties_list)

        return PlanningModel(
            title=deconstructed.title,
            options=options,
            views=views,
            shape_guides=shape_guides,
            proportions=proportions,
            construction=construction,
            parts=parts,
            details=details,
            uncertainties=uncertainties,
            compromises=compromises,
            warnings=deconstructed.warnings,
        )
