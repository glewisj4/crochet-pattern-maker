"""Core VVA engine for orthographic ingestion and mesh generation."""

from .mesh_builder import MeshBuildError, build_watertight_mesh_from_orthographic
from .models import Face, Mesh, MeshValidationError, OrthographicViewSet, Silhouette, Vertex
from .ortho_processor import OrthoProcessingError, load_orthographic_views
from .yarn_physics import YarnDynamicsEngine, YarnProfile, estimate_yardage_by_color, structural_stitch_length_mm, yarn_profile

__all__ = [
    "Face",
    "Mesh",
    "MeshBuildError",
    "MeshValidationError",
    "OrthographicViewSet",
    "OrthoProcessingError",
    "Silhouette",
    "Vertex",
    "build_watertight_mesh_from_orthographic",
    "load_orthographic_views",
    "YarnProfile",
    "YarnDynamicsEngine",
    "estimate_yardage_by_color",
    "structural_stitch_length_mm",
    "yarn_profile",
]
