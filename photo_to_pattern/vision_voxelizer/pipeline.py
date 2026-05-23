"""Main Vision & Voxelizer orchestration."""

from pathlib import Path

from .config import VisionVoxelizerConfig
from .image_loader import load_image
from .models import ImageFrame, VoxelModel
from .overlap import infer_occlusions
from .primitive_fit import fit_primitives, infer_symmetry_axis
from .segmentation import SilhouetteExtractor


class VisionVoxelizer:
    """Convert a photo or supplied frame into an editable primitive model."""

    def __init__(
        self,
        config: VisionVoxelizerConfig | None = None,
        silhouette_extractor: SilhouetteExtractor | None = None,
    ) -> None:
        self.config = config or VisionVoxelizerConfig()
        self.silhouette_extractor = silhouette_extractor or SilhouetteExtractor()

    def process(self, image_path: str | Path) -> VoxelModel:
        return self.process_frame(load_image(image_path))

    def process_frame(self, frame: ImageFrame) -> VoxelModel:
        silhouette = self.silhouette_extractor.extract(frame)
        primitives = fit_primitives(silhouette, self.config)
        occlusions = infer_occlusions(silhouette, self.config)
        axis = infer_symmetry_axis(silhouette) if self.config.assume_bilateral_symmetry else None
        notes = (
            "Overlapping limbs are represented as candidate capsules with manual depth-order review.",
            "Downstream stitch generation must apply 1:0.8 stitch aspect correction.",
            "Pattern output target is spiral-round US crochet notation.",
        )
        return VoxelModel(
            primitives=primitives,
            occlusions=occlusions,
            symmetry_axis=axis,
            scale_hint=None,
            notes=notes,
        )

