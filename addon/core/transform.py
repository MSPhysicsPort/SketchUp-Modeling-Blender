"""Transform helpers: snapshots, duplication, polygon offset, and
small 3D math for the Move/Rotate/Scale/PushPull/Offset tools.

Snapshot = the selected elements' local coordinates, captured before
a transform. Copies and arrays re-duplicate from the snapshot so
repeated operations never accumulate floating-point drift.
"""

import math

from mathutils import Matrix, Vector


# ---------------------------------------------------------------------------
# Snapshots.
# ---------------------------------------------------------------------------


class Snapshot:
    """Selected elements captured from a bmesh (local coordinates)."""

    def __init__(self, verts, edges, faces):
        # verts: {index: Vector}; edges: [(i, j)]; faces: [[indices]]
        self.verts = dict(verts)
        self.edges = list(edges)
        self.faces = [list(face) for face in faces]

    def __len__(self):
        return len(self.verts)


def capture_snapshot(bm, vert_indices):
    """Capture verts + the edges/faces fully inside the vertex set."""
    from .geometry import refresh

    refresh(bm)
    wanted = set(vert_indices)
    verts = {v.index: v.co.copy() for v in bm.verts if v.index in wanted}
    edges = [
        (e.verts[0].index, e.verts[1].index)
        for e in bm.edges
        if e.verts[0].index in wanted and e.verts[1].index in wanted
    ]
    faces = [
        [v.index for v in f.verts]
        for f in bm.faces
        if all(v.index in wanted for v in f.verts)
    ]
    return Snapshot(verts, edges, faces)


def selection_vert_indices(bm):
    """Vertex indices covered by the current selection (verts, edges,
    faces all contribute their vertices)."""
    from .geometry import refresh

    refresh(bm)
    indices = set()
    for vert in bm.verts:
        if vert.select:
            indices.add(vert.index)
    for edge in bm.edges:
        if edge.select:
            indices.add(edge.verts[0].index)
            indices.add(edge.verts[1].index)
    for face in bm.faces:
        if face.select:
            for vert in face.verts:
                indices.add(vert.index)
    return indices


def duplicate_snapshot(bm, snapshot, matrix):
    """Create fresh verts/edges/faces from a snapshot transformed by
    a Matrix. Returns {old_index: new_vert}."""
    from .geometry import refresh

    refresh(bm)
    mapping = {}
    for index, co in snapshot.verts.items():
        mapping[index] = bm.verts.new(matrix @ co)
    refresh(bm)
    for i, j in snapshot.edges:
        v1, v2 = mapping[i], mapping[j]
        if v1 is not v2 and bm.edges.get((v1, v2)) is None:
            bm.edges.new((v1, v2))
    refresh(bm)
    for loop in snapshot.faces:
        loop_verts = [mapping[i] for i in loop]
        if len(loop_verts) >= 3 and bm.faces.get(tuple(loop_verts)) is None:
            try:
                bm.faces.new(tuple(loop_verts))
            except ValueError:
                pass
    refresh(bm)
    return mapping


def move_snapshot_verts(bm, snapshot, matrix):
    """Move the snapshot's own verts in place (stretch semantics:
    unselected connected geometry stays, faces deform)."""
    from .geometry import refresh

    refresh(bm)
    for index, co in snapshot.verts.items():
        bm.verts[index].co = matrix @ co


# ---------------------------------------------------------------------------
# Small 3D math.
# ---------------------------------------------------------------------------


def closest_point_between_lines(p1, d1, p2, d2):
    """Closest points on two lines; returns (point_on_1, point_on_2)
    or None when the lines are parallel."""
    d1 = Vector(d1).normalized()
    d2 = Vector(d2).normalized()
    r = Vector(p1) - Vector(p2)
    a = d1.dot(d1)
    b = d1.dot(d2)
    c = d1.dot(r)
    d = d2.dot(d2)
    e = d2.dot(r)
    denom = a * d - b * b
    if abs(denom) < 1e-12:
        return None
    t1 = (b * e - c * d) / denom
    t2 = (a * e - b * c) / denom
    return Vector(p1) + d1 * t1, Vector(p2) + d2 * t2


def ray_line_distance(ray_origin, ray_dir, line_point, line_dir):
    """Signed distance along line_dir of the ray's closest approach
    to the line, or None when ray and line are parallel."""
    found = closest_point_between_lines(ray_origin, ray_dir, line_point, line_dir)
    if found is None:
        return None
    _ray_point, line_point_hit = found
    return (line_point_hit - Vector(line_point)).dot(Vector(line_dir).normalized())


def rotation_matrix(center, axis, angle_degrees):
    """4x4 rotation about an axis through a center point."""
    rot = Matrix.Rotation(math.radians(angle_degrees), 4, Vector(axis).normalized())
    to_origin = Matrix.Translation(-Vector(center))
    back = Matrix.Translation(Vector(center))
    return back @ rot @ to_origin


def scale_matrix(pivot, factors):
    """4x4 scale about a pivot; factors = (fx, fy, fz)."""
    scale = Matrix.Diagonal((factors[0], factors[1], factors[2], 1.0))
    to_origin = Matrix.Translation(-Vector(pivot))
    back = Matrix.Translation(Vector(pivot))
    return back @ scale @ to_origin


def mirror_matrix(point, axis):
    """4x4 mirror across the plane through `point` with normal `axis`."""
    n = Vector(axis).normalized()
    mirror = Matrix.Identity(4)
    for i in range(3):
        for j in range(3):
            mirror[i][j] -= 2.0 * n[i] * n[j]
    to_origin = Matrix.Translation(-Vector(point))
    back = Matrix.Translation(Vector(point))
    return back @ mirror @ to_origin


def face_is_planar(face, tolerance=1e-4):
    """True when all face verts lie in the Newell plane."""
    verts = [v.co for v in face.verts]
    if len(verts) <= 3:
        return True
    normal = face.normal
    if normal.length < 1e-9:
        return True
    origin = verts[0]
    for co in verts[1:]:
        if abs((co - origin).dot(normal)) > tolerance:
            return False
    return True


def autofold_nonplanar(bm, faces):
    """Triangulate faces that became non-planar (SketchUp Autofold
    approximation: one diagonal per quad, fan for n-gons)."""
    import bmesh

    from .geometry import refresh

    refresh(bm)
    targets = [f for f in faces if f.is_valid and not face_is_planar(f)]
    if targets:
        bmesh.ops.triangulate(bm, faces=targets)
        refresh(bm)
    return len(targets)


def bbox_of_points(points):
    """(min, max) Vector pair for an iterable of 3D points."""
    points = [Vector(p) for p in points]
    low = Vector(
        (min(p.x for p in points), min(p.y for p in points), min(p.z for p in points))
    )
    high = Vector(
        (max(p.x for p in points), max(p.y for p in points), max(p.z for p in points))
    )
    return low, high


# ---------------------------------------------------------------------------
# 2D polygon offset (plane coordinates).
# ---------------------------------------------------------------------------


def _line_intersection_2d(p1, d1, p2, d2):
    denom = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(denom) < 1e-12:
        return None
    diff = (p2[0] - p1[0], p2[1] - p1[1])
    t = (diff[0] * d2[1] - diff[1] * d2[0]) / denom
    return (p1[0] + t * d1[0], p1[1] + t * d1[1])


def offset_polygon_2d(points, distance, closed=True):
    """Miter-join offset of a 2D polyline/polygon.

    Points are (u, v) tuples. Positive distance offsets to the LEFT
    of each directed segment. Returns the offset points (same count
    for closed loops; open chains keep their end count with square
    caps) or None when the input is degenerate.
    """
    pts = [(float(p[0]), float(p[1])) for p in points]
    count = len(pts)
    if count < 2:
        return None
    segments = []
    segment_count = count if closed else count - 1
    for i in range(segment_count):
        a = pts[i]
        b = pts[(i + 1) % count]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < 1e-12:
            return None
        # Left normal of the directed segment.
        nx, ny = -dy / length, dx / length
        segments.append(((a[0] + nx * distance, a[1] + ny * distance), (dx / length, dy / length)))
    if closed:
        out = []
        for i in range(count):
            prev = segments[i - 1]
            curr = segments[i]
            hit = _line_intersection_2d(prev[0], prev[1], curr[0], curr[1])
            if hit is None:
                hit = curr[0]
            out.append(hit)
        return out
    out = [segments[0][0]]
    for i in range(1, count - 1):
        prev = segments[i - 1]
        curr = segments[i]
        hit = _line_intersection_2d(prev[0], prev[1], curr[0], curr[1])
        if hit is None:
            hit = curr[0]
        out.append(hit)
    last = segments[-1]
    end = pts[-1]
    # Square cap: extend the last offset line to the end point's offset.
    dx, dy = last[1]
    nx, ny = -dy, dx
    out.append((end[0] + nx * distance, end[1] + ny * distance))
    return out


def polygon_signed_area_2d(points):
    """Signed area; positive = counter-clockwise."""
    area = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        area += x1 * y2 - x2 * y1
    return area / 2.0
