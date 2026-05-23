# Antigravity Handoff: Crochet Pattern Maker

## Context

Workspace:

```text
H:\Dev\MyApps\crochet pattern maker
```

This is a Python/Tkinter desktop app that turns 1-4 reference images into an amigurumi planning package. The current app can:

- Upload 1-4 images.
- Detect and split one-image orthographic contact sheets.
- Remove/normalize backgrounds.
- Infer missing views.
- Build a structured `PlanningModel`.
- Generate planned-part crochet rounds.
- Render a planning card, virtual build, design proof, stitch graph, accuracy JSON, and clean single-file HTML report.
- Export a Windows executable with PyInstaller.

Primary executable:

```text
dist\PhotoToPattern\PhotoToPattern.exe
```

## Current State

Most recent verified state:

```powershell
python -m unittest discover -s tests
# Ran 44 tests ... OK

python .\build_exe.py
# Build complete. Output in dist\PhotoToPattern
```

Important recent changes:

- `photo_to_pattern/planning/contact_sheet.py`
  - Detects orthographic contact sheets more robustly.
  - Avoids false positives for normal wide single-character images and multi-object non-sheets.
  - Cleans extracted panels by removing caption artifacts and foreground-cropping the subject.

- `photo_to_pattern/planning/card_renderer.py`
  - Uses foreground-aware fitting.
  - Labels views as `Uploaded`, `Extracted`, or `Inferred`.
  - Corrects shape-guide overlay coordinates after cropping.

- `photo_to_pattern/planning/agent.py`
  - Adds feature/treatment tier markers through existing text fields:
    - `tier:structural`
    - `tier:flat applique`
    - `tier:embroidery guide`
    - `tier:color/overlay cue`
  - Promotes fox/leaf-like features into details/construction:
    - leaf cloak/body wrap
    - leaf vein embroidery
    - inner ears
    - snout/muzzle
    - closed eyes
    - tail color/detail

- `photo_to_pattern/planning/virtual_build.py`
  - Renders richer overlays: leaf cloak, branch veins, inner ears, muzzle/nose/mouth, closed eyes, and tail tip cue.
  - Demotes inferred arms/legs so they do not dominate the silhouette.

- `photo_to_pattern/report.py`
  - Creates a clean single-file HTML design report with embedded base64 images.
  - Includes planning card, virtual build, design proof, accuracy summary, process steps, planning model, QA summary, and generated pattern.

- `photo_to_pattern/exporter.py`
  - Wires the clean report into `export_planning_bundle`.

## User's Current Concern

The user is still unhappy with:

- Planning-card image framing and extracted view quality.
- Virtual build not closely matching the original fox/leaf character.
- Need for finer detail design logic.
- Desire for one clean report file that explains the design process.

Recent work improved this, but the next system should assume more refinement is needed.

## Required Working Style

Use a multi-agent flow similar to the one used in this thread.

Recommended flow:

1. **Orchestrator agent**
   - Owns end-to-end sequencing.
   - Keeps phases small.
   - Integrates changes.
   - Runs tests/builds.
   - Decides when to advance.

2. **Researcher agent**
   - Researches amigurumi-specific treatment decisions:
     - structural crochet vs applique vs embroidery vs colorwork vs hardware
     - view extraction/framing strategies
     - visual proof/report layout
   - Returns implementation guidance, not code, unless explicitly assigned.

3. **Phase worker agents**
   - Each owns a disjoint write scope.
   - Example phase ownership:
     - Contact-sheet/framing worker: `planning/contact_sheet.py`, `planning/card_renderer.py`, related tests.
     - Planning-detail worker: `planning/agent.py`, `planning/models.py` only if needed, related tests.
     - Virtual-build worker: `planning/virtual_build.py`, related tests.
     - Report/export worker: `report.py`, `exporter.py`, related tests.
   - Workers must not revert or overwrite each other's files.

4. **Reviewer agent**
   - Runs after each phase or after parallel phase integration.
   - Reviews for:
     - correctness
     - regressions
     - missing tests
     - whether the phase goal is actually met
   - Findings should be ordered by severity.
   - Do not build or ship until reviewer blockers are fixed.

5. **Final gate**
   - Run focused tests for changed areas.
   - Run full suite.
   - Rebuild executable.
   - If PyInstaller fails because `dist\PhotoToPattern` is locked, stop the running `PhotoToPattern.exe` process and retry.

## External GitHub/Research References Used

No third-party repository code was copied into this project. The app uses local implementations, but the architecture was informed by these repositories/projects:

- `judy2k/crochet-cad`
  - Primitive-oriented crochet generation reference.
  - Useful concept: start from simple crochetable primitives like spheres/cones and map them to pattern instructions.

- `kgshear/crogen`
  - Reverse-flow crochet modeling reference.
  - Useful concept: a stitch/pattern editing workflow with immediate visual feedback.

- `crochetparade/CrochetPARADE`
  - Crochet language and 2D/3D rendering reference.
  - Important licensing note: CrochetPARADE is GPL. Do not copy implementation code into this project unless license implications are explicitly accepted.

Additional non-GitHub research references used conceptually:

- AmiGo research paper: graph-based amigurumi design from 3D models.
- General amigurumi guides for deciding when details should be structural pieces, appliques, embroidery, colorwork, or hardware.

Keep this project's implementation independent. Treat those repos as architectural references only.

## Current Architecture Map

Main app path:

```text
run_gui.py
  -> photo_to_pattern/gui.py
    -> PlanningOrchestrator.create_from_images()
    -> PhotoToPatternApp.from_image_with_plan()
    -> export_plan_bundle()
    -> export_planning_bundle()
```

Planning:

```text
photo_to_pattern/planning/orchestrator.py
photo_to_pattern/planning/contact_sheet.py
photo_to_pattern/planning/background.py
photo_to_pattern/planning/view_classifier.py
photo_to_pattern/planning/view_synthesizer.py
photo_to_pattern/planning/agent.py
photo_to_pattern/planning/models.py
photo_to_pattern/planning/card_renderer.py
photo_to_pattern/planning/virtual_build.py
```

Pattern generation:

```text
photo_to_pattern/part_generator/generator.py
photo_to_pattern/geometric_math/*
photo_to_pattern/pattern_linguist/*
```

Verification and proof:

```text
photo_to_pattern/verification/validator.py
photo_to_pattern/verification/stitch_graph.py
photo_to_pattern/verification/graph_validator.py
photo_to_pattern/verification/design_proof.py
photo_to_pattern/verification/renderer.py
```

Accuracy/report/export:

```text
photo_to_pattern/accuracy/report.py
photo_to_pattern/report.py
photo_to_pattern/exporter.py
```

## Immediate Next Work

### 1. Make Detail Treatments Explicit

Current treatment tiering is encoded in free text. Antigravity should consider adding explicit model fields while preserving backwards compatibility:

```python
treatment: Literal["structural", "applique", "embroidery", "colorwork", "hardware"]
placement_anchor: str
view_evidence: tuple[str, ...]
scale_priority: str
child_safe: bool
round_grid_fit: str
```

Likely target:

```text
photo_to_pattern/planning/models.py
```

Migration rule:

- Keep existing dataclasses working.
- Add defaults so old tests/export JSON do not break.
- Update renderers to prefer explicit fields when present, falling back to current text markers.

### 2. Improve Contact-Sheet Extraction Further

Current detection is better, but still heuristic.

Next steps:

- Add fixture tests using the user's actual image:

```text
H:\Downloads\Gemini_Generated_Image_4kjfsj4kjfsj4kjf.png
```

or the latest generated exports:

```text
H:\Downloads\patterns\4th\
```

- Confirm:
  - front/side/back/top are detected as real extracted views
  - labels are removed
  - subject occupies enough of each view
  - no normal wide single-image reference is falsely split

### 3. Make Virtual Build More Data-Driven

The current renderer still contains fox-specific fallback logic. Next work:

- Render all structural `DesignPart`s from model data.
- Render `DesignDetail`s according to treatment/placement metadata.
- Separate proof concepts:
  - **virtual build from plan**
  - **graph proof from generated instructions**
  - **visual comparison against reference**

The virtual build should show the intended design; the design proof should show what the instructions actually build.

### 4. Improve Clean Report

Current single-file HTML report exists and is embedded.

Next work:

- Make it the primary export artifact in the GUI.
- Add a top-level process summary:
  - reference intake
  - view extraction
  - feature treatment decisions
  - generated structural pieces
  - appliques/embroidery/colorwork
  - compromises
  - accuracy/proof result
  - human review checklist

### 5. Add Human-Editable Review Stage

The app needs a review/edit step before final pattern generation:

- Edit part type.
- Include/exclude part.
- Change treatment.
- Adjust colors.
- Adjust size/proportion.
- Mark features as applique/embroidery/structural.
- Regenerate card, virtual build, and pattern after edits.

This is likely the most important product step after the current heuristic improvements.

## Known Issues / Risks

- The app can pass stitch graph checks while still visually failing the target design. Graph validity is not visual fidelity.
- Contact-sheet detection is heuristic and needs real fixture coverage.
- The planning model still relies heavily on deterministic color/position heuristics.
- The virtual build is illustrative, not a physical yarn simulation.
- PyInstaller build can fail if `PhotoToPattern.exe` is running and locking files in `dist\PhotoToPattern`.
- The workspace is currently not a Git repository unless Antigravity receives this after a repo has been created elsewhere.

## Commands

Run full test suite:

```powershell
python -m unittest discover -s tests
```

Run focused latest areas:

```powershell
python -m unittest tests.test_contact_sheet tests.test_planning_card_renderer tests.test_planning_orchestrator tests.test_virtual_build tests.test_exporter tests.test_accuracy
```

Run GUI:

```powershell
python .\run_gui.py
```

Build executable:

```powershell
python .\build_exe.py
```

If build fails due locked output:

```powershell
Get-Process | Where-Object { $_.ProcessName -like '*PhotoToPattern*' -or ($_.Path -and $_.Path -like '*crochet pattern maker*') } | Select-Object Id,ProcessName,Path
Stop-Process -Id <id>
python .\build_exe.py
```

## GitHub Push Status

At the time this handoff was written, this directory was not a Git repository:

```text
fatal: not a git repository (or any of the parent directories): .git
```

There was no configured Git remote to push to from this workspace. To push current progress, Antigravity needs either:

- an existing `.git` repo restored around this folder, or
- a GitHub repository URL and approval to initialize this folder as a new repo.

Suggested commands once a remote exists:

```powershell
git status
git add .
git commit -m "Improve amigurumi planning fidelity and clean report export"
git push -u origin main
```

