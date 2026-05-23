"""Body-sphere primitive generation inspired by crochet-cad style inputs."""

from dataclasses import dataclass
from pathlib import Path

from .geometric_math import GeometricConfig, GeometricPatternGenerator, PatternMap
from .pattern_linguist import CrochetPattern, PatternFormatter
from .qa_simulation import PatternQASimulator, QAReport
from .vision_voxelizer import ImageFrame, Primitive3D, Vec3, VoxelModel
from .vision_voxelizer.image_loader import load_image
from .vision_voxelizer.segmentation import SilhouetteExtractor


@dataclass(frozen=True)
class BodySphereResult:
    model: VoxelModel
    pattern_map: PatternMap
    crochet_pattern: CrochetPattern
    qa_report: QAReport

    def render(self) -> str:
        return "\n\n".join([self.crochet_pattern.render(), self.qa_report.render()])


def generate_body_sphere_from_image(
    image_path: str | Path,
    title: str = "4666 Body Sphere",
    config: GeometricConfig | None = None,
) -> BodySphereResult:
    frame = load_image(image_path)
    return generate_body_sphere_from_frame(frame, title=title, config=config)


def generate_body_sphere_from_dimensions(
    width: int,
    height: int,
    title: str = "Body Sphere",
    config: GeometricConfig | None = None,
) -> BodySphereResult:
    frame = ImageFrame(width=width, height=height, source="supplied-dimensions")
    return generate_body_sphere_from_frame(frame, title=title, config=config)


def generate_body_sphere_from_frame(
    frame: ImageFrame,
    title: str = "Body Sphere",
    config: GeometricConfig | None = None,
) -> BodySphereResult:
    """Generate one body primitive and its draft amigurumi rounds.

    The public crochet-cad interface exposes primitive commands like
    `ball -r 18`; this app keeps the same idea but derives a body radius from
    the detected silhouette instead of requiring the user to choose it first.
    """

    silhouette = SilhouetteExtractor().extract(frame)
    primitive = _body_primitive_from_silhouette(silhouette.bbox, silhouette.confidence)
    model = VoxelModel(
        primitives=(primitive,),
        notes=(
            "Single body-sphere draft generated from image silhouette dimensions.",
            "Use this as the body foundation before adding overlap-aware limbs.",
        ),
    )
    geometry = GeometricPatternGenerator(config)
    pattern_map = geometry.generate(model)
    crochet_pattern = PatternFormatter().format(pattern_map, title=title)
    qa_report = PatternQASimulator(config).evaluate(pattern_map, model)
    return BodySphereResult(model, pattern_map, crochet_pattern, qa_report)


def _body_primitive_from_silhouette(
    bbox: tuple[int, int, int, int],
    confidence: float,
) -> Primitive3D:
    x, y, width, height = bbox
    body_height = max(1.0, height * 0.58)
    body_width = max(1.0, width * 0.54)
    radius = min(body_width, body_height) / 2

    return Primitive3D(
        id="body_sphere",
        kind="sphere",
        center=Vec3(x + width / 2, y + height * 0.56, 0),
        radius_x=radius,
        radius_y=radius,
        radius_z=radius * 0.9,
        joint_hint="hip",
        confidence=confidence,
    )

