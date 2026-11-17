"""VCB (Measurements box) input parsing.

Pure Python: no bpy dependency, so this module is unit-testable with a
plain interpreter (T1). All parsed lengths are returned in meters.

Supported input forms (research/01 §4.3, research/02 §9):

- bare numbers (default unit), negatives: ``100``, ``-35mm``
- decimals, fractions, mixed fractions: ``1.5``, ``1/2``, ``1 1/2``
- feet'inches": ``6' 8 7/8"``, ``6'8"``, ``8"``, ``3'``
- unit suffixes: ``10mm``, ``10cm``, ``10m``, ``6in``, ``15cm``
- lists with comma/semicolon separators, empty slot = unchanged (None):
  ``8',20'``, ``3',``, ``,3'``
- coordinates: ``[3', 4', 5']`` absolute, ``<3', 4', 5'>`` relative
- angles in degrees, slope ``8:12``
- counts: ``24``, ``24s``; arrays: ``3x``, ``3*``, ``3/``, ``/3``
  (``x3`` is also accepted although desktop support is unverified)
- scale: bare number = factor, length with unit = absolute size
"""

import math
import re

try:
    from .units import UNIT_FACTORS, normalize_unit, DEFAULT_UNIT
except ImportError:  # Standalone T1 import (core/ directory on sys.path).
    from units import UNIT_FACTORS, normalize_unit, DEFAULT_UNIT

_FRACTION_RE = re.compile(r"^\s*(?:(\d+)\s+)?(\d+)\s*/\s*(\d+)\s*$")
_NUMBER_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_SUFFIX_RE = re.compile(r"^(.*?)\s*([A-Za-z]+)\s*$")


def _parse_number_or_fraction(text):
    """Parse ``12``, ``12.5``, ``1/2`` or ``1 1/2`` into a float."""
    s = text.strip()
    match = _FRACTION_RE.match(s)
    if match:
        whole, numerator, denominator = match.groups()
        denominator = int(denominator)
        if denominator == 0:
            raise ValueError("zero denominator in fraction: %r" % (text,))
        value = int(numerator) / denominator
        if whole:
            value += int(whole)
        return value
    if _NUMBER_RE.match(s):
        return float(s)
    raise ValueError("not a number: %r" % (text,))


def parse_length(text, default_unit=DEFAULT_UNIT):
    """Parse a SketchUp-style length into meters."""
    if not isinstance(text, str):
        raise TypeError("length input must be a string")
    s = text.strip().replace("\u2019", "'").replace("\u2033", '"').replace("\u201d", '"')
    if not s:
        raise ValueError("empty length")
    sign = 1.0
    if s[0] in "+-":
        if s[0] == "-":
            sign = -1.0
        s = s[1:].strip()
        if not s:
            raise ValueError("missing number: %r" % (text,))
    # Feet'inches" form.
    if "'" in s:
        feet_text, _, rest = s.partition("'")
        feet = _parse_number_or_fraction(feet_text)
        rest = rest.strip()
        if rest.endswith('"'):
            rest = rest[:-1].strip()
        inches = _parse_number_or_fraction(rest) if rest else 0.0
        return sign * (feet * UNIT_FACTORS["ft"] + inches * UNIT_FACTORS["in"])
    # Trailing inch mark.
    if s.endswith('"'):
        inches = _parse_number_or_fraction(s[:-1].strip())
        return sign * inches * UNIT_FACTORS["in"]
    # Unit suffix.
    match = _SUFFIX_RE.match(s)
    if match and match.group(2):
        number_text, unit_text = match.group(1), match.group(2)
        try:
            unit = normalize_unit(unit_text)
        except ValueError:
            raise ValueError("unknown unit: %r" % (unit_text,))
        if not number_text.strip():
            raise ValueError("missing number: %r" % (text,))
        return sign * _parse_number_or_fraction(number_text) * UNIT_FACTORS[unit]
    # Bare number / fraction in the default unit.
    return sign * _parse_number_or_fraction(s) * UNIT_FACTORS[normalize_unit(default_unit)]


def parse_length_list(text, default_unit=DEFAULT_UNIT):
    """Parse a separated list of lengths; empty slots become None."""
    s = text.strip()
    separator = ";" if ";" in s else ","
    result = []
    for part in s.split(separator):
        result.append(parse_length(part, default_unit) if part.strip() else None)
    return result


def parse_angle(text):
    """Parse an angle in degrees; slope ``rise:run`` becomes degrees."""
    s = text.strip()
    if ":" in s:
        rise_text, _, run_text = s.partition(":")
        rise = float(rise_text)
        run = float(run_text)
        if run == 0:
            raise ValueError("zero run in slope: %r" % (text,))
        return math.degrees(math.atan2(rise, run))
    lowered = s.lower()
    for suffix in ("degrees", "deg", "\u00b0"):
        if lowered.endswith(suffix):
            s = s[: -len(suffix)].strip()
            break
    return float(s)


def parse_count(text):
    """Parse a segment/edge count: ``24`` or ``24s``."""
    match = re.match(r"^\s*(\d+)\s*[sS]?\s*$", text)
    if not match:
        raise ValueError("not a count: %r" % (text,))
    return int(match.group(1))


def parse_array(text):
    """Parse an array spec; returns (kind, n) or None if no match.

    ``3x`` / ``3*`` / ``x3`` -> ("external", 3);
    ``3/`` / ``/3`` -> ("internal", 3).
    """
    s = text.strip()
    match = re.match(r"^(\d+)\s*[xX\*]$", s) or re.match(r"^[xX\*]\s*(\d+)$", s)
    if match:
        return ("external", int(match.group(1)))
    match = re.match(r"^(\d+)\s*/$", s) or re.match(r"^/\s*(\d+)$", s)
    if match:
        return ("internal", int(match.group(1)))
    return None


def parse_scale(text, default_unit=DEFAULT_UNIT):
    """Parse a Scale input: ("ratio", factor) or ("absolute", meters)."""
    s = text.strip()
    if "'" in s or '"' in s or re.search(r"[A-Za-z]", s):
        return ("absolute", parse_length(s, default_unit))
    return ("ratio", float(s))


def parse_scale_list(text, default_unit=DEFAULT_UNIT):
    """Parse a separated list of Scale inputs; empty slots become None."""
    s = text.strip()
    separator = ";" if ";" in s else ","
    result = []
    for part in s.split(separator):
        result.append(parse_scale(part, default_unit) if part.strip() else None)
    return result


def parse_coordinate(text, default_unit=DEFAULT_UNIT):
    """Parse ``[x, y, z]`` (absolute) or ``<x, y, z>`` (relative).

    Returns (is_relative, [lengths in meters or None]).
    """
    s = text.strip()
    if s.startswith("[") and s.endswith("]"):
        is_relative, inner = False, s[1:-1]
    elif s.startswith("<") and s.endswith(">"):
        is_relative, inner = True, s[1:-1]
    else:
        raise ValueError("not a coordinate: %r" % (text,))
    parts = inner.split(",")
    if len(parts) not in (2, 3):
        raise ValueError("coordinate needs 2 or 3 values: %r" % (text,))
    return (
        is_relative,
        [parse_length(p, default_unit) if p.strip() else None for p in parts],
    )


_PARSERS = {
    "length": parse_length,
    "length_list": parse_length_list,
    "angle": parse_angle,
    "count": parse_count,
    "array": parse_array,
    "scale": parse_scale,
    "scale_list": parse_scale_list,
    "coordinate": parse_coordinate,
}


def parse_vcb(text, kind, default_unit=DEFAULT_UNIT):
    """Single entry point: parse VCB text for the given input kind."""
    try:
        parser = _PARSERS[kind]
    except KeyError:
        raise ValueError("unknown VCB kind: %r" % (kind,))
    return parser(text, default_unit) if kind != "angle" and kind != "count" and kind != "array" else parser(text)
