# Amigurumi Pattern Design: A Technical Research Guide for App Development

This document consolidates research on the principles, mathematics, and logic of amigurumi crochet pattern design. It is intended to serve as a reference for developing an application that converts 3D images or photos into accurate crochet patterns.

## 1. Fundamentals of Amigurumi Construction
Amigurumi (Japanese for "knitted or crocheted stuffed toy") relies on creating 3D volumes by manipulating stitch density.

### Key Terms & Abbreviations
- **MR (Magic Ring):** An adjustable loop used to start rounds without leaving a hole.
- **Sc (Single Crochet):** The standard stitch for amigurumi; dense and sturdy.
- **Inc (Increase):** Placing two stitches into one stitch from the previous round to expand the fabric.
- **Inv Dec (Invisible Decrease):** A technique that combines two stitches by using front loops only, minimizing holes and bulk.
- **Spiral Rounds:** Amigurumi is typically worked in a continuous spiral rather than joined rounds to avoid a visible seam.

---

## 2. The Mathematics of Shaping
The shape of a crochet piece is dictated by the rate and placement of increases and decreases.

### The Linear Circle Rule
To keep a circle flat, you must increase the number of stitches in each round by a constant amount (usually the number of stitches in the first round).
- **Round 1:** 6 sc (6)
- **Round 2:** 6 increases (12)
- **Round 3:** (1 sc, inc) x 6 (18)
- **Round 4:** (2 sc, inc) x 6 (24)
- **Logic:** $Stitches = 6 	imes RoundNumber$

### Spherical Geometry
A sphere is created in three phases:
1. **Expansion:** Evenly increasing until the desired diameter is reached.
2. **Maintenance:** Working "even" (no inc/dec) for several rounds to create height.
3. **Contraction:** Mirroring the expansion phase with even decreases.
- **Curvature Logic:** The number of stitches in a round on a sphere scales with $sin(	heta)$, where $	heta$ is the angle from the top of the sphere.

### Complex Shaping
- **Positive Curvature (Spheres/Cones):** Increase stitches slower than the linear circle rate.
- **Zero Curvature (Cylinders):** Work the same number of stitches per round.
- **Negative Curvature (Ruffles/Hyperbolic):** Increase stitches faster than the linear circle rate (e.g., doubling stitches every round).

---

## 3. Computational Logic for App Implementation
To build an app that converts photos to patterns, the following workflow is recommended:

### Phase A: Image Processing
1. **Edge Detection:** Extract the silhouette of the subject.
2. **Voxelization/3D Modeling:** Convert the 2D image into 3D primitive shapes (spheres, cylinders, cones).
3. **Simplification:** Reduce the character to its most basic geometric breakdown.

### Phase B: Pattern Generation
1. **Stitch Mapping:** Translate the 3D surface area into a series of stitches.
2. **Density Calculation:** Determine increase/decrease placement based on the curvature of the 3D model.
3. **Staggering:** Randomize increase/decrease placement slightly to prevent "cornering" (where stacked increases create a hexagonal shape instead of a circle).

### Phase C: Pattern Parsing
- Use a **Context-Free Grammar (CFG)** to ensure the generated pattern follows standard crochet notation.
- **Constraint:** Ensure the final stitch count of each round connects logically to the next.

---

## 4. Advanced Techniques for High-Fidelity
- **Stitch Ratio:** Note that a single crochet stitch is typically slightly wider than it is tall (approx. 1:0.8). Pattern algorithms must account for this aspect ratio to avoid "squashed" figures.
- **Color Mapping:** For "tapestry" style amigurumi, pixels in the photo must be mapped to specific stitches, accounting for the slight "lean" of crochet stitches in the round.

---
*Sources: Chalkdust Magazine (Mathematics of Crochet), Atomm & Amigurumio (Pattern Generation Tech), TinyCurl (Amigurumi Foundations).*
