import unittest

from photo_to_pattern.geometric_math import GeometricPatternGenerator
from photo_to_pattern.vision_voxelizer import Primitive3D, Vec3, VoxelModel


class GeometricPatternTests(unittest.TestCase):
    def test_sphere_rounds_have_bounded_deltas_and_staggering(self):
        model = VoxelModel(
            primitives=(
                Primitive3D(
                    id="sphere",
                    kind="sphere",
                    center=Vec3(0, 0, 0),
                    radius_x=32,
                    radius_y=32,
                    radius_z=32,
                ),
            )
        )

        pattern_map = GeometricPatternGenerator().generate(model)

        self.assertTrue(pattern_map.rounds)
        for round_spec in pattern_map.rounds[1:]:
            self.assertLessEqual(abs(round_spec.delta), 6)
            if round_spec.action in {"inc", "dec"}:
                self.assertTrue(round_spec.placements)


if __name__ == "__main__":
    unittest.main()

