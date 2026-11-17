"""T1: curve plane math (core/curves.py, pure, no bpy)."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon", "core"))

import curves  # noqa: E402


class TestPlaneMath(unittest.TestCase):
    def test_plane_basis_orthonormal(self):
        for normal in ((0, 0, 1), (1, 0, 0), (0, 1, 0), (1, 1, 1)):
            u, v = curves.plane_basis(normal)
            self.assertAlmostEqual(sum(a * b for a, b in zip(u, v)), 0.0)
            self.assertAlmostEqual(math.sqrt(sum(a * a for a in u)), 1.0)
            self.assertAlmostEqual(math.sqrt(sum(a * a for a in v)), 1.0)

    def test_to_from_plane_roundtrip(self):
        origin = (1.0, 2.0, 3.0)
        for normal in ((0, 0, 1), (1, 0, 0), (0.2, 0.3, 0.9)):
            for point in ((1.0, 2.0, 3.0), (4.0, -1.0, 0.5), (0.0, 0.0, 0.0)):
                projected = curves.project_on_plane(point, origin, normal)
                uv = curves.to_plane(projected, origin, normal)
                back = curves.from_plane(uv, origin, normal)
                for a, b in zip(projected, back):
                    self.assertAlmostEqual(a, b, places=9)

    def test_angle_in_plane(self):
        center = (0.0, 0.0, 0.0)
        normal = (0, 0, 1)
        self.assertAlmostEqual(curves.angle_in_plane((1, 0, 0), center, normal), 0.0)
        self.assertAlmostEqual(curves.angle_in_plane((0, 1, 0), center, normal), 90.0)
        self.assertAlmostEqual(curves.angle_in_plane((-1, 0, 0), center, normal), 180.0)
        self.assertAlmostEqual(curves.angle_in_plane((0, -1, 0), center, normal), 270.0)

    def test_circle_points(self):
        pts = curves.circle_points((0, 0, 0), (0, 0, 1), 2.0, 12)
        self.assertEqual(len(pts), 12)
        for point in pts:
            self.assertAlmostEqual(math.hypot(point[0], point[1]), 2.0)
            self.assertAlmostEqual(point[2], 0.0)

    def test_arc_points_endpoints(self):
        pts = curves.arc_points((0, 0, 0), (0, 0, 1), 1.0, 0.0, 90.0, 6)
        self.assertEqual(len(pts), 7)
        self.assertAlmostEqual(pts[0][0], 1.0)
        self.assertAlmostEqual(pts[0][1], 0.0)
        self.assertAlmostEqual(pts[-1][0], 0.0, places=9)
        self.assertAlmostEqual(pts[-1][1], 1.0)

    def test_arc_from_three_points(self):
        solved = curves.arc_from_three_points((1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, 0, 1))
        self.assertIsNotNone(solved)
        center, radius = solved
        for coord in center:
            self.assertAlmostEqual(coord, 0.0)
        self.assertAlmostEqual(radius, 1.0)
        self.assertIsNone(
            curves.arc_from_three_points((0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 0, 1))
        )

    def test_bulge_radius_roundtrip(self):
        chord = 2.0
        for bulge in (0.1, 0.5, 1.0):
            radius = curves.arc_bulge_to_radius(chord, bulge)
            self.assertAlmostEqual(curves.arc_radius_to_bulge(chord, radius), bulge)
        self.assertIsNone(curves.arc_radius_to_bulge(2.0, 0.5))

    def test_segments_for_circle_segments(self):
        self.assertEqual(curves.segments_for_circle_segments(24, 90.0), 6)
        self.assertEqual(curves.segments_for_circle_segments(20, 180.0), 10)
        self.assertEqual(curves.segments_for_circle_segments(24, 360.0), 24)


if __name__ == "__main__":
    unittest.main()
