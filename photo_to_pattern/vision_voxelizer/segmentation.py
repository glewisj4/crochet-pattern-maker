"""Foreground segmentation contracts."""

from .models import ImageFrame, Silhouette, Vec2


class SegmentationUnavailableError(RuntimeError):
    """Raised when segmentation needs a real image backend."""


class SilhouetteExtractor:
    """Extracts the foreground silhouette from a decoded image frame."""

    def extract(self, frame: ImageFrame) -> Silhouette:
        if frame.width <= 0 or frame.height <= 0:
            raise SegmentationUnavailableError(
                "Image decoding is not configured. Install a Pillow/OpenCV adapter "
                "or provide an ImageFrame with width, height, and pixels."
            )

        bbox = _bbox_from_pixels(frame)
        confidence = 0.72 if bbox is not None else 0.35
        if bbox is None:
            bbox = (0, 0, frame.width, frame.height)

        x, y, width, height = bbox
        contour = (
            Vec2(x, y),
            Vec2(x + width, y),
            Vec2(x + width, y + height),
            Vec2(x, y + height),
        )
        return Silhouette(
            bbox=bbox,
            contour=contour,
            area=float(width * height),
            confidence=confidence,
        )


def _bbox_from_pixels(frame: ImageFrame) -> tuple[int, int, int, int] | None:
    image = frame.pixels
    if image is None or not hasattr(image, "getdata"):
        return None

    pixel_source = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
    pixels = list(pixel_source)
    if not pixels:
        return None

    corners = [
        pixels[0],
        pixels[frame.width - 1],
        pixels[-frame.width],
        pixels[-1],
    ]
    background = _average_rgba(corners)
    min_x, min_y = frame.width, frame.height
    max_x, max_y = -1, -1

    for index, pixel in enumerate(pixels):
        x = index % frame.width
        y = index // frame.width
        if _foreground_score(pixel, background) > 34:
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

    if max_x < min_x or max_y < min_y:
        return None
    return min_x, min_y, max_x - min_x + 1, max_y - min_y + 1


def _average_rgba(pixels: list[tuple[int, ...]]) -> tuple[float, float, float, float]:
    channels = []
    for channel in range(4):
        values = [pixel[channel] if len(pixel) > channel else 255 for pixel in pixels]
        channels.append(sum(values) / len(values))
    return tuple(channels)  # type: ignore[return-value]


def _foreground_score(pixel: tuple[int, ...], background: tuple[float, float, float, float]) -> float:
    rgba = tuple(pixel[index] if len(pixel) > index else 255 for index in range(4))
    alpha_signal = 255 - rgba[3]
    color_signal = sum(abs(rgba[index] - background[index]) for index in range(3)) / 3
    return max(alpha_signal, color_signal)
