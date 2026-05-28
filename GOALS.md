# PhotoToPattern Remediation & Completion Progress

## Phase 1 & 2 Correction: Semantic Vision & Advanced Primitives
- [x] Hard-lock the Gemini VLM pipeline; throw a termination exception on unconfigured API keys or local fallback loops.
- [x] Implement VLM prompt structures to strictly enforce 6-point part categorization (Primary Body, Accents, Appendages, Overlaid Garments, Facial Embroidery, Insets).
- [x] Build the `YarnDynamicsEngine` module (`core/yarn_physics.py`) to process standard yarn weight (#1-#7), hook size, and material fiber selectors (Acrylic, Cotton, Wool, Chenille).
- [x] Implement a geometric formula engine in `core/yarn_physics.py` to calculate accurate multi-color yardage totals based on structural stitch counts.
- [x] Build specialized shape-generation primitives in `compiler/generators.py`:
  - [x] Curled/tapered tails via short-row modifiers.
  - [x] Dual-color inset ears.
  - [x] Eccentric oval muzzles/snouts.
  - [x] Independent garment panels (e.g., leaf cloaks) with distinct stitch instructions.
- [x] Refactor the body compiler to force mathematical decrease sequences (`[sc, dec] x 6 -> dec around`) ensuring all 3D shapes close securely.
- [x] Add regression tests ensuring no limb or body components compile with their widest round sitting on an exposed un-joined edge.

## Phase 3 Correction: True Stitch-Graph Physics & Vision-Matching Validation
- [ ] Rewrite `planning/virtual_build.py` to strip out symbolic vector drawings.
- [ ] Implement a node-based spring renderer that strings together actual single crochet coordinate vectors.
- [ ] Update the internal stuffing simulation model to scale its expansion limits against the elastic thresholds provided by the `YarnDynamicsEngine` (e.g., high stretch for acrylic/chenille, low stretch for cotton).
- [ ] Implement an automated image similarity validation step (e.g., using structural edge matching) comparing the simulated virtual build directly against the original orthographic profile cards.
- [ ] Restructure the final validation scoring logic: Force a hard failure if the true structural planning confidence index rates under 75%.

## Phase 4: Integration, UI Update, and Deployment Packaging
- [ ] Connect the closed-loop optimization system: automatically trigger re-compilation runs with adjusted stitch counts if the structural similarity score misses the 90% threshold.
- [ ] Update the GUI dashboard display to trace multi-color yardage requirements and dropdown selectors.
- [ ] Execute comprehensive standalone test arrays (`python -m unittest discover -s tests`).
- [ ] Run PyInstaller system assembly scripts to compile the verified standalone binary (`PhotoToPattern.exe`).
