"""Inference engine: geometry layer (pure Python, no bpy).

Two-layer design (proposal §5.9): this module is the geometry layer —
it takes pre-computed candidates (screen positions, ray hits) and
returns the winning inference with pure math, so it is unit-testable
with a plain interpreter (T1). The screen layer (mouse pixels -> ray,
candidate building from bmesh, BVH ray cast) lives in the modal
operator base and is verified on the real machine.

P1 scope: point inferences (Endpoint, Midpoint, Center, Intersection,
Guide Point, Origin, On Edge, On Line, On Face), axis / From Point
linear inferences, the arrow-key / Shift lock state machine, and the
Line Alt three-state cycle. Parallel / Perpendicular / Extend /
Through Point / Tangent and dual-constraint (compound) inferences
arrive in later phases; the state machine already carries their modes
so call sites do not change.
"""

import math
from collections import namedtuple

# ---------------------------------------------------------------------------
# Small vector helpers (plain tuples, no mathutils: T1 runs without bpy).
# ---------------------------------------------------------------------------


def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vscale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def vdot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vcross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def vlen(a):
    return math.sqrt(vdot(a, a))


def vnorm(a):
    length = vlen(a)
    if length == 0.0:
        return (0.0, 0.0, 0.0)
    return vscale(a, 1.0 / length)


def vdist(a, b):
    return vlen(vsub(a, b))


# ---------------------------------------------------------------------------
# Axes, colors, labels.
# ---------------------------------------------------------------------------

Axes = namedtuple("Axes", ["origin", "x", "y", "z"])

WORLD_AXES = Axes((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))

AXIS_COLORS = ((1.0, 0.0, 0.0, 1.0), (0.0, 0.8, 0.0, 1.0), (0.0, 0.4, 1.0, 1.0))
AXIS_NAMES = ("Red", "Green", "Blue")

# Marker colors (RGBA). Only Midpoint's light blue is confirmed by the
# official text; the rest come from the 2006 manual / community
# tutorials (second-hand, D15: verify against Sen's screenshots).
# Intersection is white here (the manual says black, invisible on
# Blender's dark viewport). Everything is a configurable constant.
INFERENCE_COLORS = {
    "endpoint": (0.0, 0.8, 0.0, 1.0),
    "midpoint": (0.35, 0.75, 1.0, 1.0),
    "center": (0.0, 0.4, 1.0, 1.0),
    "intersection": (1.0, 1.0, 1.0, 1.0),
    "guide_point": (1.0, 0.8, 0.0, 1.0),
    "origin": (1.0, 1.0, 1.0, 1.0),
    "on_edge": (1.0, 0.0, 0.0, 1.0),
    "on_line": (1.0, 0.8, 0.0, 1.0),
    "on_face": (0.2, 0.5, 1.0, 1.0),
    "from_point": (1.0, 0.0, 1.0, 1.0),
    "free": (1.0, 1.0, 1.0, 1.0),
}

# ScreenTip msgids (English; translated at draw time via translate()).
# Chinese wording is unverified and awaits Sen's confirmation.
INFERENCE_LABELS = {
    "endpoint": "Endpoint",
    "midpoint": "Midpoint",
    "center": "Center",
    "intersection": "Intersection",
    "guide_point": "Guide Point",
    "origin": "Origin",
    "on_edge": "On Edge",
    "on_line": "On Line",
    "on_face": "On Face",
    "from_point": "From Point",
    "axis": "On Axis",
    "free": "",
}

# Lower wins. Point inferences beat linear, linear beats free face point.
KIND_PRIORITY = {
    "endpoint": 0,
    "midpoint": 1,
    "center": 2,
    "intersection": 3,
    "guide_point": 4,
    "origin": 5,
    "on_edge": 6,
    "on_line": 7,
    "on_face": 8,
    "from_point": 9,
    "axis": 9,
    "free": 10,
}

AXIS_SNAP_DEGREES = 8.0
DEFAULT_PIXEL_TOLERANCE = 12.0


class InferenceResult:
    """One evaluated inference: kind, 3D point, display metadata."""

    __slots__ = ("kind", "point", "axis_index", "source")

    def __init__(self, kind, point, axis_index=None, source=None):
        self.kind = kind
        self.point = tuple(point)
        self.axis_index = axis_index
        self.source = source

    @property
    def label(self):
        if self.kind == "axis" and self.axis_index is not None:
            return "On %s Axis" % AXIS_NAMES[self.axis_index]
        return INFERENCE_LABELS.get(self.kind, "")

    @property
    def color(self):
        if self.kind in ("axis", "from_point") and self.axis_index is not None:
            return AXIS_COLORS[self.axis_index]
        return INFERENCE_COLORS.get(self.kind, (1.0, 1.0, 1.0, 1.0))

    def __repr__(self):
        return "InferenceResult(%r, %r)" % (self.kind, self.point)


# ---------------------------------------------------------------------------
# Pure geometry primitives.
# ---------------------------------------------------------------------------


def closest_point_on_segment(point, seg_a, seg_b):
    """Return (closest point, t in [0, 1], distance)."""
    ab = vsub(seg_b, seg_a)
    denom = vdot(ab, ab)
    if denom == 0.0:
        return seg_a, 0.0, vdist(point, seg_a)
    t = vdot(vsub(point, seg_a), ab) / denom
    t = max(0.0, min(1.0, t))
    closest = vadd(seg_a, vscale(ab, t))
    return closest, t, vdist(point, closest)


def ray_segment_closest(ray_origin, ray_dir, seg_a, seg_b):
    """Closest points between a ray (t >= 0) and a segment.

    Returns (ray_t, seg_t, distance, ray_point, seg_point).
    """
    d1 = vnorm(ray_dir)
    d2 = vsub(seg_b, seg_a)
    r = vsub(ray_origin, seg_a)
    a = 1.0
    b = vdot(d1, d2)
    c = vdot(d2, d2)
    d = vdot(d1, r)
    e = vdot(d2, r)
    denom = a * c - b * b
    if c == 0.0:
        seg_t = 0.0
        ray_t = max(0.0, -d)
    elif denom < 1e-12:
        # Parallel: project the ray origin onto the segment line.
        seg_t = max(0.0, min(1.0, e / c))
        ray_t = b * seg_t - d
        if ray_t < 0.0:
            ray_t = 0.0
            _, seg_t, _ = closest_point_on_segment(ray_origin, seg_a, seg_b)
    else:
        seg_t = (a * e - b * d) / denom
        seg_t = max(0.0, min(1.0, seg_t))
        ray_t = b * seg_t - d
        if ray_t < 0.0:
            ray_t = 0.0
            _, seg_t, _ = closest_point_on_segment(ray_origin, seg_a, seg_b)
    ray_point = vadd(ray_origin, vscale(d1, ray_t))
    seg_point = vadd(seg_a, vscale(d2, seg_t))
    return ray_t, seg_t, vdist(ray_point, seg_point), ray_point, seg_point


def segment_segment_closest(a1, a2, b1, b2):
    """Closest points between two segments (Ericson, Real-Time CD).

    Returns (t_a, t_b, distance, point_a, point_b).
    """
    d1 = vsub(a2, a1)
    d2 = vsub(b2, b1)
    r = vsub(a1, b1)
    a = vdot(d1, d1)
    e = vdot(d2, d2)
    f = vdot(d2, r)
    if a <= 1e-12 and e <= 1e-12:
        return 0.0, 0.0, vdist(a1, b1), a1, b1
    if a <= 1e-12:
        s = 0.0
        t = max(0.0, min(1.0, f / e))
    else:
        c = vdot(d1, r)
        if e <= 1e-12:
            t = 0.0
            s = max(0.0, min(1.0, -c / a))
        else:
            b = vdot(d1, d2)
            denom = a * e - b * b
            s = (b * f - c * e) / denom if denom > 1e-12 else 0.0
            s = max(0.0, min(1.0, s))
            t = (b * s + f) / e
            if t < 0.0:
                t = 0.0
                s = max(0.0, min(1.0, -c / a))
            elif t > 1.0:
                t = 1.0
                s = max(0.0, min(1.0, (b - c) / a))
    point_a = vadd(a1, vscale(d1, s))
    point_b = vadd(b1, vscale(d2, t))
    return s, t, vdist(point_a, point_b), point_a, point_b


def ray_triangle(ray_origin, ray_dir, v0, v1, v2):
    """Moller-Trumbore; returns ray t or None (no backface culling)."""
    direction = vnorm(ray_dir)
    e1 = vsub(v1, v0)
    e2 = vsub(v2, v0)
    p = vcross(direction, e2)
    det = vdot(e1, p)
    if abs(det) < 1e-12:
        return None
    inv_det = 1.0 / det
    tvec = vsub(ray_origin, v0)
    u = vdot(tvec, p) * inv_det
    if u < 0.0 or u > 1.0:
        return None
    q = vcross(tvec, e1)
    v = vdot(direction, q) * inv_det
    if v < 0.0 or u + v > 1.0:
        return None
    t = vdot(e2, q) * inv_det
    return t if t >= 0.0 else None


def project_point_on_line(point, line_origin, line_dir):
    direction = vnorm(line_dir)
    return vadd(line_origin, vscale(direction, vdot(vsub(point, line_origin), direction)))


def project_point_on_plane(point, plane_origin, plane_normal):
    normal = vnorm(plane_normal)
    return vsub(point, vscale(normal, vdot(vsub(point, plane_origin), normal)))


def ray_plane(ray_origin, ray_dir, plane_origin, plane_normal):
    """Ray/plane intersection point, or None when (near-)parallel."""
    normal = vnorm(plane_normal)
    denom = vdot(vnorm(ray_dir), normal)
    if abs(denom) < 1e-9:
        return None
    t = vdot(vsub(plane_origin, ray_origin), normal) / denom
    if t < 0.0:
        return None
    return vadd(ray_origin, vscale(vnorm(ray_dir), t))


def dist_point_to_segment_2d(px, py, ax, ay, bx, by):
    """2D point-to-segment distance in pixels."""
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom == 0.0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / denom
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def segments_intersect_2d(a1, a2, b1, b2):
    """2D segment intersection; returns (x, y, t_on_a, t_on_b) or None."""
    r = (a2[0] - a1[0], a2[1] - a1[1])
    s = (b2[0] - b1[0], b2[1] - b1[1])
    denom = r[0] * s[1] - r[1] * s[0]
    if abs(denom) < 1e-12:
        return None
    qp = (b1[0] - a1[0], b1[1] - a1[1])
    t = (qp[0] * s[1] - qp[1] * s[0]) / denom
    u = (qp[0] * r[1] - qp[1] * r[0]) / denom
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return (a1[0] + t * r[0], a1[1] + t * r[1], t, u)
    return None


# ---------------------------------------------------------------------------
# Lock state machine (pure).
# ---------------------------------------------------------------------------

LINE_MODE_ALL_ON = "all_on"
LINE_MODE_ALL_OFF = "all_off"
LINE_MODE_PARALLEL_PERP = "parallel_perp"


class LockState:
    """Arrow-key / Shift lock state machine (research/01 §4.2).

    Modes: none, axis (R/G/B), direction (Shift-locked), plane.
    Arrow keys toggle: pressing the same axis key again unlocks
    (community consensus, D15: "press again to release" unverified).
    Shift locks while held and releases on key-up.
    """

    def __init__(self):
        self.mode = "none"
        self.axis_index = None
        self.origin = None
        self.direction = None
        self.normal = None
        self.line_mode = LINE_MODE_ALL_ON

    @property
    def locked(self):
        return self.mode != "none"

    def press_arrow(self, axis_index, origin):
        if self.mode == "axis" and self.axis_index == axis_index:
            self.clear()
        else:
            self.mode = "axis"
            self.axis_index = axis_index
            self.origin = tuple(origin)
            self.direction = None
            self.normal = None

    def press_shift(self, direction, origin):
        if vlen(direction) < 1e-9:
            return
        self.mode = "direction"
        self.direction = vnorm(direction)
        self.origin = tuple(origin)
        self.axis_index = None
        self.normal = None

    def release_shift(self):
        if self.mode == "direction":
            self.clear()

    def set_plane(self, normal, origin):
        self.mode = "plane"
        self.normal = vnorm(normal)
        self.origin = tuple(origin)
        self.axis_index = None
        self.direction = None

    def press_alt_line(self):
        order = (LINE_MODE_ALL_ON, LINE_MODE_ALL_OFF, LINE_MODE_PARALLEL_PERP)
        self.line_mode = order[(order.index(self.line_mode) + 1) % len(order)]

    def clear(self):
        self.mode = "none"
        self.axis_index = None
        self.origin = None
        self.direction = None
        self.normal = None

    def apply(self, point, axes=WORLD_AXES):
        """Constrain a point to the active lock; no-op when unlocked."""
        if self.mode == "axis" and self.origin is not None:
            axis = (axes.x, axes.y, axes.z)[self.axis_index]
            return project_point_on_line(point, self.origin, axis)
        if self.mode == "direction" and self.origin is not None:
            return project_point_on_line(point, self.origin, self.direction)
        if self.mode == "plane" and self.origin is not None:
            return project_point_on_plane(point, self.origin, self.normal)
        return tuple(point)

    def distance_to_lock(self, point, axes=WORLD_AXES):
        """3D distance from a point to the lock line/plane (inf if free)."""
        if not self.locked or self.origin is None:
            return math.inf
        if self.mode == "plane":
            return abs(vdot(vsub(point, self.origin), self.normal))
        if self.mode == "axis":
            axis = (axes.x, axes.y, axes.z)[self.axis_index]
            direction = axis
        else:
            direction = self.direction
        closest, _, dist = closest_point_on_segment(
            point,
            vsub(self.origin, vscale(direction, 1e6)),
            vadd(self.origin, vscale(direction, 1e6)),
        )
        return dist

    @property
    def label(self):
        if self.mode == "axis":
            return "On %s Axis" % AXIS_NAMES[self.axis_index]
        if self.mode == "direction":
            return "Locked Direction"
        if self.mode == "plane":
            return "Locked Plane"
        return ""

    @property
    def color(self):
        if self.mode == "axis":
            return AXIS_COLORS[self.axis_index]
        return (1.0, 0.0, 1.0, 1.0)


# ---------------------------------------------------------------------------
# Evaluation.
# ---------------------------------------------------------------------------


def _axis_snap(free_point, anchor, axes, max_degrees=AXIS_SNAP_DEGREES):
    """Snap a free point to the nearest axis line through anchor.

    Returns (axis_index, snapped_point, angle_degrees) or None.
    """
    delta = vsub(free_point, anchor)
    length = vlen(delta)
    if length < 1e-9:
        return None
    best = None
    for index, axis in enumerate((axes.x, axes.y, axes.z)):
        cos_angle = abs(vdot(delta, axis)) / length
        cos_angle = max(-1.0, min(1.0, cos_angle))
        angle = math.degrees(math.acos(cos_angle))
        if angle <= max_degrees and (best is None or angle < best[2]):
            snapped = project_point_on_line(free_point, anchor, axis)
            best = (index, snapped, angle)
    return best


def evaluate(
    ray_origin,
    ray_dir,
    mouse_xy,
    points=(),
    edges=(),
    face_hit=None,
    guide_lines=(),
    start_point=None,
    from_point=None,
    lock=None,
    axes=WORLD_AXES,
    pixel_tolerance=DEFAULT_PIXEL_TOLERANCE,
    lock_tolerance=0.005,
):
    """Evaluate the winning inference for one mouse position.

    points: iterable of (kind, point3d, xy2d).
    edges: iterable of (p1_3d, p2_3d, xy1_2d, xy2_2d).
    face_hit: (point3d, normal, face_index) or None.
    guide_lines: iterable of (point3d, direction3d, xy1_2d, xy2_2d)
        where the 2D points are two far-apart projections of the line.
    Returns an InferenceResult (never None: falls back to a free point
    on the ground plane through the axes origin).
    """
    ray_origin = tuple(ray_origin)
    ray_dir = vnorm(ray_dir)
    lock = lock or LockState()
    linear_enabled = lock.line_mode == LINE_MODE_ALL_ON

    # 1. Point candidates within pixel tolerance.
    best = None  # (distance_px, priority, kind, point, source)
    for kind, point, xy in points:
        dist_px = math.hypot(mouse_xy[0] - xy[0], mouse_xy[1] - xy[1])
        if dist_px > pixel_tolerance:
            continue
        if lock.locked and lock.distance_to_lock(point, axes) > lock_tolerance:
            continue
        entry = (dist_px, KIND_PRIORITY.get(kind, 99), kind, tuple(point), None)
        if best is None or entry[:2] < best[:2]:
            best = entry
    # On-edge candidates from 2D segment distance.
    for p1, p2, xy1, xy2 in edges:
        dist_px = dist_point_to_segment_2d(
            mouse_xy[0], mouse_xy[1], xy1[0], xy1[1], xy2[0], xy2[1]
        )
        if dist_px > pixel_tolerance:
            continue
        _, _, _, _, seg_point = ray_segment_closest(ray_origin, ray_dir, p1, p2)
        if lock.locked and lock.distance_to_lock(seg_point, axes) > lock_tolerance:
            continue
        entry = (dist_px, KIND_PRIORITY["on_edge"], "on_edge", seg_point, None)
        if best is None or entry[:2] < best[:2]:
            best = entry
    # On-line (guide line) candidates.
    for gpoint, gdir, xy1, xy2 in guide_lines:
        dist_px = dist_point_to_segment_2d(
            mouse_xy[0], mouse_xy[1], xy1[0], xy1[1], xy2[0], xy2[1]
        )
        if dist_px > pixel_tolerance:
            continue
        far_a = vsub(gpoint, vscale(gdir, 1e6))
        far_b = vadd(gpoint, vscale(gdir, 1e6))
        _, _, _, _, line_point = ray_segment_closest(ray_origin, ray_dir, far_a, far_b)
        if lock.locked and lock.distance_to_lock(line_point, axes) > lock_tolerance:
            continue
        entry = (dist_px, KIND_PRIORITY["on_line"], "on_line", line_point, None)
        if best is None or entry[:2] < best[:2]:
            best = entry
    if best is not None:
        point = lock.apply(best[3], axes) if lock.locked else best[3]
        return InferenceResult(best[2], point)

    # 2. Free reference point (face hit, else ground plane).
    if face_hit is not None:
        free_point = tuple(face_hit[0])
    else:
        ground = ray_plane(ray_origin, ray_dir, axes.origin, axes.z)
        if ground is None:
            ground = vadd(ray_origin, vscale(ray_dir, 5.0))
        free_point = ground

    # 3. Linear inferences (axis / From Point), unless disabled.
    if linear_enabled:
        if from_point is not None:
            snapped = _axis_snap(free_point, from_point, axes)
            if snapped is not None:
                return InferenceResult("from_point", snapped[1], axis_index=snapped[0])
        if start_point is not None:
            snapped = _axis_snap(free_point, start_point, axes)
            if snapped is not None:
                return InferenceResult("axis", snapped[1], axis_index=snapped[0])

    # 4. Lock constraint on the free point.
    if lock.locked:
        return InferenceResult("free", lock.apply(free_point, axes))

    # 5. Face hit / free point.
    if face_hit is not None:
        return InferenceResult("on_face", free_point)
    return InferenceResult("free", free_point)


def find_intersections(edges_2d, mouse_xy, pixel_tolerance, world_tolerance=0.005):
    """Screen-space edge/edge intersections near the mouse.

    edges_2d: iterable of (p1_3d, p2_3d, xy1, xy2).
    Returns a list of 3D points where two projected segments cross
    near the mouse and the 3D segments pass within world_tolerance.
    """
    near = []
    for p1, p2, xy1, xy2 in edges_2d:
        if (
            dist_point_to_segment_2d(mouse_xy[0], mouse_xy[1], xy1[0], xy1[1], xy2[0], xy2[1])
            <= pixel_tolerance * 2.0
        ):
            near.append((p1, p2, xy1, xy2))
    results = []
    for i in range(len(near)):
        for j in range(i + 1, len(near)):
            hit = segments_intersect_2d(near[i][2], near[i][3], near[j][2], near[j][3])
            if hit is None:
                continue
            ix, iy, _, _ = hit
            if math.hypot(ix - mouse_xy[0], iy - mouse_xy[1]) > pixel_tolerance:
                continue
            _, _, dist, _, seg_point = segment_segment_closest(
                near[i][0], near[i][1], near[j][0], near[j][1]
            )
            if dist <= world_tolerance:
                results.append(seg_point)
    return results
