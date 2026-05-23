"""Heuristics for identifying uploaded character views."""

from __future__ import annotations

from pathlib import Path

from .background import foreground_bbox
from .models import ViewKind


def classify_view(path: str | Path, used: set[ViewKind] | None = None) -> tuple[ViewKind, float, str]:
    """Classify a cleaned character view from filename and silhouette shape."""

    image_path = Path(path)
    used = used or set()
    name = image_path.stem.lower()
    for kind in ("front", "side", "back", "top"):
        if kind in name and kind not in used:
            return kind, 0.95, "classified from filename"

    x, y, width, height = foreground_bbox(image_path)
    del x, y
    ratio = width / max(1, height)
    if "front" not in used:
        if 0.48 <= ratio <= 0.88:
            return "front", 0.62, "classified from upright silhouette"
    if "side" not in used and ratio < 0.58:
        return "side", 0.58, "classified from narrow silhouette"
    if "back" not in used:
        return "back", 0.44, "assigned as remaining rear view"
    return "unknown", 0.25, "unable to classify confidently"

