"""Missing-view synthesis boundary.

The default implementation is deterministic so the desktop executable can run
offline. A future image-model adapter can implement the same interface and
produce stronger inferred side/back/top views from the uploaded references.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

from .models import PlanningView, ViewKind


class ViewSynthesizer:
    """Create missing views from the best available reference."""

    def synthesize(
        self,
        target: ViewKind,
        references: tuple[PlanningView, ...],
        output_path: str | Path,
    ) -> PlanningView:
        if target not in {"front", "side", "back", "top"}:
            raise ValueError(f"Cannot synthesize unsupported view: {target}")

        reference = _best_reference(references, target)
        image = Image.open(reference.cleaned_path).convert("RGBA")
        if target == "back":
            generated = _make_back(image)
        elif target == "side":
            generated = _make_side(image)
        elif target == "top":
            generated = _make_top(image)
        else:
            generated = image.copy()

        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        generated.save(destination)
        return PlanningView(
            kind=target,
            source_path=reference.cleaned_path,
            cleaned_path=destination,
            inferred=True,
            confidence=0.38,
            note=f"locally inferred from {reference.kind}; replace with image-AI adapter for production",
        )


def _best_reference(references: tuple[PlanningView, ...], target: ViewKind) -> PlanningView:
    exact = [view for view in references if view.kind == target]
    if exact:
        return exact[0]
    front = [view for view in references if view.kind == "front"]
    if front:
        return front[0]
    return references[0]


def _make_back(image: Image.Image) -> Image.Image:
    mirrored = ImageOps.mirror(image)
    alpha = mirrored.getchannel("A")
    softened = ImageEnhance.Color(mirrored.convert("RGB")).enhance(0.82).convert("RGBA")
    softened.putalpha(alpha)
    return softened


def _make_side(image: Image.Image) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return image.copy()
    subject = image.crop(bbox)
    side_width = max(28, round(subject.width * 0.58))
    resized = subject.resize((side_width, subject.height))
    canvas = Image.new("RGBA", image.size, (255, 255, 255, 0))
    x = (canvas.width - resized.width) // 2
    y = (canvas.height - resized.height) // 2
    canvas.alpha_composite(resized, (x, y))
    return canvas


def _make_top(image: Image.Image) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return image.copy()
    subject = image.crop(bbox)
    top = subject.resize((max(28, round(subject.width * 0.82)), max(28, round(subject.height * 0.34))))
    canvas = Image.new("RGBA", image.size, (255, 255, 255, 0))
    x = (canvas.width - top.width) // 2
    y = (canvas.height - top.height) // 2
    canvas.alpha_composite(top, (x, y))
    return canvas

