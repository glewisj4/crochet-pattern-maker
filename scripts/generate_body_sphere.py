"""Generate a basic body sphere pattern for 4666.png or supplied dimensions."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from photo_to_pattern.geometric_math import GeometricConfig
from photo_to_pattern.body_sphere import (
    generate_body_sphere_from_dimensions,
    generate_body_sphere_from_image,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a body-sphere amigurumi draft.")
    parser.add_argument("--image", default="4666.png", help="Source image path. Defaults to 4666.png.")
    parser.add_argument("--width", type=int, help="Fallback silhouette width in pixels.")
    parser.add_argument("--height", type=int, help="Fallback silhouette height in pixels.")
    parser.add_argument("--title", default="4666 Body Sphere")
    parser.add_argument("--output", help="Optional output text file.")
    parser.add_argument(
        "--max-stitches",
        type=int,
        default=72,
        help="Maximum stitch count for any generated round. Default: 72.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.width and args.height:
        result = generate_body_sphere_from_dimensions(
            args.width,
            args.height,
            title=args.title,
            config=GeometricConfig(max_stitches_per_round=args.max_stitches),
        )
    else:
        image_path = Path(args.image)
        if not image_path.exists():
            parser.exit(
                2,
                f"error: {image_path} does not exist. Add 4666.png or pass --width and --height.\n",
            )
        result = generate_body_sphere_from_image(
            image_path,
            title=args.title,
            config=GeometricConfig(max_stitches_per_round=args.max_stitches),
        )

    rendered = result.render()
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
