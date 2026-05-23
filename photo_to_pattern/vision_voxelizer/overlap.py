"""Overlap and hidden-limb inference for silhouette-only inputs."""

from .config import VisionVoxelizerConfig
from .models import LimbOcclusion, Silhouette, Vec2


def infer_occlusions(
    silhouette: Silhouette,
    config: VisionVoxelizerConfig,
) -> tuple[LimbOcclusion, ...]:
    """Flag likely overlap zones for later user confirmation.

    A single 2D silhouette cannot prove depth ordering. This module records
    ambiguity instead of collapsing it into overconfident geometry.
    """

    if not config.overlap_support:
        return ()

    x, y, width, height = silhouette.bbox
    if width <= 0 or height <= 0:
        return ()

    aspect = width / height
    occlusions: list[LimbOcclusion] = []

    if aspect > 0.72:
        occlusions.append(
            LimbOcclusion(
                kind="overlap",
                location=Vec2(x + width / 2, y + height * 0.45),
                estimated_depth_order=None,
                confidence=min(0.8, 0.35 + aspect * 0.35),
                note="Wide silhouette may contain arms or legs crossing the torso.",
            )
        )

    if silhouette.confidence < config.confidence_floor_for_autofit:
        occlusions.append(
            LimbOcclusion(
                kind="ambiguous_attachment",
                location=Vec2(x + width / 2, y + height / 2),
                estimated_depth_order=None,
                confidence=1.0 - silhouette.confidence,
                note="Low segmentation confidence requires manual attachment review.",
            )
        )

    return tuple(occlusions)

