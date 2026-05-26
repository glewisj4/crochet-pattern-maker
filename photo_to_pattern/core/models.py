"""Typed geometry models for the Phase 1 VVA core."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path


class MeshValidationError(ValueError):
    """Raised when a generated mesh fails structural integrity checks."""


@dataclass(frozen=True)
class Vertex:
    x: float
    y: float
    z: float

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class Face:
    a: int
    b: int
    c: int

    def as_tuple(self) -> tuple[int, int, int]:
        return (self.a, self.b, self.c)


@dataclass(frozen=True)
class Silhouette:
    """Foreground silhouette extracted from one orthographic view."""

    kind: str
    source_path: Path
    image_size: tuple[int, int]
    bbox: tuple[int, int, int, int]
    mask: tuple[tuple[bool, ...], ...]
    confidence: float

    @property
    def width(self) -> int:
        return self.bbox[2]

    @property
    def height(self) -> int:
        return self.bbox[3]

    @property
    def foreground_ratio(self) -> float:
        pixels = sum(1 for row in self.mask for value in row if value)
        total = max(1, len(self.mask) * (len(self.mask[0]) if self.mask else 1))
        return pixels / total


@dataclass(frozen=True)
class OrthographicViewSet:
    """Normalized view evidence used to reconstruct a low-poly hull."""

    front: Silhouette
    side: Silhouette
    back: Silhouette | None = None
    top: Silhouette | None = None

    def available_views(self) -> tuple[Silhouette, ...]:
        return tuple(view for view in (self.front, self.side, self.back, self.top) if view is not None)


@dataclass(frozen=True)
class Mesh:
    """Low-poly triangular mesh in app-local coordinates."""

    vertices: tuple[Vertex, ...]
    faces: tuple[Face, ...]
    source: str = "orthographic_hull"

    def validate(self) -> None:
        """Validate indexing, finite coordinates, triangular faces, and watertight edges."""

        if len(self.vertices) < 4:
            raise MeshValidationError("Mesh must contain at least four vertices.")
        if len(self.faces) < 4:
            raise MeshValidationError("Mesh must contain at least four faces.")

        for index, vertex in enumerate(self.vertices):
            if not all(isfinite(value) for value in vertex.as_tuple()):
                raise MeshValidationError(f"Vertex {index} contains a non-finite coordinate.")

        edge_counts: dict[tuple[int, int], int] = {}
        for face_index, face in enumerate(self.faces):
            indices = face.as_tuple()
            if len(set(indices)) != 3:
                raise MeshValidationError(f"Face {face_index} is degenerate.")
            for index in indices:
                if index < 0 or index >= len(self.vertices):
                    raise MeshValidationError(f"Face {face_index} references missing vertex {index}.")
            for start, end in ((face.a, face.b), (face.b, face.c), (face.c, face.a)):
                edge = (start, end) if start < end else (end, start)
                edge_counts[edge] = edge_counts.get(edge, 0) + 1

        bad_edges = [edge for edge, count in edge_counts.items() if count != 2]
        if bad_edges:
            raise MeshValidationError(f"Mesh is not watertight; {len(bad_edges)} edge(s) are not shared by two faces.")
        if self.signed_volume() <= 0:
            raise MeshValidationError("Mesh volume must be positive; face winding may be invalid.")

    def bounds(self) -> tuple[Vertex, Vertex]:
        if not self.vertices:
            raise MeshValidationError("Cannot calculate bounds for an empty mesh.")
        xs = [vertex.x for vertex in self.vertices]
        ys = [vertex.y for vertex in self.vertices]
        zs = [vertex.z for vertex in self.vertices]
        return Vertex(min(xs), min(ys), min(zs)), Vertex(max(xs), max(ys), max(zs))

    def signed_volume(self) -> float:
        volume = 0.0
        for face in self.faces:
            a = self.vertices[face.a]
            b = self.vertices[face.b]
            c = self.vertices[face.c]
            volume += (
                a.x * (b.y * c.z - b.z * c.y)
                - a.y * (b.x * c.z - b.z * c.x)
                + a.z * (b.x * c.y - b.y * c.x)
            ) / 6.0
        return volume

    def export_obj(self, output_path: str | Path) -> Path:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# {self.source}"]
        for vertex in self.vertices:
            lines.append(f"v {vertex.x:.6f} {vertex.y:.6f} {vertex.z:.6f}")
        for face in self.faces:
            lines.append(f"f {face.a + 1} {face.b + 1} {face.c + 1}")
        destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return destination
