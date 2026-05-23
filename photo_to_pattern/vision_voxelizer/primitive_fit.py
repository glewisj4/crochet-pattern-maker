"""Conservative primitive fitting from a 2D silhouette."""

from .config import VisionVoxelizerConfig
from .models import Axis, Primitive3D, Silhouette, Vec2, Vec3


def infer_symmetry_axis(silhouette: Silhouette) -> Axis:
    x, y, width, height = silhouette.bbox
    return Axis(
        origin=Vec2(x + width / 2, y),
        direction=Vec2(0, 1),
        confidence=max(0.1, min(0.95, silhouette.confidence)),
    )


def fit_primitives(
    silhouette: Silhouette,
    config: VisionVoxelizerConfig,
) -> tuple[Primitive3D, ...]:
    """Fit a first-pass torso/head model plus tentative limb volumes."""

    x, y, width, height = silhouette.bbox
    if width <= 0 or height <= 0:
        return ()

    depth = max(1.0, width * config.depth_inference_ratio)
    head_h = height * 0.26
    torso_h = height * 0.42
    limb_r = max(1.0, width * config.limb_width_ratio / 2)

    primitives = [
        Primitive3D(
            id="head",
            kind="ovoid",
            center=Vec3(x + width / 2, y + head_h / 2, 0),
            radius_x=width * 0.32,
            radius_y=head_h / 2,
            radius_z=depth * 0.32,
            joint_hint="neck",
            confidence=silhouette.confidence,
        ),
        Primitive3D(
            id="torso",
            kind="ovoid",
            center=Vec3(x + width / 2, y + head_h + torso_h / 2, 0),
            radius_x=width * 0.38,
            radius_y=torso_h / 2,
            radius_z=depth * 0.38,
            parent_id="head",
            joint_hint="neck",
            confidence=silhouette.confidence,
        ),
    ]

    if config.overlap_support:
        primitives.extend(
            [
                Primitive3D(
                    id="left_limb_candidate",
                    kind="capsule",
                    center=Vec3(x + width * 0.24, y + height * 0.56, -depth * 0.12),
                    radius_x=limb_r,
                    radius_y=height * 0.22,
                    radius_z=limb_r * 0.8,
                    parent_id="torso",
                    joint_hint="shoulder",
                    confidence=silhouette.confidence * 0.65,
                    metadata={"requires_manual_depth_order": True},
                ),
                Primitive3D(
                    id="right_limb_candidate",
                    kind="capsule",
                    center=Vec3(x + width * 0.76, y + height * 0.56, depth * 0.12),
                    radius_x=limb_r,
                    radius_y=height * 0.22,
                    radius_z=limb_r * 0.8,
                    parent_id="torso",
                    joint_hint="shoulder",
                    confidence=silhouette.confidence * 0.65,
                    metadata={"requires_manual_depth_order": True},
                ),
            ]
        )

    return tuple(primitives)

