"""T1 pure-logic unit tests: VCB parsing + unit conversion.

Runs with a plain interpreter, no Blender (proposal §5.9).
Usage: python3 tests/test_vcb_units.py
"""

import math
import sys
import unittest
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parent.parent / "addon" / "core"
sys.path.insert(0, str(CORE_DIR))

import units  # noqa: E402
import vcb  # noqa: E402


class TestParseLength(unittest.TestCase):
    def test_bare_number_uses_default_unit(self):
        self.assertAlmostEqual(vcb.parse_length("100"), 0.1, places=9)
        self.assertAlmostEqual(vcb.parse_length("100", "m"), 100.0, places=9)

    def test_unit_suffixes(self):
        self.assertAlmostEqual(vcb.parse_length("15cm"), 0.15, places=9)
        self.assertAlmostEqual(vcb.parse_length("6in"), 0.1524, places=9)
        self.assertAlmostEqual(vcb.parse_length("10m"), 10.0, places=9)
        self.assertAlmostEqual(vcb.parse_length("1yd"), 0.9144, places=9)
        self.assertAlmostEqual(vcb.parse_length("2.5CM"), 0.025, places=9)
        self.assertAlmostEqual(vcb.parse_length("34 cm"), 0.34, places=9)

    def test_inch_mark(self):
        self.assertAlmostEqual(vcb.parse_length('6"'), 0.1524, places=9)
        self.assertAlmostEqual(vcb.parse_length('6 1/2"'), 0.1651, places=9)

    def test_feet_inches(self):
        self.assertAlmostEqual(vcb.parse_length("6'"), 1.8288, places=9)
        self.assertAlmostEqual(vcb.parse_length("6'8\""), 2.032, places=9)
        self.assertAlmostEqual(
            vcb.parse_length("6' 8 7/8\""), 6 * 0.3048 + 8.875 * 0.0254, places=9
        )
        self.assertAlmostEqual(vcb.parse_length("8'"), 2.4384, places=9)

    def test_fractions(self):
        self.assertAlmostEqual(vcb.parse_length("1/2"), 0.0005, places=9)
        self.assertAlmostEqual(vcb.parse_length("1 1/2in"), 0.0381, places=9)
        self.assertAlmostEqual(vcb.parse_length("3/4"), 0.00075, places=9)

    def test_negative(self):
        self.assertAlmostEqual(vcb.parse_length("-35mm"), -0.035, places=9)
        self.assertAlmostEqual(vcb.parse_length("-3'6\""), -1.0668, places=9)

    def test_zero(self):
        self.assertAlmostEqual(vcb.parse_length("0"), 0.0, places=9)

    def test_errors(self):
        for bad in ("", "abc", "10 parsecs", "1/0", "mm", "6''", "1.2.3"):
            with self.assertRaises(ValueError, msg=bad):
                vcb.parse_length(bad)


class TestParseLengthList(unittest.TestCase):
    def test_two_values(self):
        self.assertEqual(
            [round(v, 9) if v is not None else None for v in vcb.parse_length_list("8',20'")],
            [2.4384, 6.096],
        )

    def test_empty_slot_means_unchanged(self):
        self.assertEqual(
            [round(v, 9) if v is not None else None for v in vcb.parse_length_list("3',")],
            [0.9144, None],
        )
        self.assertEqual(
            [round(v, 9) if v is not None else None for v in vcb.parse_length_list(",3'")],
            [None, 0.9144],
        )

    def test_semicolon_separator(self):
        self.assertEqual(
            [round(v, 9) for v in vcb.parse_length_list("1;2")], [0.001, 0.002]
        )


class TestParseAngle(unittest.TestCase):
    def test_degrees(self):
        self.assertAlmostEqual(vcb.parse_angle("34.1"), 34.1, places=9)
        self.assertAlmostEqual(vcb.parse_angle("45°"), 45.0, places=9)
        self.assertAlmostEqual(vcb.parse_angle("-30"), -30.0, places=9)

    def test_slope(self):
        self.assertAlmostEqual(
            vcb.parse_angle("8:12"), math.degrees(math.atan2(8, 12)), places=9
        )


class TestParseCount(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(vcb.parse_count("24"), 24)
        self.assertEqual(vcb.parse_count("24s"), 24)
        self.assertEqual(vcb.parse_count("24S"), 24)

    def test_errors(self):
        for bad in ("2.5", "abc", ""):
            with self.assertRaises(ValueError, msg=bad):
                vcb.parse_count(bad)


class TestParseArray(unittest.TestCase):
    def test_external(self):
        self.assertEqual(vcb.parse_array("3x"), ("external", 3))
        self.assertEqual(vcb.parse_array("3*"), ("external", 3))
        self.assertEqual(vcb.parse_array("x3"), ("external", 3))

    def test_internal(self):
        self.assertEqual(vcb.parse_array("3/"), ("internal", 3))
        self.assertEqual(vcb.parse_array("/3"), ("internal", 3))

    def test_no_match(self):
        self.assertIsNone(vcb.parse_array("abc"))
        self.assertIsNone(vcb.parse_array("12"))


class TestParseScale(unittest.TestCase):
    def test_ratio(self):
        self.assertEqual(vcb.parse_scale("1.5"), ("ratio", 1.5))

    def test_absolute(self):
        kind, value = vcb.parse_scale("10m")
        self.assertEqual(kind, "absolute")
        self.assertAlmostEqual(value, 10.0, places=9)
        kind, value = vcb.parse_scale("10'")
        self.assertEqual(kind, "absolute")
        self.assertAlmostEqual(value, 3.048, places=9)


class TestParseCoordinate(unittest.TestCase):
    def test_absolute(self):
        relative, values = vcb.parse_coordinate("[3', 4', 5']")
        self.assertFalse(relative)
        self.assertEqual([round(v, 9) for v in values], [0.9144, 1.2192, 1.524])

    def test_relative(self):
        relative, values = vcb.parse_coordinate("<1, 2>")
        self.assertTrue(relative)
        self.assertEqual([round(v, 9) for v in values], [0.001, 0.002])

    def test_errors(self):
        with self.assertRaises(ValueError):
            vcb.parse_coordinate("1, 2")


class TestParseVcbDispatcher(unittest.TestCase):
    def test_dispatch(self):
        self.assertAlmostEqual(vcb.parse_vcb("100", "length"), 0.1, places=9)
        self.assertEqual(vcb.parse_vcb("24s", "count"), 24)
        self.assertEqual(vcb.parse_vcb("3x", "array"), ("external", 3))

    def test_unknown_kind(self):
        with self.assertRaises(ValueError):
            vcb.parse_vcb("1", "nope")


class TestUnits(unittest.TestCase):
    def test_round_trip(self):
        for unit in ("mm", "cm", "m", "km", "in", "ft", "yd"):
            self.assertAlmostEqual(
                units.from_meters(units.to_meters(12.5, unit), unit), 12.5, places=9
            )

    def test_aliases(self):
        self.assertEqual(units.normalize_unit("inches"), "in")
        self.assertEqual(units.normalize_unit("FEET"), "ft")
        self.assertEqual(units.normalize_unit("Metres"), "m")
        with self.assertRaises(ValueError):
            units.normalize_unit("parsec")

    def test_format_length(self):
        self.assertEqual(units.format_length(0.1, "mm"), "100mm")
        self.assertEqual(units.format_length(0.1234, "mm", precision=1), "123.4mm")
        self.assertEqual(units.format_length(1.5, "m", precision=1), "1.5m")

    def test_format_fractional_inches(self):
        self.assertEqual(units.format_fractional_inches(2.054225), "6' 8 7/8\"")
        self.assertEqual(units.format_fractional_inches(0.0254), '1"')
        self.assertEqual(units.format_fractional_inches(0.9144), "3'")
        self.assertEqual(units.format_fractional_inches(0.0), '0"')
        self.assertEqual(units.format_fractional_inches(-0.0254), '-1"')


if __name__ == "__main__":
    unittest.main(verbosity=2)
