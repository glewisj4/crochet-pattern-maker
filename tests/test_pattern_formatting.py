import unittest
from photo_to_pattern.geometric_math import PatternMap, RoundSpec
from photo_to_pattern.planning.models import PlanningModel, PlanningOptions, DesignPart
from photo_to_pattern.pattern_linguist.formatter import PatternFormatter, _clean_name, find_closest_part


class PatternFormattingTests(unittest.TestCase):
    def test_name_cleaning(self):
        self.assertEqual(_clean_name("head"), "head")
        self.assertEqual(_clean_name("Ears_1"), "ear")
        self.assertEqual(_clean_name("leg_1_1"), "leg")
        self.assertEqual(_clean_name("body"), "torso")
        self.assertEqual(_clean_name("Torso"), "torso")
        self.assertEqual(_clean_name("Legs"), "leg")

    def test_find_closest_part(self):
        parts = [
            DesignPart("Head", "sphere", (1, 1, 1), None, "neck", "source", 1.0, yarn_type="cotton"),
            DesignPart("Torso", "cylinder", (1, 1, 1), None, "none", "source", 1.0, yarn_type="wool"),
            DesignPart("Ears", "sphere", (1, 1, 1), None, "head", "source", 1.0, yarn_type="acrylic"),
        ]
        self.assertEqual(find_closest_part("head", parts).name, "Head")
        self.assertEqual(find_closest_part("ears_1", parts).name, "Ears")
        self.assertEqual(find_closest_part("body", parts).name, "Torso")
        self.assertEqual(find_closest_part("torso", parts).name, "Torso")
        self.assertIsNone(find_closest_part("unrelated_part", parts))

    def test_yarn_yardage_math_and_grouping(self):
        parts = (
            DesignPart("Head", "sphere", (1, 1, 1), None, "neck", "source", 1.0, yarn_type="cotton", color_hex="#e87e40"),
            DesignPart("Torso", "cylinder", (1, 1, 1), None, "none", "source", 1.0, yarn_type="cotton", color_hex="#ffffff"),
            DesignPart("Arms", "cylinder", (1, 1, 1), None, "body", "source", 1.0, yarn_type="acrylic", color_hex="#000000"),
            DesignPart("Legs", "cylinder", (1, 1, 1), None, "body", "source", 1.0, yarn_type="acrylic", color_hex="#000000"),
            DesignPart("Tail", "cylinder", (1, 1, 1), None, "body", "source", 1.0, yarn_type="wool", color_hex="#ff0000"),
            DesignPart("Ears", "sphere", (1, 1, 1), None, "head", "source", 1.0, yarn_type="velvet/chenille", color_hex="#abc123"),
        )
        options = PlanningOptions(target_height_inches=8.0)
        planning_model = PlanningModel("Test Model", options, (), (), (), (), parts)

        # 30 stitches for head: cotton (2.6 inches) -> (30 * 2.6 * 1.2) / 36.0 = 2.6 yards of Cotton (Orange)
        # 10 stitches for body/torso: cotton (2.6 inches) -> (10 * 2.6 * 1.2) / 36.0 = 0.866... yards of Cotton (White)
        # 15 stitches for arm: acrylic (3.0 inches) -> (15 * 3.0 * 1.2) / 36 = 1.5 yards
        # 15 stitches for leg: acrylic (3.0) -> 1.5 yards. Both arm and leg map to Acrylic Yarn (Black), total 3.0 yards
        # 20 stitches for tail: wool (3.2 inches) -> (20 * 3.2 * 1.2) / 36 = 2.133... yards of Wool (Red)
        # 10 stitches for ears: velvet/chenille (4.5 inches) -> (10 * 4.5 * 1.2) / 36 = 1.5 yards of Velvet/Chenille (#abc123)

        rounds = (
            RoundSpec("head", 1, 10, 0, 10, "mr", "start", (), 1.0),
            RoundSpec("head", 2, 20, 10, 10, "inc", "increase", (), 2.0),
            RoundSpec("torso", 1, 10, 0, 10, "mr", "start", (), 1.0),
            RoundSpec("arms_1", 1, 15, 0, 15, "mr", "start", (), 1.0),
            RoundSpec("legs_1", 1, 15, 0, 15, "mr", "start", (), 1.0),
            RoundSpec("tail", 1, 20, 0, 20, "mr", "start", (), 1.0),
            RoundSpec("ears_1", 1, 10, 0, 10, "mr", "start", (), 1.0),
        )
        pattern_map = PatternMap(rounds)

        formatter = PatternFormatter()
        pattern = formatter.format(pattern_map, planning_model=planning_model)

        # Check that Yarn & Materials Requirements section exists
        materials_sec = next((s for s in pattern.sections if s.title == "Yarn & Materials Requirements"), None)
        self.assertIsNotNone(materials_sec)

        # Verify grouped yarn yardage strings come from the yarn dynamics engine.
        lines = list(materials_sec.lines)
        self.assertTrue(any(line.startswith("Cotton Yarn (Orange): ~") for line in lines))
        self.assertTrue(any(line.startswith("Cotton Yarn (White): ~") for line in lines))
        self.assertTrue(any(line.startswith("Acrylic Yarn (Black): ~") for line in lines))
        self.assertTrue(any(line.startswith("Wool Yarn (Red): ~") for line in lines))
        self.assertTrue(any(line.startswith("Velvet/Chenille Yarn (#abc123): ~") for line in lines))

    def test_hook_size_selection(self):
        formatter = PatternFormatter()
        rounds = (RoundSpec("torso", 1, 10, 0, 10, "mr", "start", (), 1.0),)
        pattern_map = PatternMap(rounds)

        yarn_types = ["cotton", "acrylic", "wool", "velvet/chenille", "unknown_yarn"]
        expected_hooks = {
            "cotton": "2.25 mm (US B-1) to 2.75 mm (US C-2)",
            "acrylic": "3.25 mm (US D-3) to 3.75 mm (US F-5)",
            "wool": "3.5 mm (US E-4) to 4.0 mm (US G-6)",
            "velvet/chenille": "5.0 mm (US H-8) to 6.0 mm (US J-10)",
            "unknown_yarn": "3.25 mm (US D-3) to 3.75 mm (US F-5)",
        }

        for ytype in yarn_types:
            parts = (DesignPart("Torso", "cylinder", (1, 1, 1), None, "none", "source", 1.0, yarn_type=ytype),)
            options = PlanningOptions(target_height_inches=8.0)
            planning_model = PlanningModel("Test Hook", options, (), (), (), (), parts)

            pattern = formatter.format(pattern_map, planning_model=planning_model)
            materials_sec = next((s for s in pattern.sections if s.title == "Yarn & Materials Requirements"), None)
            self.assertIsNotNone(materials_sec)
            self.assertIn(f"Crochet Hook: {expected_hooks[ytype]}", materials_sec.lines)

    def test_safety_eye_mm_size_calculation(self):
        formatter = PatternFormatter()
        rounds = (RoundSpec("head", 1, 10, 0, 10, "mr", "start", (), 1.0),)
        pattern_map = PatternMap(rounds)

        # target_height = 8.0 -> max(6, min(24, round(8.0 * 1.5))) = 12
        parts = (DesignPart("Head", "sphere", (1, 1, 1), None, "neck", "source", 1.0),)
        options = PlanningOptions(target_height_inches=8.0, infant_safe=False)
        planning_model = PlanningModel("Test Eyes", options, (), (), (), (), parts)
        pattern = formatter.format(pattern_map, planning_model=planning_model)
        materials_sec = next((s for s in pattern.sections if s.title == "Yarn & Materials Requirements"), None)
        self.assertIn("Safety eyes: 12 mm", materials_sec.lines)

        # target_height = 3.0 -> round(4.5) = 4 -> min/max capped to 6
        options = PlanningOptions(target_height_inches=3.0, infant_safe=False)
        planning_model = PlanningModel("Test Eyes Small", options, (), (), (), (), parts)
        pattern = formatter.format(pattern_map, planning_model=planning_model)
        materials_sec = next((s for s in pattern.sections if s.title == "Yarn & Materials Requirements"), None)
        self.assertIn("Safety eyes: 6 mm", materials_sec.lines)

        # target_height = 20.0 -> round(30.0) = 30 -> capped to 24
        options = PlanningOptions(target_height_inches=20.0, infant_safe=False)
        planning_model = PlanningModel("Test Eyes Large", options, (), (), (), (), parts)
        pattern = formatter.format(pattern_map, planning_model=planning_model)
        materials_sec = next((s for s in pattern.sections if s.title == "Yarn & Materials Requirements"), None)
        self.assertIn("Safety eyes: 24 mm", materials_sec.lines)

        # infant_safe = True warning check
        options = PlanningOptions(target_height_inches=8.0, infant_safe=True)
        planning_model = PlanningModel("Test Eyes Safe", options, (), (), (), (), parts)
        pattern = formatter.format(pattern_map, planning_model=planning_model)
        materials_sec = next((s for s in pattern.sections if s.title == "Yarn & Materials Requirements"), None)
        expected_warning = "Safety eyes: 12 mm (Choking hazard: Since Child Safety Mode is enabled, replace plastic eyes with embroidered eyes or soft felt circles!)"
        self.assertIn(expected_warning, materials_sec.lines)

    def test_presence_of_sections(self):
        formatter = PatternFormatter()
        rounds = (
            RoundSpec("head", 1, 10, 0, 10, "mr", "start", (), 1.0),
            RoundSpec("head", 2, 20, 10, 10, "inc", "increase", (), 2.0),
        )
        pattern_map = PatternMap(rounds)

        # Case 1: planning_model is None
        pattern = formatter.format(pattern_map, planning_model=None)
        titles = [s.title for s in pattern.sections]
        self.assertNotIn("Yarn & Materials Requirements", titles)
        self.assertNotIn("Stitch Abbreviations Key", titles)
        self.assertNotIn("Assembly & Sewing Instructions", titles)

        # Case 2: planning_model is provided
        parts = (DesignPart("Head", "sphere", (1, 1, 1), None, "neck", "source", 1.0),)
        options = PlanningOptions(target_height_inches=8.0)
        planning_model = PlanningModel("Test Sections", options, (), (), (), (), parts)
        pattern = formatter.format(pattern_map, planning_model=planning_model)
        titles = [s.title for s in pattern.sections]
        self.assertIn("Yarn & Materials Requirements", titles)
        self.assertIn("Stitch Abbreviations Key", titles)
        self.assertIn("Assembly & Sewing Instructions", titles)

        # Check Assembly & Sewing Instructions contents
        assembly_sec = next((s for s in pattern.sections if s.title == "Assembly & Sewing Instructions"), None)
        self.assertIsNotNone(assembly_sec)
        # N = 2 head rounds -> 2 * 0.6 = 1.2 -> mid = 1 -> round_a = 1, round_b = 2
        self.assertIn("2. Eye Placement: Place safety eyes between Rounds 1 and 2 (about 60% down the Head), about 8 stitches apart. (To compensate for the 3.5-degree spiral drift factor, shift the left eye backward by 1 stitch index to remain perfectly anatomically centered.)", assembly_sec.lines)


if __name__ == "__main__":
    unittest.main()
