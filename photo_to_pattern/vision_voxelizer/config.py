"""Configuration for the Vision & Voxelizer module."""

from dataclasses import dataclass


@dataclass(frozen=True)
class VisionVoxelizerConfig:
    """Runtime knobs for conservative primitive extraction.

    The MVP supports overlapping limbs by marking possible occlusions and
    requiring later UI/manual confirmation when confidence is low.
    """

    overlap_support: bool = True
    assume_bilateral_symmetry: bool = True
    min_component_area_ratio: float = 0.01
    limb_width_ratio: float = 0.28
    depth_inference_ratio: float = 0.72
    confidence_floor_for_autofit: float = 0.62

