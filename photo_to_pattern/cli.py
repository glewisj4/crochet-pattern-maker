"""Command-line interface for the photo-to-pattern MVP."""

from __future__ import annotations

import argparse
from pathlib import Path

from .app import PhotoToPatternApp
from .geometric_math import GeometricConfig
from .preview import render_analysis_preview
from .vision_voxelizer import ImageFrame


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an amigurumi draft pattern from a photo or dimensions.")
    parser.add_argument("--image", help="Path to a source image. Requires a configured image decoding adapter.")
    parser.add_argument("--width", type=int, help="Synthetic/supplied silhouette width in pixels.")
    parser.add_argument("--height", type=int, help="Synthetic/supplied silhouette height in pixels.")
    parser.add_argument("--title", default="Photo-to-Amigurumi Pattern")
    parser.add_argument("--output", help="Optional text output path.")
    parser.add_argument("--preview", help="Optional annotated preview image output path.")
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

    app = PhotoToPatternApp(GeometricConfig(max_stitches_per_round=args.max_stitches))

    try:
        if args.width and args.height:
            result = app.from_frame(
                ImageFrame(width=args.width, height=args.height, source=args.image or "synthetic-frame"),
                title=args.title,
            )
        elif args.image:
            result = app.from_image(args.image, title=args.title)
        else:
            parser.error("Provide either --image or both --width and --height.")
    except Exception as exc:
        parser.exit(2, f"error: {exc}\n")

    rendered = result.render()
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    if args.preview:
        if not args.image or result.character_analysis is None:
            parser.exit(2, "error: --preview requires --image.\n")
        render_analysis_preview(args.image, result.character_analysis, args.preview)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
