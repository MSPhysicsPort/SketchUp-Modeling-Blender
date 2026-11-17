"""T1: inference geometry layer (plain interpreter, no Blender)."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon"))

from core.inference import (  # noqa: E402
    WORLD_AXES,
    InferenceResult,
    LockState,
    closest_point_on_segment,
    dist_point_to_segment_2d,
    evaluate,
    find_intersections,
    project_point_on_line,
    project_point_on_plane,
    ray_plane,
    ray_segment_closest,
    ray_triangle,
    segment_segment_closest,
    segments_intersect_2d,
)


def approx(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


class TestPrimitives(unittest.TestCase):
    def test_closest_point_interior(self):
        point, t, dist = closest_point_on_segment((1, 1, 0), (0, 0, 0), (2, 0, 0))
        self.assertTrue(approx(point, (1, 0, 0)))
        self.assertAlmostEqual(t, 0.5)
        self.assertAlmostEqual(dist, 1.0)

    def test_closest_point_clamped(self):
        point, t, _ = closest_point_on_segment((5, 0, 0), (0, 0, 0), (2, 0, 0))
        self.assertTrue(approx(point, (2, 0, 0)))
        self.assertAlmostEqual(t, 1.0)

    def test_closest_point_degenerate(self):
        point, t, dist = closest_point_on_segment((1, 0, 0), (0, 0, 0), (0, 0, 0))
        self.assertTrue(approx(point, (0, 0, 0)))
        self.assertAlmostEqual(dist, 1.0)

    def test_ray_segment_crossing(self):
        _, _, dist, _, seg = ray_segment_closest(
            (0, 0, 5), (0, 0, -1), (-1, 0, 0), (1, 0, 0)
        )
        self.assertAlmostEqual(dist, 0.0)
        self.assertTrue(approx(seg, (0, 0, 0)))

    def test_ray_segment_parallel(self):
        _, seg_t, dist, _, _ = ray_segment_closest(
            (0, 1, 0), (1, 0, 0), (0, 0, 0), (2, 0, 0)
        )
        self.assertAlmostEqual(dist, 1.0)
        self.assertAlmostEqual(seg_t, 0.0)

    def test_ray_segment_behind(self):
        ray_t, _, _, ray_pt, _ = ray_segment_closest(
            (0, 0, 5), (0, 0, 1), (-1, 0, 0), (1, 0, 0)
        )
        self.assertAlmostEqual(ray_t, 0.0)
        self.assertTrue(approx(ray_pt, (0, 0, 5)))

    def test_segment_segment_crossing(self):
        _, _, dist, _, _ = segment_segment_closest(
            (-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0)
        )
        self.assertAlmostEqual(dist, 0.0)

    def test_segment_segment_skew(self):
        _, _, dist, _, _ = segment_segment_closest(
            (-1, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 1)
        )
        self.assertAlmostEqual(dist, 1.0)

    def test_ray_triangle_hit(self):
        t = ray_triangle(
            (0.2, 0.2, 5), (0, 0, -1), (0, 0, 0), (1, 0, 0), (0, 1, 0)
        )
        self.assertAlmostEqual(t, 5.0)

    def test_ray_triangle_miss(self):
        self.assertIsNone(
            ray_triangle((2, 2, 5), (0, 0, -1), (0, 0, 0), (1, 0, 0), (0, 1, 0))
        )

    def test_ray_triangle_parallel(self):
        self.assertIsNone(
            ray_triangle((0, 0, 5), (1, 0, 0), (0, 0, 0), (1, 0, 0), (0, 1, 0))
        )

    def test_project_line_plane(self):
        self.assertTrue(
            approx(project_point_on_line((1, 2, 3), (0, 0, 0), (1, 0, 0)), (1, 0, 0))
        )
        self.assertTrue(
            approx(project_point_on_plane((1, 2, 3), (0, 0, 0), (0, 0, 1)), (1, 2, 0))
        )

    def test_ray_plane(self):
        self.assertTrue(
            approx(ray_plane((0, 0, 5), (0, 0, -1), (0, 0, 0), (0, 0, 1)), (0, 0, 0))
        )
        self.assertIsNone(ray_plane((0, 0, 5), (1, 0, 0), (0, 0, 0), (0, 0, 1)))

    def test_dist_2d(self):
        self.assertAlmostEqual(dist_point_to_segment_2d(1, 1, 0, 0, 2, 0), 1.0)
        self.assertAlmostEqual(dist_point_to_segment_2d(5, 0, 0, 0, 2, 0), 3.0)

    def test_segments_intersect_2d(self):
        hit = segments_intersect_2d((0, 0), (2, 2), (0, 2), (2, 0))
        self.assertIsNotNone(hit)
        self.assertAlmostEqual(hit[0], 1.0)
        self.assertAlmostEqual(hit[1], 1.0)
        self.assertIsNone(segments_intersect_2d((0, 0), (1, 0), (0, 1), (1, 1)))
        self.assertIsNone(segments_intersect_2d((0, 0), (2, 0), (3, 0), (4, 0)))


class TestLockState(unittest.TestCase):
    def test_arrow_toggle(self):
        lock = LockState()
        lock.press_arrow(0, (1, 2, 3))
        self.assertTrue(lock.locked)
        self.assertEqual(lock.mode, "axis")
        lock.press_arrow(0, (1, 2, 3))
        self.assertFalse(lock.locked)

    def test_arrow_switch(self):
        lock = LockState()
        lock.press_arrow(0, (0, 0, 0))
        lock.press_arrow(2, (0, 0, 0))
        self.assertEqual(lock.axis_index, 2)

    def test_shift_press_release(self):
        lock = LockState()
        lock.press_shift((1, 0, 0), (0, 0, 0))
        self.assertEqual(lock.mode, "direction")
        lock.release_shift()
        self.assertFalse(lock.locked)

    def test_shift_zero_direction_ignored(self):
        lock = LockState()
        lock.press_shift((0, 0, 0), (0, 0, 0))
        self.assertFalse(lock.locked)

    def test_alt_cycle(self):
        lock = LockState()
        self.assertEqual(lock.line_mode, "all_on")
        lock.press_alt_line()
        self.assertEqual(lock.line_mode, "all_off")
        lock.press_alt_line()
        self.assertEqual(lock.line_mode, "parallel_perp")
        lock.press_alt_line()
        self.assertEqual(lock.line_mode, "all_on")

    def test_apply_axis(self):
        lock = LockState()
        lock.press_arrow(2, (1, 1, 0))
        self.assertTrue(approx(lock.apply((5, 5, 5)), (1, 1, 5)))

    def test_apply_direction(self):
        lock = LockState()
        lock.press_shift((1, 1, 0), (0, 0, 0))
        self.assertTrue(approx(lock.apply((2, 0, 0)), (1, 1, 0)))

    def test_apply_plane(self):
        lock = LockState()
        lock.set_plane((0, 0, 1), (0, 0, 2))
        self.assertTrue(approx(lock.apply((1, 2, 5)), (1, 2, 2)))

    def test_distance_to_lock(self):
        lock = LockState()
        lock.press_arrow(0, (0, 0, 0))
        self.assertAlmostEqual(lock.distance_to_lock((5, 3, 0)), 3.0)
        self.assertAlmostEqual(lock.distance_to_lock((5, 0, 0)), 0.0)

    def test_label_color(self):
        lock = LockState()
        lock.press_arrow(1, (0, 0, 0))
        self.assertEqual(lock.label, "On Green Axis")
        self.assertEqual(lock.color, (0.0, 0.8, 0.0, 1.0))


class TestEvaluate(unittest.TestCase):
    RAY = ((0, 0, 5), (0, 0, -1))

    def test_endpoint_beats_midpoint_same_spot(self):
        result = evaluate(
            *self.RAY,
            mouse_xy=(100, 100),
            points=[
                ("midpoint", (1, 0, 0), (100, 100)),
                ("endpoint", (1, 0, 0), (100, 100)),
            ],
        )
        self.assertEqual(result.kind, "endpoint")

    def test_nearest_point_wins(self):
        result = evaluate(
            *self.RAY,
            mouse_xy=(100, 100),
            points=[
                ("endpoint", (1, 0, 0), (105, 100)),
                ("midpoint", (0, 0, 0), (101, 100)),
            ],
        )
        self.assertEqual(result.kind, "midpoint")

    def test_tolerance_cutoff(self):
        result = evaluate(
            *self.RAY,
            mouse_xy=(100, 100),
            points=[("endpoint", (1, 0, 0), (200, 200))],
            pixel_tolerance=12.0,
        )
        self.assertEqual(result.kind, "free")

    def test_on_edge(self):
        result = evaluate(
            *self.RAY,
            mouse_xy=(100, 100),
            edges=[((-1, 0, 0), (1, 0, 0), (90, 100), (110, 100))],
        )
        self.assertEqual(result.kind, "on_edge")
        self.assertTrue(approx(result.point, (0, 0, 0)))

    def test_on_face_fallback(self):
        result = evaluate(
            *self.RAY,
            mouse_xy=(100, 100),
            face_hit=((0.5, 0.5, 0), (0, 0, 1), 0),
        )
        self.assertEqual(result.kind, "on_face")
        self.assertTrue(approx(result.point, (0.5, 0.5, 0)))

    def test_free_ground_plane(self):
        result = evaluate(*self.RAY, mouse_xy=(100, 100))
        self.assertEqual(result.kind, "free")
        self.assertTrue(approx(result.point, (0, 0, 0)))

    def test_axis_snap_from_start(self):
        result = evaluate(
            *self.RAY,
            mouse_xy=(100, 100),
            face_hit=((2.0, 0.05, 0), (0, 0, 1), 0),
            start_point=(0, 0, 0),
        )
        self.assertEqual(result.kind, "axis")
        self.assertEqual(result.axis_index, 0)
        self.assertTrue(approx(result.point, (2.0, 0.0, 0)))
        self.assertEqual(result.label, "On Red Axis")

    def test_axis_snap_angle_cutoff(self):
        result = evaluate(
            *self.RAY,
            mouse_xy=(100, 100),
            face_hit=((1.0, 1.0, 0), (0, 0, 1), 0),
            start_point=(0, 0, 0),
        )
        self.assertEqual(result.kind, "on_face")

    def test_from_point_beats_start(self):
        result = evaluate(
            *self.RAY,
            mouse_xy=(100, 100),
            face_hit=((0.05, 3.0, 0), (0, 0, 1), 0),
            start_point=(0, 0, 0),
            from_point=(0, 0, 0),
        )
        self.assertEqual(result.kind, "from_point")
        self.assertEqual(result.axis_index, 1)

    def test_line_mode_off_disables_linear(self):
        lock = LockState()
        lock.press_alt_line()
        self.assertEqual(lock.line_mode, "all_off")
        result = evaluate(
            *self.RAY,
            mouse_xy=(100, 100),
            face_hit=((2.0, 0.05, 0), (0, 0, 1), 0),
            start_point=(0, 0, 0),
            lock=lock,
        )
        self.assertEqual(result.kind, "on_face")

    def test_locked_point_off_line_ignored(self):
        lock = LockState()
        lock.press_arrow(0, (0, 0, 0))
        result = evaluate(
            *self.RAY,
            mouse_xy=(100, 100),
            points=[("endpoint", (0, 5, 0), (100, 100))],
            face_hit=((3, 0, 0), (0, 0, 1), 0),
            lock=lock,
        )
        self.assertEqual(result.kind, "free")
        self.assertTrue(approx(result.point, (3, 0, 0)))

    def test_locked_point_on_line_kept(self):
        lock = LockState()
        lock.press_arrow(0, (0, 0, 0))
        result = evaluate(
            *self.RAY,
            mouse_xy=(100, 100),
            points=[("endpoint", (3, 0, 0), (100, 100))],
            lock=lock,
        )
        self.assertEqual(result.kind, "endpoint")

    def test_guide_line(self):
        result = evaluate(
            *self.RAY,
            mouse_xy=(100, 100),
            guide_lines=[((0, 0, 0), (1, 0, 0), (90, 100), (110, 100))],
        )
        self.assertEqual(result.kind, "on_line")

    def test_result_repr(self):
        self.assertIn("endpoint", repr(InferenceResult("endpoint", (0, 0, 0))))


class TestFindIntersections(unittest.TestCase):
    def test_crossing_found(self):
        found = find_intersections(
            [
                ((-1, 0, 0), (1, 0, 0), (90, 100), (110, 100)),
                ((0, -1, 0), (0, 1, 0), (100, 90), (100, 110)),
            ],
            (100, 100),
            12.0,
        )
        self.assertEqual(len(found), 1)
        self.assertTrue(approx(found[0], (0, 0, 0), tol=1e-6))

    def test_skew_excluded(self):
        found = find_intersections(
            [
                ((-1, 0, 0), (1, 0, 0), (90, 100), (110, 100)),
                ((0, -1, 1), (0, 1, 1), (100, 90), (100, 110)),
            ],
            (100, 100),
            12.0,
        )
        self.assertEqual(found, [])

    def test_far_crossing_excluded(self):
        found = find_intersections(
            [
                ((-1, 0, 0), (1, 0, 0), (90, 100), (110, 100)),
                ((0, -1, 0), (0, 1, 0), (100, 90), (100, 110)),
            ],
            (300, 300),
            12.0,
        )
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
