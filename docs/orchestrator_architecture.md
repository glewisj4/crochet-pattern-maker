# Photo-to-Pattern Orchestrator Architecture

## Decisions

- Image complexity: overlapping limbs are in scope.
- Stitch style: spiral rounds.
- First output format: CFG-valid written US crochet notation.

## Sub-Agent Contracts

### A. Vision & Voxelizer

Owns silhouette extraction, overlap ambiguity detection, and primitive fitting.
Outputs an editable `VoxelModel` containing spheres, ovoids, capsules, cylinders,
cones, occlusion hints, and confidence scores.

### B. Geometric Mathematician

Consumes `VoxelModel`. Converts each primitive profile into rounds using:

- stitch aspect ratio `width:height = 1:0.8`
- linear circle rule `stitches = 6 * round_number`
- sine-based growth curves for spheres and ovoids
- staggered increase/decrease placement

### C. Pattern Linguist

Consumes the mathematical round map. Emits US crochet terminology:
`MR`, `Sc`, `Inc`, `Inv Dec`, and spiral round counts. The notation grammar
should reject transitions where the previous round count cannot produce the
next round count through valid increases/decreases.

### D. QA & Simulation

Consumes generated notation and reconstructs an approximate round profile.
Flags squashing, abrupt stitch deltas, joint tension, and unsupported overlaps.

## Overlapping Limb Policy

A single 2D photo cannot reliably determine depth order. The app must preserve
ambiguity as candidate limb capsules with confidence and manual-review metadata.
The pattern generator should not merge an ambiguous limb into the torso until
depth order and attachment points are confirmed.

## Implemented MVP

The current app implements the full draft-pattern pipeline:

1. `photo_to_pattern.vision_voxelizer` creates a confidence-scored `VoxelModel`.
2. `photo_to_pattern.geometric_math` converts primitives into stitch rounds.
3. `photo_to_pattern.pattern_linguist` formats spiral-round US crochet notation.
4. `photo_to_pattern.qa_simulation` flags stability, squashing, and overlap risks.
5. `photo_to_pattern.app.PhotoToPatternApp` orchestrates the end-to-end flow.

Run with supplied dimensions:

```powershell
python -m photo_to_pattern --width 120 --height 160 --title "Draft Bunny"
```

Run with an image file:

```powershell
python -m photo_to_pattern --image .\subject.png --title "Subject Pattern"
```

Without Pillow, image mode reads dimensions and uses the full image rectangle as
a low-confidence silhouette. With Pillow installed from `requirements.txt`, the
loader attempts a simple foreground bounding box before primitive fitting.

Generate only the body sphere for `4666.png`:

```powershell
python .\scripts\generate_body_sphere.py --image .\4666.png --output .\4666_body_sphere.txt
```

If the image is not available yet, test the same flow with dimensions:

```powershell
python .\scripts\generate_body_sphere.py --width 140 --height 180
```

Generate an annotated preview alongside the pattern:

```powershell
python -m photo_to_pattern --image .\subject.png --output .\subject_pattern.txt --preview .\subject_preview.jpg
```

Launch the GUI:

```powershell
python .\run_gui.py
```

Build the Windows executable:

```powershell
python .\build_exe.py
```

The executable is written to:

```text
dist\PhotoToPattern\PhotoToPattern.exe
```

You can also double-click:

```text
Launch PhotoToPattern.bat
```

Keep the full `dist\PhotoToPattern` folder together. The `.exe` depends on the
adjacent `_internal` directory created by PyInstaller.

The GUI supports image upload, analysis, annotated preview display, pattern
review, and export. Exported plan bundles include:

- original image
- annotated preview image
- generated crochet pattern text
- JSON details with detected regions, voxel primitives, and QA issues

## External Research Notes

- `judy2k/crochet-cad` is useful as a primitive-oriented reference. Its public
  README describes command-line generation for balls, cones, and donuts, which
  matches this app's primitive-first architecture.
- `kgshear/crogen` is useful as a reverse-flow reference: users build rows and
  stitches while a 3D model updates, then export written instructions.
- `crochetparade/CrochetPARADE` is useful as a future validation target because
  it documents a custom crochet language grammar and 2D/3D rendering workflow.

This project does not copy GPL code from those repositories. It keeps a local
implementation with compatible architectural ideas and explicit adapter points.

## Current Prototype Loop

Research result:

- No turn-key photo-to-amigurumi repository was found.
- CrochetPARADE is the best grammar/rendering reference.
- Stitchy-style image-to-crochet tools support the color-chart direction.
- The immediate local roadblock was semantic segmentation of a clean character
  illustration.

Plan:

- Keep whole-silhouette detection for scale.
- Add color-region connected components for body, mask, eyes, and legs.
- Use body and leg regions to build the primitive model.
- Keep face mask and eyes as surface applique or embroidery instructions.

Built:

- `photo_to_pattern.image_regions` extracts color regions with Pillow and pure
  Python connected components.
- `PhotoToPatternApp.from_image` now prefers a region-aware `VoxelModel`.
- Real-image output includes a `Surface Details` section.

Evaluation on `Gemini_Generated_Image_gq6cmogq6cmogq6c.png`:

- Detected foreground bbox: `753w x 892h px at 344, 923`.
- Detected body: yellow region.
- Detected face mask: dark upper region.
- Detected eyes: two pale yellow components.
- Detected legs: two dark lower components.
- Generated output: `gemini_character_pattern_prototype.txt`.

Shape-aware geometry increment:

- `ColorRegion` now stores sampled contour points, a fitted major axis, and
  median thickness.
- Leg primitives are generated as chained capsule segments along the fitted
  axis instead of one bbox-sized capsule.
- Preview rendering draws contours and fitted limb centerlines in addition to
  region boxes.
- Generated shape-fit output: `gemini_character_pattern_shape_fit.txt`.
- Generated shape-fit preview: `gemini_character_shape_preview.jpg`.

Skeleton increment:

- Limb regions now run through dependency-light thinning and longest-path
  extraction.
- Leg capsule chains follow the detected centerline instead of a single straight
  major axis.
- Preview renders the limb centerline in cyan over the detected leg regions.
- Generated skeleton output: `gemini_character_pattern_skeleton.txt`.
- Generated skeleton preview: `gemini_character_skeleton_preview.jpg`.
