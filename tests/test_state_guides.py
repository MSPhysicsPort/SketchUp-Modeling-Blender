"""T1: session state, VCB buffer, guides (plain interpreter)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon"))

from core.state import DrawingAxes, SessionState, VCBBuffer, get_session, reset_session  # noqa: E402
from data.guides import GuideSet  # noqa: E402


class TestVCBBuffer(unittest.TestCase):
    def test_feed_backspace_clear(self):
        buf = VCBBuffer()
        self.assertTrue(buf.is_empty)
        buf.feed("1")
        buf.feed("2")
        buf.feed(".")
        buf.feed("5")
        self.assertEqual(buf.text, "12.5")
        buf.backspace()
        self.assertEqual(buf.text, "12.")
        buf.clear()
        self.assertTrue(buf.is_empty)

    def test_commit_length(self):
        buf = VCBBuffer()
        buf.feed("1")
        buf.feed("0")
        buf.feed("0")
        result = buf.commit("length", default_unit="mm")
        self.assertAlmostEqual(result, 0.1)
        self.assertTrue(buf.is_empty)

    def test_commit_coordinate(self):
        buf = VCBBuffer()
        for char in "[1,2,3]":
            buf.feed(char)
        result = buf.commit("coordinate", default_unit="mm")
        self.assertEqual(result, (False, [0.001, 0.002, 0.003]))

    def test_commit_empty_is_none(self):
        self.assertIsNone(VCBBuffer().commit("length"))

    def test_commit_invalid_keeps_text(self):
        buf = VCBBuffer()
        buf.feed("x")
        buf.feed("y")
        buf.feed("z")
        with self.assertRaises(ValueError):
            buf.commit("length", default_unit="mm")
        self.assertEqual(buf.text, "xyz")


class TestDrawingAxes(unittest.TestCase):
    def test_default_world(self):
        axes = DrawingAxes()
        self.assertEqual(axes.origin, (0.0, 0.0, 0.0))
        self.assertEqual(axes.z, (0.0, 0.0, 1.0))

    def test_reset(self):
        axes = DrawingAxes(origin=(1, 2, 3), z=(0, 1, 0))
        axes.reset()
        self.assertEqual(axes.origin, (0.0, 0.0, 0.0))
        self.assertEqual(axes.z, (0.0, 0.0, 1.0))

    def test_as_axes(self):
        axes = DrawingAxes().as_axes()
        self.assertEqual(axes.x, (1.0, 0.0, 0.0))


class TestSessionState(unittest.TestCase):
    def test_singleton_and_reset(self):
        first = get_session()
        self.assertIs(get_session(), first)
        reset_session()
        self.assertIsNot(get_session(), first)
        reset_session()

    def test_defaults(self):
        state = SessionState()
        self.assertIsNone(state.from_point)
        self.assertIsNone(state.active_tool_id)
        self.assertFalse(state.lock.locked)
        self.assertTrue(state.vcb.is_empty)


class TestGuideSet(unittest.TestCase):
    def test_add_point_dedup(self):
        guides = GuideSet()
        guides.add_point((1, 2, 3))
        guides.add_point((1, 2, 3))
        self.assertEqual(len(guides.points), 1)

    def test_add_line_normalizes(self):
        guides = GuideSet()
        guides.add_line((0, 0, 0), (2, 0, 0))
        self.assertEqual(guides.lines[0][1], (1.0, 0.0, 0.0))

    def test_clear(self):
        guides = GuideSet()
        guides.add_point((0, 0, 0))
        guides.add_line((0, 0, 0), (0, 1, 0))
        guides.clear()
        self.assertEqual(guides.points, [])
        self.assertEqual(guides.lines, [])

    def test_remove_near(self):
        guides = GuideSet()
        guides.add_point((0, 0, 0))
        guides.add_point((5, 5, 5))
        guides.add_line((0, 0, 0), (1, 0, 0))
        removed = guides.remove_near((0.001, 0, 0), tolerance=0.01)
        self.assertEqual(removed, 2)
        self.assertEqual(len(guides.points), 1)
        self.assertEqual(guides.lines, [])

    def test_candidates(self):
        guides = GuideSet()
        guides.add_point((1, 2, 3))
        guides.add_line((0, 0, 0), (0, 0, 1))
        self.assertEqual(guides.point_candidates(), [("guide_point", (1, 2, 3))])
        self.assertEqual(len(guides.line_candidates()), 1)


if __name__ == "__main__":
    unittest.main()
