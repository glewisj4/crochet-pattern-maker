"""Pillow-based color segmentation for simple illustrated characters."""

from collections import deque
from pathlib import Path

from photo_to_pattern.vision_voxelizer.image_loader import load_image
from photo_to_pattern.vision_voxelizer.segmentation import SilhouetteExtractor

from .models import CharacterAnalysis, ColorRegion, RegionKind
from .shape_fit import (
    centerline_from_component,
    contour_from_component,
    major_axis_from_component,
    median_thickness_from_component,
)


class CharacterRegionAnalyzer:
    """Extract body, mask, eye, and limb regions from a clean illustration."""

    def __init__(self, max_dimension: int = 700, min_component_pixels: int = 24) -> None:
        self.max_dimension = max_dimension
        self.min_component_pixels = min_component_pixels

    def analyze(self, image_path: str | Path) -> CharacterAnalysis:
        frame = load_image(image_path)
        if frame.pixels is None:
            return CharacterAnalysis(
                source=str(image_path),
                image_size=(frame.width, frame.height),
                foreground_bbox=(0, 0, frame.width, frame.height),
                regions=(),
                warnings=("Pillow is required for color-region analysis.",),
            )

        image = frame.pixels.convert("RGBA")
        scale = min(1.0, self.max_dimension / max(image.width, image.height))
        if scale < 1.0:
            sample = image.resize((round(image.width * scale), round(image.height * scale)))
        else:
            sample = image

        sample_frame = type(frame)(
            width=sample.width,
            height=sample.height,
            source=frame.source,
            pixels=sample,
        )
        silhouette = SilhouetteExtractor().extract(sample_frame)
        masks = self._build_masks(sample, silhouette.bbox)
        raw_regions = []
        for kind, mask in masks.items():
            raw_regions.extend(self._components(kind, mask, sample, scale))

        regions = self._reinterpret_dark_regions(raw_regions, silhouette.bbox, scale)
        warnings = self._warnings(regions)
        bbox = _scale_bbox(silhouette.bbox, 1 / scale)
        return CharacterAnalysis(
            source=str(image_path),
            image_size=(image.width, image.height),
            foreground_bbox=bbox,
            regions=tuple(regions),
            warnings=tuple(warnings),
        )

    def _build_masks(
        self,
        image: object,
        foreground_bbox: tuple[int, int, int, int],
    ) -> dict[RegionKind, set[tuple[int, int]]]:
        x0, y0, width, height = foreground_bbox
        x1 = x0 + width
        y1 = y0 + height
        masks: dict[RegionKind, set[tuple[int, int]]] = {
            "body": set(),
            "face_mask": set(),
            "eye": set(),
        }

        pixels = image.load()
        for y in range(max(0, y0), min(image.height, y1)):
            for x in range(max(0, x0), min(image.width, x1)):
                r, g, b, a = pixels[x, y]
                if a < 32 or _is_background(r, g, b):
                    continue
                kind = _classify_pixel(r, g, b)
                if kind in masks:
                    masks[kind].add((x, y))
        return masks

    def _components(
        self,
        kind: RegionKind,
        mask: set[tuple[int, int]],
        image: object,
        scale: float,
    ) -> list[ColorRegion]:
        regions: list[ColorRegion] = []
        remaining = set(mask)
        pixels = image.load()

        while remaining:
            start = remaining.pop()
            queue = deque([start])
            component = [start]
            while queue:
                x, y = queue.popleft()
                for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        queue.append(neighbor)
                        component.append(neighbor)

            if len(component) < self.min_component_pixels:
                continue
            regions.append(_region_from_component(kind, component, pixels, scale))

        return regions

    def _reinterpret_dark_regions(
        self,
        regions: list[ColorRegion],
        foreground_bbox: tuple[int, int, int, int],
        scale: float,
    ) -> list[ColorRegion]:
        dark_regions = [region for region in regions if region.kind == "face_mask"]
        other_regions = [region for region in regions if region.kind != "face_mask"]
        if not dark_regions:
            return sorted(other_regions, key=lambda region: region.area, reverse=True)

        fg_x, fg_y, fg_w, fg_h = _scale_bbox(foreground_bbox, 1 / scale)
        lower_cutoff = fg_y + fg_h * 0.66
        sorted_dark = sorted(dark_regions, key=lambda region: region.area, reverse=True)
        face_mask = sorted_dark[0]
        retyped = [
            ColorRegion(
                kind="face_mask",
                bbox=face_mask.bbox,
                area=face_mask.area,
                centroid=face_mask.centroid,
                average_color=face_mask.average_color,
                confidence=0.86,
                contour=face_mask.contour,
                major_axis=face_mask.major_axis,
                centerline=face_mask.centerline,
                median_thickness=face_mask.median_thickness,
            )
        ]

        for region in sorted_dark[1:]:
            kind: RegionKind = "leg" if region.centroid[1] >= lower_cutoff else "unknown"
            retyped.append(
                ColorRegion(
                    kind=kind,
                    bbox=region.bbox,
                    area=region.area,
                    centroid=region.centroid,
                    average_color=region.average_color,
                    confidence=0.78 if kind == "leg" else 0.45,
                    contour=region.contour,
                    major_axis=region.major_axis,
                    centerline=region.centerline,
                    median_thickness=region.median_thickness,
                )
            )

        return sorted(other_regions + retyped, key=lambda region: (region.kind, -region.area))

    def _warnings(self, regions: list[ColorRegion]) -> list[str]:
        warnings = []
        if not any(region.kind == "body" for region in regions):
            warnings.append("No yellow body region detected.")
        if not any(region.kind == "face_mask" for region in regions):
            warnings.append("No dark face-mask region detected.")
        if len([region for region in regions if region.kind == "eye"]) < 1:
            warnings.append("No pale eye region detected.")
        if len([region for region in regions if region.kind == "leg"]) < 2:
            warnings.append("Fewer than two leg regions detected.")
        return warnings


def _classify_pixel(r: int, g: int, b: int) -> RegionKind:
    luma = (r + g + b) / 3
    spread = max(r, g, b) - min(r, g, b)
    if luma < 95:
        return "face_mask"
    if r > 190 and g > 175 and 90 < b < 230 and r - b > 25 and g - b > 18:
        return "eye"
    if r > 145 and g > 95 and b < 115 and spread > 45:
        return "body"
    return "unknown"


def _is_background(r: int, g: int, b: int) -> bool:
    return r > 235 and g > 235 and b > 235 and max(r, g, b) - min(r, g, b) < 18


def _region_from_component(
    kind: RegionKind,
    component: list[tuple[int, int]],
    pixels: object,
    scale: float,
) -> ColorRegion:
    component_set = set(component)
    xs = [point[0] for point in component_set]
    ys = [point[1] for point in component_set]
    total_r = total_g = total_b = 0
    for x, y in component_set:
        r, g, b, _ = pixels[x, y]
        total_r += r
        total_g += g
        total_b += b

    area = len(component_set)
    bbox = (
        round(min(xs) / scale),
        round(min(ys) / scale),
        round((max(xs) - min(xs) + 1) / scale),
        round((max(ys) - min(ys) + 1) / scale),
    )
    centroid = (sum(xs) / area / scale, sum(ys) / area / scale)
    return ColorRegion(
        kind=kind,
        bbox=bbox,
        area=round(area / (scale * scale)),
        centroid=centroid,
        average_color=(round(total_r / area), round(total_g / area), round(total_b / area)),
        confidence=0.74,
        contour=contour_from_component(component_set, scale),
        major_axis=major_axis_from_component(component_set, scale),
        centerline=centerline_from_component(component_set, scale),
        median_thickness=median_thickness_from_component(component_set, scale),
    )


def _scale_bbox(bbox: tuple[int, int, int, int], factor: float) -> tuple[int, int, int, int]:
    x, y, width, height = bbox
    return round(x * factor), round(y * factor), round(width * factor), round(height * factor)
