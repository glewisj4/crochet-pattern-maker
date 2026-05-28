"""Regression tests for specialized amigurumi primitive generators."""

from __future__ import annotations

import unittest

from photo_to_pattern.compiler.generators import (
    closed_capsule_profile,
    closed_ovoid_profile,
    curled_tapered_tail_profile,
    eccentric_oval_muzzle_profile,
    inset_ear_profiles,
    leaf_cloak_panel_rows,
)
from photo_to_pattern.geometric_math import GeometricConfig
from photo_to_pattern.part_generator.generator import generate_planned_part_pattern_map
from photo_to_pattern.planning.models import DesignPart, PlanningModel, PlanningOptions


class AdvancedPrimitiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = GeometricConfig()

    def test_closed_structural_profiles_do_not_end_at_widest_round(self):
        for profile in (
            closed_ovoid_profile(12, 36, self.config),
            closed_capsule_profile(14, 30, self.config),
        ):
            self.assertEqual(profile[-1], self.config.min_stitches)
            self.assertLess(profile[-1], max(profile))

    def test_specialized_detail_profiles_are_distinct(self):
        tail = curled_tapered_tail_profile(12, 30, self.config)
        outer_ear, inner_ear = inset_ear_profiles(10, 24, self.config)
        muzzle = eccentric_oval_muzzle_profile(8, 36, self.config)
        cloak = leaf_cloak_panel_rows(9, 42, self.config)

        self.assertEqual(tail[-1], self.config.min_stitches)
        self.assertGreater(len(outer_ear), len(inner_ear))
        self.assertGreater(max(outer_ear), max(inner_ear))
        self.assertLessEqual(max(muzzle), 24)
        self.assertEqual(cloak[-1], self.config.min_stitches)
        self.assertEqual(max(cloak), 42)

    def test_generated_body_and_limb_patterns_close_before_finish(self):
        model = PlanningModel(
            title="closure",
            options=PlanningOptions(),
            views=(),
            shape_guides=(),
            proportions=(),
            construction=(),
            parts=(
                DesignPart("Body", "ovoid", (0.6, 0.7, 0.5), (232, 126, 64), "root", "test", 0.95),
                DesignPart("Legs", "capsule", (0.45, 0.45, 0.30), (232, 126, 64), "lower body", "test", 0.95, category="Appendages"),
            ),
        )

        pattern_map = generate_planned_part_pattern_map(model, self.config)
        grouped: dict[str, list[int]] = {}
        for round_spec in pattern_map.rounds:
            grouped.setdefault(round_spec.primitive_id, []).append(round_spec.stitch_count)

        self.assertTrue(grouped)
        for counts in grouped.values():
            self.assertEqual(counts[-1], self.config.min_stitches)
            self.assertLess(counts[-1], max(counts))

    def test_generated_inset_ears_include_inner_panels(self):
        model = PlanningModel(
            title="ears",
            options=PlanningOptions(),
            views=(),
            shape_guides=(),
            proportions=(),
            construction=(),
            parts=(
                DesignPart("Ears", "inset_ear", (0.60, 0.60, 0.30), (232, 126, 64), "top head", "test", 0.95, category="Insets"),
            ),
        )

        pattern_map = generate_planned_part_pattern_map(model, self.config)
        ids = {round_spec.primitive_id for round_spec in pattern_map.rounds}

        self.assertIn("ears_1", ids)
        self.assertIn("ears_1_inner_inset", ids)
        self.assertIn("ears_2", ids)
        self.assertIn("ears_2_inner_inset", ids)


if __name__ == "__main__":
    unittest.main()
