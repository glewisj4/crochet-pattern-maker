"""Differential topology analysis for Phase 2 mesh-to-pattern planning."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import math
from typing import Literal

from photo_to_pattern.core import Face, Mesh, Vertex


CurvatureRole = Literal["increase", "decrease", "steady"]
SegmentRole = Literal["body", "appendage", "junction"]


class TopologyError(ValueError):
    """Raised when topology analysis cannot be completed."""


@dataclass(frozen=True)
class CurvatureSample:
    vertex_index: int
    gaussian_curvature: float
    area: float
    role: CurvatureRole


@dataclass(frozen=True)
class MeshSegment:
    id: str
    role: SegmentRole
    vertex_indices: tuple[int, ...]
    face_indices: tuple[int, ...]
    mean_curvature: float
    is_bifurcation: bool = False


@dataclass(frozen=True)
class TopologyMap:
    samples: tuple[CurvatureSample, ...]
    segments: tuple[MeshSegment, ...]
    bifurcation_vertices: tuple[int, ...]

    def sample_for(self, vertex_index: int) -> CurvatureSample:
        for sample in self.samples:
            if sample.vertex_index == vertex_index:
                return sample
        raise TopologyError(f"Missing curvature sample for vertex {vertex_index}.")


def analyze_mesh_topology(mesh: Mesh, *, curvature_epsilon: float = 1e-4) -> TopologyMap:
    """Calculate curvature and structural segments for a watertight mesh."""

    mesh.validate()
    samples = calculate_gaussian_curvature(mesh, curvature_epsilon=curvature_epsilon)
    bifurcations = identify_bifurcation_vertices(mesh, samples)
    segments = segment_structural_mesh(mesh, samples, bifurcations)
    return TopologyMap(samples=samples, segments=segments, bifurcation_vertices=bifurcations)


def calculate_gaussian_curvature(mesh: Mesh, *, curvature_epsilon: float = 1e-4) -> tuple[CurvatureSample, ...]:
    """Estimate vertex Gaussian curvature with the angle-deficit method.

    For a closed triangular mesh, the integrated Gaussian curvature at a vertex
    is `2*pi - sum(incident face angles)`. This function normalizes that
    deficit by one third of the incident triangle areas to produce a local
    curvature density usable by later stitch-density mapping.
    """

    mesh.validate()
    angle_sums = [0.0 for _ in mesh.vertices]
    area_sums = [0.0 for _ in mesh.vertices]

    for face in mesh.faces:
        indices = face.as_tuple()
        vertices = tuple(mesh.vertices[index] for index in indices)
        area = _triangle_area(*vertices)
        if area <= 0:
            raise TopologyError("Cannot calculate curvature on a degenerate face.")
        for local_index, vertex_index in enumerate(indices):
            angle_sums[vertex_index] += _corner_angle(vertices[local_index], vertices[(local_index + 1) % 3], vertices[(local_index + 2) % 3])
            area_sums[vertex_index] += area / 3.0

    samples: list[CurvatureSample] = []
    for vertex_index, area in enumerate(area_sums):
        if area <= 0:
            raise TopologyError(f"Vertex {vertex_index} has no incident face area.")
        curvature = (2.0 * math.pi - angle_sums[vertex_index]) / area
        if curvature > curvature_epsilon:
            role: CurvatureRole = "increase"
        elif curvature < -curvature_epsilon:
            role = "decrease"
        else:
            role = "steady"
        samples.append(CurvatureSample(vertex_index, curvature, area, role))
    return tuple(samples)


def identify_bifurcation_vertices(
    mesh: Mesh,
    samples: tuple[CurvatureSample, ...],
    *,
    valence_threshold: int = 5,
) -> tuple[int, ...]:
    """Find likely structural junctions from valence and positive curvature."""

    adjacency = _vertex_adjacency(mesh)
    if not samples:
        return ()
    sample_by_index = {sample.vertex_index: sample for sample in samples}
    max_valence = max((len(neighbors) for neighbors in adjacency.values()), default=0)
    valence_cutoff = max(valence_threshold + 1, math.ceil(max_valence * 0.75))
    bifurcations = []
    for vertex_index, neighbors in adjacency.items():
        sample = sample_by_index[vertex_index]
        if (
            len(neighbors) >= valence_cutoff
            and sample.gaussian_curvature > 0
            and (_has_directional_split(mesh, vertex_index, neighbors) or _has_neighbor_distance_split(mesh, vertex_index, neighbors))
        ):
            bifurcations.append(vertex_index)
    return tuple(sorted(bifurcations))


def segment_structural_mesh(
    mesh: Mesh,
    samples: tuple[CurvatureSample, ...],
    bifurcation_vertices: tuple[int, ...],
) -> tuple[MeshSegment, ...]:
    """Split mesh into junction and connected body/appendage segments."""

    sample_by_index = {sample.vertex_index: sample for sample in samples}
    bifurcation_set = set(bifurcation_vertices)
    adjacency = _vertex_adjacency(mesh)
    face_lookup = _vertex_faces(mesh)
    segments: list[MeshSegment] = []

    if bifurcation_set:
        segments.append(_make_segment("junction_1", "junction", tuple(sorted(bifurcation_set)), face_lookup, sample_by_index, True))

    visited: set[int] = set(bifurcation_set)
    segment_number = 1
    total_vertices = max(1, len(mesh.vertices))
    for start in range(len(mesh.vertices)):
        if start in visited:
            continue
        queue: deque[int] = deque([start])
        visited.add(start)
        vertices: list[int] = []
        while queue:
            current = queue.popleft()
            vertices.append(current)
            for neighbor in adjacency[current]:
                if neighbor in visited or neighbor in bifurcation_set:
                    continue
                visited.add(neighbor)
                queue.append(neighbor)
        if not vertices:
            continue
        role: SegmentRole = "appendage" if len(vertices) / total_vertices < 0.35 else "body"
        segments.append(_make_segment(f"{role}_{segment_number}", role, tuple(sorted(vertices)), face_lookup, sample_by_index, False))
        segment_number += 1

    return tuple(segments)


def _make_segment(
    segment_id: str,
    role: SegmentRole,
    vertices: tuple[int, ...],
    face_lookup: dict[int, set[int]],
    sample_by_index: dict[int, CurvatureSample],
    is_bifurcation: bool,
) -> MeshSegment:
    face_indices = sorted({face for vertex in vertices for face in face_lookup.get(vertex, set())})
    mean = sum(sample_by_index[index].gaussian_curvature for index in vertices) / max(1, len(vertices))
    return MeshSegment(segment_id, role, vertices, tuple(face_indices), mean, is_bifurcation)


def _vertex_adjacency(mesh: Mesh) -> dict[int, set[int]]:
    adjacency: dict[int, set[int]] = {index: set() for index in range(len(mesh.vertices))}
    for face in mesh.faces:
        for start, end in ((face.a, face.b), (face.b, face.c), (face.c, face.a)):
            adjacency[start].add(end)
            adjacency[end].add(start)
    return adjacency


def _vertex_faces(mesh: Mesh) -> dict[int, set[int]]:
    faces: dict[int, set[int]] = defaultdict(set)
    for face_index, face in enumerate(mesh.faces):
        for vertex_index in face.as_tuple():
            faces[vertex_index].add(face_index)
    return faces


def _triangle_area(a: Vertex, b: Vertex, c: Vertex) -> float:
    ab = _subtract(b, a)
    ac = _subtract(c, a)
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    return 0.5 * math.sqrt(sum(value * value for value in cross))


def _corner_angle(origin: Vertex, left: Vertex, right: Vertex) -> float:
    a = _subtract(left, origin)
    b = _subtract(right, origin)
    length_a = math.sqrt(sum(value * value for value in a))
    length_b = math.sqrt(sum(value * value for value in b))
    if length_a <= 0 or length_b <= 0:
        raise TopologyError("Cannot calculate an angle for coincident vertices.")
    cosine = sum(a[index] * b[index] for index in range(3)) / (length_a * length_b)
    return math.acos(max(-1.0, min(1.0, cosine)))


def _subtract(a: Vertex, b: Vertex) -> tuple[float, float, float]:
    return (a.x - b.x, a.y - b.y, a.z - b.z)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.inf
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return ordered[index]


def _has_directional_split(mesh: Mesh, vertex_index: int, neighbors: set[int]) -> bool:
    if len(neighbors) < 5:
        return False
    origin = mesh.vertices[vertex_index]
    angles = []
    for neighbor_index in neighbors:
        neighbor = mesh.vertices[neighbor_index]
        dx = neighbor.x - origin.x
        dy = neighbor.y - origin.y
        if abs(dx) + abs(dy) <= 1e-9:
            continue
        angles.append(math.atan2(dy, dx))
    if len(angles) < 5:
        return False
    ordered = sorted(angles)
    gaps = [ordered[index + 1] - ordered[index] for index in range(len(ordered) - 1)]
    gaps.append((ordered[0] + 2.0 * math.pi) - ordered[-1])
    return max(gaps) > (math.pi / 2.0)


def _has_neighbor_distance_split(mesh: Mesh, vertex_index: int, neighbors: set[int]) -> bool:
    origin = mesh.vertices[vertex_index]
    distances = []
    for neighbor_index in neighbors:
        neighbor = mesh.vertices[neighbor_index]
        vector = _subtract(neighbor, origin)
        distances.append(math.sqrt(sum(value * value for value in vector)))
    if len(distances) < 5:
        return False
    mean = sum(distances) / len(distances)
    if mean <= 0:
        return False
    variance = sum((distance - mean) ** 2 for distance in distances) / len(distances)
    return math.sqrt(variance) / mean > 0.12
