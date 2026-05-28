"""Regression tests for yarn material physics and yardage estimation."""

from __future__ import annotations

import unittest

from photo_to_pattern.core.yarn_physics import YarnDynamicsEngine, estimate_yardage_by_color, structural_stitch_length_mm, yarn_profile
from photo_to_pattern.geometric_math import PatternMap, RoundSpec


class YarnPhysicsTests(unittest.TestCase):
    def test_yarn_profile_material_bounds(self):
        cotton = yarn_profile(weight=4, hook_mm=3.5, fiber="cotton", color_hex="ffffff")
        chenille = yarn_profile(weight=6, hook_mm=6.0, fiber="chenille", color_hex="#ff8800")

        self.assertEqual(cotton.color_hex, "#ffffff")
        self.assertLess(cotton.elasticity, chenille.elasticity)
        self.assertGreater(cotton.spring_coefficient, chenille.spring_coefficient)
        self.assertGreater(structural_stitch_length_mm(chenille), structural_stitch_length_mm(cotton))

    def test_estimates_yardage_by_color_profile(self):
        rounds = (
            RoundSpec("head", 1, 6, 0, 6, "mr", "start", (), 6),
            RoundSpec("head", 2, 12, 6, 6, "inc", "increase", (1, 3, 5, 7, 9, 11), 12),
            RoundSpec("cloak", 1, 20, 0, 20, "mr", "start", (), 20),
        )
        pattern_map = PatternMap(rounds=rounds)
        default = yarn_profile(weight=4, hook_mm=3.5, fiber="acrylic", color_hex="#e87e40")
        green = yarn_profile(weight=3, hook_mm=3.0, fiber="cotton", color_hex="#568b4b")

        estimates = estimate_yardage_by_color(
            pattern_map,
            default_profile=default,
            color_profiles={"#568b4b": green},
            part_colors={"head": "#e87e40", "cloak": "#568b4b"},
        )

        by_color = {item.color_hex: item for item in estimates}
        self.assertEqual(by_color["#e87e40"].stitches, 18)
        self.assertEqual(by_color["#568b4b"].stitches, 20)
        self.assertGreater(by_color["#e87e40"].yards, 0)
        self.assertGreater(by_color["#568b4b"].meters, 0)

    def test_engine_facade_matches_functional_api(self):
        engine = YarnDynamicsEngine()
        profile = engine.profile(weight=4, hook_mm=3.5, fiber="acrylic", color_hex="#e87e40")
        self.assertEqual(engine.stitch_length_mm(profile), structural_stitch_length_mm(profile))


if __name__ == "__main__":
    unittest.main()
