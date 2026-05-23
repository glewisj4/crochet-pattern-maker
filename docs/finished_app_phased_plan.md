# Phased Plan To Finish The Amigurumi Designer

## Goal

The finished app should convert 1-4 reference images into a usable amigurumi design package that is honest about accuracy, form compromises, and missing information. The output should include written crochet instructions, a planning card, generated/provided reference views, a visual design proof, stitch validation artifacts, and review checkpoints.

## Phase 1: Workflow Clarity And User Controls

Status: mostly implemented.

- Upload 1-4 images without auto-processing.
- Add a clear Process Design button.
- Show a phase/status indicator while processing.
- Let the user control target finished height, gauge, and part proportions.
- Export structured JSON for the full planning model.

Internal verification:

- Unit tests for options propagation.
- Export includes size/proportion settings.
- Generated pattern changes with target height/gauge.

## Phase 2: Re-Imagine Reference As Amigurumi

Status: next active phase.

- Add an optional workflow step that transforms uploaded art/photo references into an amigurumi-friendly reference before planning.
- For production, this should call an image model that creates front/side/back/top plush-style orthographic views.
- Offline fallback should create a local simplified reference and clearly mark it as a fallback, not true AI re-imagining.
- The planning model must record whether original or re-imagined references were used.

Internal verification:

- Output bundle includes re-imagined reference images.
- Planning model records `reimagine_as_amigurumi`.
- UI clearly exposes this as an option.

## Phase 3: Compromise Visibility

Status: next active phase.

- Track which visual features can be directly crocheted, which should become appliques/embroidery, and which are likely to be simplified.
- Show compromises in the planning notes and export JSON.
- Design proof should distinguish generated-round pieces from planned-only pieces.
- Add a "form compromise" summary: feature, reason, suggested treatment, severity.

Internal verification:

- Exported planning details include compromise items.
- Low-confidence inferred parts create review items.
- Design proof visually marks unsupported/planned-only pieces.

## Phase 4: Pattern Generation For Every Planned Part

Status: not complete.

- Generate `PatternMap` rounds for all planned parts, not only detected voxel primitives.
- Map planned parts to crochet primitives: sphere, ovoid, cylinder, cone, capsule, flat applique.
- Include quantity handling for paired arms/legs/ears.
- Generate attachment notes tied to actual rounds and stitch positions.

Internal verification:

- Design proof no longer shows major planned body parts as dashed unless intentionally omitted.
- Strict pattern validation passes for all pieces.
- Exported stitch graph has nodes for every generated crocheted part.

## Phase 5: True Stitch Graph And 3D Preview

Status: scaffolded, not complete.

- Convert strict pattern into a connected stitch graph.
- Use the graph to render an assembled 3D or pseudo-3D preview.
- Flag impossible or unstable joins.
- Show round-by-round shape profiles beside the assembled proof.

Internal verification:

- Stitch graph validates node/edge continuity.
- Preview can identify missing joins and open pieces.
- Visual proof is generated from instructions rather than only planning geometry.

## Phase 6: Model-Backed Vision Adapter

Status: interface needed.

- Add a pluggable image-AI adapter for:
  - view classification
  - missing-view generation
  - re-imagined amigurumi turnaround
  - semantic part detection
- Keep offline fallback for testing.
- Store AI confidence, prompt/version, and user-visible warnings.

Internal verification:

- App runs without API credentials.
- App produces better results when model backend is configured.
- All AI outputs are labeled as inferred and reviewable.

## Phase 7: Editable Review Workflow

Status: not complete.

- Let users edit detected/planned parts before final pattern generation.
- Add controls for part inclusion, primitive type, color, size, attachment, and detail method.
- Regenerate planning card, virtual build, and pattern from edited model.

Internal verification:

- Edits persist in project JSON.
- Exports reflect edited design, not original detection.
- Design proof updates after edits.

## Phase 8: Finished Export Package

Status: partially implemented.

- Export:
  - planning card
  - original and cleaned views
  - re-imagined views when enabled
  - structured planning model
  - compromise report
  - written crochet pattern
  - strict grammar
  - stitch graph
  - design proof
  - stitch simulation
  - JSON verification report
- Add PDF export once the image/text artifacts are stable.

Internal verification:

- One export folder contains everything needed to review and crochet the design.
- Verification report summarizes pass/fail and human review needs.

