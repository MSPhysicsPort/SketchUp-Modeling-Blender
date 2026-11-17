"""Unit conversion and formatting.

Pure Python: no bpy dependency, unit-testable with a plain interpreter (T1).

The add-on stores geometry in meters (Blender units) internally; this
module only converts for display and input (see research/02 §9).
"""

import math

# Meters per unit.
UNIT_FACTORS = {
    "mm": 0.001,
    "cm": 0.01,
    "m": 1.0,
    "km": 1000.0,
    "in": 0.0254,
    "ft": 0.3048,
    "yd": 0.9144,
}

_UNIT_ALIASES = {
    "millimeter": "mm", "millimeters": "mm",
    "millimetre": "mm", "millimetres": "mm",
    "centimeter": "cm", "centimeters": "cm",
    "centimetre": "cm", "centimetres": "cm",
    "meter": "m", "meters": "m", "metre": "m", "metres": "m",
    "kilometer": "km", "kilometers": "km",
    "kilometre": "km", "kilometres": "km",
    "inch": "in", "inches": "in",
    "foot": "ft", "feet": "ft",
    "yard": "yd", "yards": "yd",
}

# D15 default: millimeter template, length snapping off.
DEFAULT_UNIT = "mm"
LENGTH_SNAPPING_DEFAULT = False


def normalize_unit(unit):
    """Return the canonical unit key for a user-supplied unit name."""
    key = str(unit).strip().lower()
    if key in UNIT_FACTORS:
        return key
    if key in _UNIT_ALIASES:
        return _UNIT_ALIASES[key]
    raise ValueError("unknown unit: %r" % (unit,))


def to_meters(value, unit):
    return float(value) * UNIT_FACTORS[normalize_unit(unit)]


def from_meters(meters, unit):
    return float(meters) / UNIT_FACTORS[normalize_unit(unit)]


def format_length(meters, unit=DEFAULT_UNIT, precision=1):
    """Format a length in meters as a decimal string, e.g. ``100mm``."""
    value = from_meters(meters, unit)
    text = "%.*f" % (precision, value)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("", "-0"):
        text = "0"
    return text + normalize_unit(unit)


def format_fractional_inches(meters, denominator=16):
    """Format a length as feet/inches with a fractional inch part.

    Examples: ``6' 8 7/8"``, ``8"``, ``3'``, ``7/8"``.
    """
    total_inches = from_meters(meters, "in")
    sign = "-" if total_inches < 0 else ""
    total_inches = abs(total_inches)
    feet = int(total_inches // 12)
    remainder = total_inches - feet * 12
    whole = int(remainder)
    numerator = int(round((remainder - whole) * denominator))
    if numerator == denominator:
        whole += 1
        numerator = 0
    if whole == 12:
        feet += 1
        whole = 0
    if numerator:
        common = math.gcd(numerator, denominator)
        numerator //= common
        denominator //= common
    parts = []
    if feet:
        parts.append("%d'" % feet)
    inch_text = ""
    if whole:
        inch_text += str(whole)
    if numerator:
        inch_text += (" " if inch_text else "") + "%d/%d" % (numerator, denominator)
    if inch_text:
        parts.append(inch_text + '"')
    if not parts:
        return '0"'
    return sign + " ".join(parts)
