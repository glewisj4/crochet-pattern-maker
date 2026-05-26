"""Orthographic image ingestion and silhouette extraction for VVA."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from .models import OrthographicViewSet, Silhouette


class OrthoProcessingError(ValueError):
    """Raised when orthographic view ingestion cannot produce usable silhouettes."""


def load_orthographic_views(
    *,
    front: str | Path,
    side: str | Path,
    back: str | Path | None = None,
    top: str | Path | None = None,
    mask_size: int = 64,
) -> OrthographicViewSet:
    """Load and normalize front/side/back/top references into silhouettes."""

    if mask_size < 16:
        raise OrthoProcessingError("mask_size must be at least 16.")
    try:
        front_silhouette = extract_silhouette(front, "front", mask_size)
        side_silhouette = extract_silhouette(side, "side", mask_size)
        back_silhouette = extract_silhouette(back, "back", mask_size) if back is not None else None
        top_silhouette = extract_silhouette(top, "top", mask_size) if top is not None else None
    except OSError as exc:
        raise OrthoProcessingError(f"Unable to load orthographic image: {exc}") from exc

    _validate_pair(front_silhouette, side_silhouette)
    return OrthographicViewSet(
        front=front_silhouette,
        side=side_silhouette,
        back=back_silhouette,
        top=top_silhouette,
    )


def extract_silhouette(image_path: str | Path, kind: str, mask_size: int = 64) -> Silhouette:
    """Extract a foreground bounding silhouette from one image."""

    source = Path(image_path)
    try:
        image = Image.open(source).convert("RGBA")
    except OSError as exc:
        raise OrthoProcessingError(f"Unable to open {kind} view at {source}: {exc}") from exc

    bbox = _foreground_bbox(image)
    if bbox is None:
        raise OrthoProcessingError(f"{kind} view has no detectable foreground.")
    left, top, right, bottom = bbox
    width = max(1, right - left)
    height = max(1, bottom - top)
    cropped = image.crop(bbox)
    mask = _normalized_mask(cropped, mask_size)
    confidence = _confidence(mask, width, height, image.size)
    return Silhouette(
        kind=kind,
        source_path=source,
        image_size=image.size,
        bbox=(left, top, width, height),
        mask=mask,
        confidence=confidence,
    )


def _validate_pair(front: Silhouette, side: Silhouette) -> None:
    height_ratio = min(front.height, side.height) / max(front.height, side.height)
    if height_ratio < 0.55:
        raise OrthoProcessingError(
            f"Front/side view heights are inconsistent: front={front.height}, side={side.height}."
        )


def _foreground_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    pixels = image.load()
    min_x, min_y = image.width, image.height
    max_x = max_y = -1
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha <= 24:
                continue
            if _is_background(red, green, blue):
                continue
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    if max_x < min_x:
        return None
    return _pad_bbox((min_x, min_y, max_x + 1, max_y + 1), image.size)


def _normalized_mask(image: Image.Image, mask_size: int) -> tuple[tuple[bool, ...], ...]:
    resized = image.resize((mask_size, mask_size))
    pixels = resized.load()
    rows: list[tuple[bool, ...]] = []
    for y in range(mask_size):
        row = []
        for x in range(mask_size):
            red, green, blue, alpha = pixels[x, y]
            row.append(alpha > 24 and not _is_background(red, green, blue))
        rows.append(tuple(row))
    return tuple(rows)


def _confidence(mask: tuple[tuple[bool, ...], ...], width: int, height: int, image_size: tuple[int, int]) -> float:
    foreground = sum(1 for row in mask for value in row if value)
    ratio = foreground / max(1, len(mask) * (len(mask[0]) if mask else 1))
    image_area = max(1, image_size[0] * image_size[1])
    bbox_ratio = width * height / image_area
    score = 0.35 + min(0.35, ratio) + min(0.30, bbox_ratio * 1.8)
    return max(0.0, min(1.0, score))


def _is_background(red: int, green: int, blue: int) -> bool:
    return red >= 242 and green >= 242 and blue >= 242


def _pad_bbox(box: tuple[int, int, int, int], size: tuple[int, int]) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    pad_x = max(2, round(width * 0.04))
    pad_y = max(2, round(height * 0.04))
    return (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(size[0], right + pad_x),
        min(size[1], bottom + pad_y),
    )
