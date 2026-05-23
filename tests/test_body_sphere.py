import unittest

from photo_to_pattern.body_sphere import generate_body_sphere_from_dimensions


class BodySphereTests(unittest.TestCase):
    def test_generates_body_sphere_pattern(self):
        result = generate_body_sphere_from_dimensions(140, 180, title="Body Test")
        rendered = result.render()

        self.assertIn("Body Test", rendered)
        self.assertIn("Body Sphere", rendered)
        self.assertIn("MR", rendered)
        self.assertEqual(result.model.primitives[0].id, "body_sphere")


if __name__ == "__main__":
    unittest.main()

