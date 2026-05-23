import unittest

from photo_to_pattern.vision_voxelizer import ImageFrame, VisionVoxelizer


class VisionVoxelizerTests(unittest.TestCase):
    def test_process_frame_creates_overlap_aware_model(self):
        voxelizer = VisionVoxelizer()

        model = voxelizer.process_frame(
            ImageFrame(width=120, height=160, source="synthetic.png", pixels=None)
        )

        primitive_ids = {primitive.id for primitive in model.primitives}
        self.assertIn("head", primitive_ids)
        self.assertIn("torso", primitive_ids)
        self.assertIn("left_limb_candidate", primitive_ids)
        self.assertIn("right_limb_candidate", primitive_ids)
        self.assertTrue(model.occlusions)
        self.assertIsNotNone(model.symmetry_axis)

    def test_narrow_silhouette_does_not_force_overlap_flag(self):
        voxelizer = VisionVoxelizer()

        model = voxelizer.process_frame(
            ImageFrame(width=50, height=160, source="synthetic.png", pixels=None)
        )

        overlap_flags = [item for item in model.occlusions if item.kind == "overlap"]
        self.assertEqual(overlap_flags, [])


if __name__ == "__main__":
    unittest.main()

