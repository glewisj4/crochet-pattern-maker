"""Low-poly watertight hull generation from orthographic silhouettes."""

from __future__ import annotations

import math

from .models import Face, Mesh, OrthographicViewSet, Vertex


class MeshBuildError(ValueError):
    """Raised when a mesh cannot be generated from view evidence."""


def build_watertight_mesh_from_orthographic(
    views: OrthographicViewSet,
    *,
    radial_segments: int = 24,
    height_segments: int = 12,
) -> Mesh:
    """Build a closed low-poly hull from front and side silhouettes.

    This Phase 1 hull is intentionally conservative: each horizontal ring is
    bounded independently by the front silhouette width and side silhouette
    depth at the same normalized height. That keeps the mesh projection inside
    the orthographic evidence while still producing a watertight low-poly hull
    suitable for downstream topology work.
    """

    if radial_segments < 8 or radial_segments % 4 != 0:
        raise MeshBuildError("radial_segments must be a multiple of 4 and at least 8.")
    if height_segments < 4:
        raise MeshBuildError("height_segments must be at least 4.")

    front = views.front
    side = views.side
    height = (front.height + side.height) / 2.0
    if height <= 0 or front.width <= 0 or side.width <= 0:
        raise MeshBuildError("Orthographic silhouettes must have positive dimensions.")

    max_radius_x = max(1.0, front.width / 2.0)
    max_radius_y = max(1.0, side.width / 2.0)
    radius_z = max(1.0, height / 2.0)
    vertices: list[Vertex] = [Vertex(0.0, 0.0, radius_z)]

    for ring in range(1, height_segments):
        normalized_height = ring / height_segments
        z = radius_z - (2.0 * radius_z * normalized_height)
        front_scale, side_scale = _profile_scales(views, normalized_height)
        radius_x = max_radius_x * front_scale
        radius_y = max_radius_y * side_scale
        for segment in range(radial_segments):
            theta = 2.0 * math.pi * segment / radial_segments
            vertices.append(
                Vertex(
                    math.cos(theta) * radius_x,
                    math.sin(theta) * radius_y,
                    z,
                )
            )
    bottom_index = len(vertices)
    vertices.append(Vertex(0.0, 0.0, -radius_z))

    faces: list[Face] = []
    first_ring = 1
    for segment in range(radial_segments):
        nxt = first_ring + (segment + 1) % radial_segments
        cur = first_ring + segment
        faces.append(Face(0, cur, nxt))

    for ring in range(1, height_segments - 1):
        current_start = 1 + (ring - 1) * radial_segments
        next_start = current_start + radial_segments
        for segment in range(radial_segments):
            cur = current_start + segment
            cur_next = current_start + (segment + 1) % radial_segments
            nxt = next_start + segment
            nxt_next = next_start + (segment + 1) % radial_segments
            faces.append(Face(cur, nxt, cur_next))
            faces.append(Face(cur_next, nxt, nxt_next))

    last_ring = 1 + (height_segments - 2) * radial_segments
    for segment in range(radial_segments):
        cur = last_ring + segment
        nxt = last_ring + (segment + 1) % radial_segments
        faces.append(Face(cur, bottom_index, nxt))

    mesh = Mesh(vertices=tuple(vertices), faces=tuple(faces), source="phase1_orthographic_hull")
    try:
        mesh.validate()
    except Exception as exc:
        raise MeshBuildError(f"Generated mesh failed validation: {exc}") from exc
    return mesh


def _profile_scales(views: OrthographicViewSet, normalized_height: float) -> tuple[float, float]:
    front_scale = _mask_width_at(views.front.mask, normalized_height)
    side_scale = _mask_width_at(views.side.mask, normalized_height)
    # Keep a minimum cross-section so low-poly synthetic subjects do not pinch
    # into holes before Phase 2 topology segmentation exists.
    return max(0.08, min(1.0, front_scale)), max(0.08, min(1.0, side_scale))


def _mask_width_at(mask: tuple[tuple[bool, ...], ...], normalized_height: float) -> float:
    if not mask:
        return 1.0
    row_index = max(0, min(len(mask) - 1, round(normalized_height * (len(mask) - 1))))
    row = mask[row_index]
    columns = [index for index, value in enumerate(row) if value]
    if not columns:
        return 0.12
    return max(0.12, (max(columns) - min(columns) + 1) / max(1, len(row)))
