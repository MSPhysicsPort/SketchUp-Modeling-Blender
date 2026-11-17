"""Curve entity metadata (proposal §3.2 / research B §10.4).

SketchUp curves (Circle, Polygon, Arc, Pie, Freehand) are entities
with metadata: type, center, radius, segment count, plane. Blender
has no equivalent, so the metadata lives in a mesh ID property
``su_curves`` (a dict keyed by curve id, saved with the file) and
each curve edge carries the curve id in the ``su_curve_id`` edge int
layer. Loose edges have id 0.

Records (all plain JSON-able values, meters/degrees):
    type: "circle" | "polygon" | "arc" | "pie" | "freehand" | "curve"
    center: [x, y, z] (world coords; circle/polygon/arc/pie center)
    radius: float (circle/polygon/arc/pie)
    segments: int (edge count the curve was built with)
    normal: [x, y, z] (drawing plane normal)
    start_angle / end_angle: degrees in plane coords (arc/pie)
    closed: bool

Center inference and Entity Info radius/segment edits read these
records. If the recorded geometry no longer matches the edges
(edited by other tools), the record is stale: readers must validate
and degrade the edges to loose edges.
"""

import math

CURVE_ID_LAYER = "su_curve_id"
CURVES_PROPERTY = "su_curves"

# UNVERIFIED: the official Circle article gives no default segment
# count. 24 is the value SketchUp ships with in practice; it is a
# named constant so it can be corrected the moment Sen confirms the
# real default. Never present it as an official figure.
DEFAULT_CIRCLE_SEGMENTS = 24
DEFAULT_POLYGON_SEGMENTS = 6
# Official (Arcs article): arcs default to 12 segments.
DEFAULT_ARC_SEGMENTS = 12

GOLDEN_RATIO = 1.618033988749895
CENTER_TOLERANCE = 1e-4


# ---------------------------------------------------------------------------
# Mesh property access.
# ---------------------------------------------------------------------------


def _to_plain(value):
    """Convert ID property values to plain Python types.

    IDPropertyArray/IDPropertyGroup objects must never be written
    back into an ID property: assigning them inside a new dict
    recurses in Blender's converter and segfaults (seen 2026-11-17).
    """
    if isinstance(value, (str, bytes)):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if hasattr(value, "items"):
        try:
            return {str(k): _to_plain(v) for k, v in value.items()}
        except Exception:
            return {}
    if hasattr(value, "__len__") and hasattr(value, "__getitem__"):
        try:
            return [_to_plain(item) for item in value]
        except Exception:
            return []
    return value


def get_curves(mesh):
    """Return the curves dict {str(id): record} or {} if absent."""
    if mesh is None:
        return {}
    try:
        prop = mesh.get(CURVES_PROPERTY)
    except (AttributeError, ReferenceError):
        return {}
    if prop is None:
        return {}
    return {str(key): _to_plain(value) for key, value in prop.items()}


def set_curves(mesh, curves):
    plain = {str(key): _to_plain(value) for key, value in curves.items()}
    if not plain:
        try:
            del mesh[CURVES_PROPERTY]
        except (KeyError, TypeError, AttributeError):
            pass
        return
    mesh[CURVES_PROPERTY] = plain


def new_curve_id(mesh):
    curves = get_curves(mesh)
    used = [int(key) for key in curves if str(key).lstrip("-").isdigit()]
    return max(used, default=0) + 1


def register_curve(mesh, record):
    """Store a record, return its new curve id."""
    curves = get_curves(mesh)
    curve_id = new_curve_id(mesh)
    curves[str(curve_id)] = dict(record)
    set_curves(mesh, curves)
    return curve_id


def get_curve(mesh, curve_id):
    return get_curves(mesh).get(str(curve_id))


def update_curve(mesh, curve_id, record):
    curves = get_curves(mesh)
    if str(curve_id) in curves:
        curves[str(curve_id)] = dict(record)
        set_curves(mesh, curves)


def remove_curve(mesh, curve_id):
    curves = get_curves(mesh)
    if str(curve_id) in curves:
        del curves[str(curve_id)]
        set_curves(mesh, curves)


# ---------------------------------------------------------------------------
# Edge layer access (bmesh).
# ---------------------------------------------------------------------------


def ensure_curve_layer(bm):
    layer = bm.edges.layers.int.get(CURVE_ID_LAYER)
    if layer is None:
        layer = bm.edges.layers.int.new(CURVE_ID_LAYER)
    return layer


def tag_edges(bm, edges, curve_id):
    # Creating the layer invalidates previously fetched element
    # wrappers: keep indices, re-fetch after ensure.
    indices = [edge.index for edge in edges]
    layer = ensure_curve_layer(bm)
    bm.edges.ensure_lookup_table()
    for index in indices:
        bm.edges[index][layer] = int(curve_id)


def curve_id_of(bm, edge):
    layer = bm.edges.layers.int.get(CURVE_ID_LAYER)
    if layer is None:
        return 0
    return edge[layer]


def edges_of_curve(bm, curve_id):
    layer = bm.edges.layers.int.get(CURVE_ID_LAYER)
    if layer is None:
        return []
    return [edge for edge in bm.edges if edge[layer] == curve_id]


def untag_edges(bm, edges):
    layer = bm.edges.layers.int.get(CURVE_ID_LAYER)
    if layer is None:
        return
    indices = [edge.index for edge in edges]
    bm.edges.ensure_lookup_table()
    for index in indices:
        bm.edges[index][layer] = 0


# ---------------------------------------------------------------------------
# Plane geometry (pure math, T1-testable).
# ---------------------------------------------------------------------------


def plane_basis(normal):
    """Return (u, v) orthonormal basis vectors for a plane normal."""
    nx, ny, nz = normal
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / length, ny / length, nz / length
    if abs(nz) < 0.9:
        ux, uy, uz = -ny, nx, 0.0
    else:
        # cross(+Y, n) direction: perpendicular to n, +X when n is +Z.
        ux, uy, uz = nz, 0.0, -nx
    ulen = math.sqrt(ux * ux + uy * uy + uz * uz)
    ux, uy, uz = ux / ulen, uy / ulen, uz / ulen
    vx = ny * uz - nz * uy
    vy = nz * ux - nx * uz
    vz = nx * uy - ny * ux
    return (ux, uy, uz), (vx, vy, vz)


def to_plane(point, origin, normal):
    """Project a 3D point onto a plane; return (u, v) plane coords."""
    u, v = plane_basis(normal)
    dx, dy, dz = (point[0] - origin[0], point[1] - origin[1], point[2] - origin[2])
    return (
        dx * u[0] + dy * u[1] + dz * u[2],
        dx * v[0] + dy * v[1] + dz * v[2],
    )


def from_plane(uv, origin, normal):
    """Convert (u, v) plane coords back to a 3D point."""
    u, v = plane_basis(normal)
    return (
        origin[0] + uv[0] * u[0] + uv[1] * v[0],
        origin[1] + uv[0] * u[1] + uv[1] * v[1],
        origin[2] + uv[0] * u[2] + uv[1] * v[2],
    )


def project_on_plane(point, origin, normal):
    """Drop a 3D point perpendicularly onto a plane."""
    nx, ny, nz = normal
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / length, ny / length, nz / length
    dx, dy, dz = (point[0] - origin[0], point[1] - origin[1], point[2] - origin[2])
    dist = dx * nx + dy * ny + dz * nz
    return (point[0] - dist * nx, point[1] - dist * ny, point[2] - dist * nz)


def angle_in_plane(point, center, normal):
    """Angle (degrees, 0..360) of a point around a center in a plane."""
    u, v = to_plane(point, center, normal)
    return math.degrees(math.atan2(v, u)) % 360.0


def circle_points(center, normal, radius, segments, start_angle=0.0):
    """Points of a full circle (segments points, last connects to first)."""
    pts = []
    for i in range(segments):
        angle = math.radians(start_angle + 360.0 * i / segments)
        pts.append(
            from_plane(
                (radius * math.cos(angle), radius * math.sin(angle)),
                center,
                normal,
            )
        )
    return pts


def arc_points(center, normal, radius, start_angle, end_angle, segments):
    """Points along an arc, inclusive of both ends (segments+1 points).

    The arc runs counter-clockwise from start_angle to end_angle
    (both degrees); if end_angle <= start_angle it wraps past 360.
    """
    sweep = (end_angle - start_angle) % 360.0
    if sweep == 0.0:
        sweep = 360.0
    pts = []
    for i in range(segments + 1):
        angle = math.radians(start_angle + sweep * i / segments)
        pts.append(
            from_plane(
                (radius * math.cos(angle), radius * math.sin(angle)),
                center,
                normal,
            )
        )
    return pts


def arc_from_three_points(p1, p2, p3, normal):
    """Circle through three plane points; returns (center, radius) or
    None when the points are collinear."""
    u1, v1 = to_plane(p1, p1, normal)
    u2, v2 = to_plane(p2, p1, normal)
    u3, v3 = to_plane(p3, p1, normal)
    d = 2.0 * (u1 * (v2 - v3) + u2 * (v3 - v1) + u3 * (v1 - v2))
    if abs(d) < 1e-12:
        return None
    sq1 = u1 * u1 + v1 * v1
    sq2 = u2 * u2 + v2 * v2
    sq3 = u3 * u3 + v3 * v3
    cu = (sq1 * (v2 - v3) + sq2 * (v3 - v1) + sq3 * (v1 - v2)) / d
    cv = (sq1 * (u3 - u2) + sq2 * (u1 - u3) + sq3 * (u2 - u1)) / d
    center = from_plane((cu, cv), p1, normal)
    radius = math.hypot(u1 - cu, v1 - cv)
    return center, radius


def arc_bulge_to_radius(chord_length, bulge):
    """Radius of an arc from chord length and bulge (sagitta)."""
    if bulge <= 0.0:
        return None
    half = chord_length / 2.0
    return (half * half + bulge * bulge) / (2.0 * bulge)


def arc_radius_to_bulge(chord_length, radius):
    """Bulge (sagitta) of an arc from chord length and radius."""
    half = chord_length / 2.0
    if radius < half:
        return None
    return radius - math.sqrt(radius * radius - half * half)


def segments_for_circle_segments(arc_segments_total, sweep_degrees):
    """Arc segments implied by a full-circle segment count (``20c``)."""
    return max(1, round(arc_segments_total * sweep_degrees / 360.0))
