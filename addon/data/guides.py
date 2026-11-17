"""Guides (reference lines / points): pure data container.

Guides are their own entity type: they never enter the Mesh, never
participate in face creation, and are only inference candidates
(Guide Point / On Line) plus dashed overlay drawing. The Tape
Measure / Protractor tools that create them arrive in P6; this
module is the data + candidate plumbing that P1 inference builds on.

Persistence (saved with the file) arrives with the creating tools;
for P1 the set lives in session state only.
"""


class GuideSet:
    """A set of guide points and infinite guide lines."""

    def __init__(self):
        self.points = []
        self.lines = []

    def add_point(self, point):
        point = tuple(point)
        if point not in self.points:
            self.points.append(point)
        return point

    def add_line(self, point, direction):
        try:
            from ..core.inference import vnorm
        except (ImportError, ValueError):
            from core.inference import vnorm

        entry = (tuple(point), vnorm(direction))
        if entry not in self.lines:
            self.lines.append(entry)
        return entry

    def clear(self):
        self.points = []
        self.lines = []

    def to_dict(self):
        return {
            "points": [list(p) for p in self.points],
            "lines": [[list(p), list(d)] for p, d in self.lines],
        }

    @classmethod
    def from_dict(cls, data):
        guides = cls()
        try:
            guides.points = [tuple(p) for p in data.get("points", [])]
            guides.lines = [
                (tuple(p), tuple(d)) for p, d in data.get("lines", [])
            ]
        except (TypeError, ValueError):
            pass
        return guides

    def remove_near(self, point, tolerance=0.01):
        """Remove guides near a point; returns the number removed."""
        try:
            from ..core.inference import vdist, vsub, vdot
        except (ImportError, ValueError):
            from core.inference import vdist, vsub, vdot

        before = len(self.points) + len(self.lines)
        self.points = [p for p in self.points if vdist(p, point) > tolerance]
        kept = []
        for gpoint, gdir in self.lines:
            delta = vsub(point, gpoint)
            along = vdot(delta, gdir)
            closest = (
                gpoint[0] + gdir[0] * along,
                gpoint[1] + gdir[1] * along,
                gpoint[2] + gdir[2] * along,
            )
            if vdist(closest, point) > tolerance:
                kept.append((gpoint, gdir))
        self.lines = kept
        return before - (len(self.points) + len(self.lines))

    def point_candidates(self):
        """Guide points as inference point candidates (kind, point)."""
        return [("guide_point", point) for point in self.points]

    def line_candidates(self):
        """Guide lines as (point, direction) pairs for inference."""
        return list(self.lines)
