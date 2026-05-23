"""Export helpers for Vision & Voxelizer outputs."""

from dataclasses import asdict
import json

from .models import VoxelModel


def voxel_model_to_json(model: VoxelModel) -> str:
    return json.dumps(asdict(model), indent=2, sort_keys=True)

