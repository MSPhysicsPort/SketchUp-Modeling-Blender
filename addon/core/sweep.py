"""Follow Me sweep math (pure 3D, no Blender deps): order a path
edge-chain, build parallel-transport frames, and sweep a profile
loop along the path with miter planes at joints.

Corner handling is our own defined algorithm (miter planes +
extension clamp); the official docs do not specify it.
"""

import math

from mathutils import Matrix, Vector

# Miter extension clamp: a ring point may not extend further than
# this multiple of the profile's bounding radius from the path
# vertex, avoiding runaway spikes at sharp corners.
MAX_MITER_RATIO = 4.0


def order_path(points_edges):
    """Order an edge chain into a point list.

    points_edges: list of (point_a, point_b) coordinate pairs.
    Returns (ordered_points, closed) or None when the edges do not
    form a single continuous chain.
    """
    if not points_edges:
        return None
    # Deduplicate vertices by rounded coordinates.
    def key(point):
        return (round(point[0], 6), round(point[1], 6), round(point[2], 6))

    adjacency = {}
    coords = {}
    for a, b in points_edges:
        ka, kb = key(a), key(b)
        coords[ka] = Vector(a)
        coords[kb] = Vector(b)
        adjacency.setdefault(ka, []).append(kb)
        adjacency.setdefault(kb, []).append(ka)
    endpoints = [k for k, neighbours in adjacency.items() if len(neighbours) == 1]
    if len(endpoints) == 0:
        start = next(iter(adjacency))
        closed = True
    elif len(endpoints) == 2:
        start = endpoints[0]
        closed = False
    else:
        return None
    ordered = [start]
    previous = None
    current = start
    while True:
        neighbours = [n for n in adjacency[current] if n != previous]
        if not neighbours:
            break
        nxt = neighbours[0]
        if nxt == start:
            break
        ordered.append(nxt)
        previous, current = current, nxt
        if len(ordered) > len(adjacency) + 1:
            return None
    if len(ordered) != len(adjacency):
        return None
    return [coords[k] for k in ordered], closed


def _rotation_between(v_from, v_to):
    """Minimal rotation matrix taking v_from to v_to."""
    a = Vector(v_from).normalized()
    b = Vector(v_to).normalized()
    dot = max(-1.0, min(1.0, a.dot(b)))
    if dot > 1.0 - 1e-9:
        return Matrix.Identity(3)
    if dot < -1.0 + 1e-9:
        # 180 degrees: pick any perpendicular axis.
        axis = a.cross(Vector((1, 0, 0)))
        if axis.length < 1e-6:
            axis = a.cross(Vector((0, 1, 0)))
        return Matrix.Rotation(math.pi, 3, axis.normalized())
    axis = a.cross(b)
    return Matrix.Rotation(math.acos(dot), 3, axis.normalized())


def _line_plane_hit(point, direction, plane_point, plane_normal):
    denom = Vector(direction).dot(plane_normal)
    if abs(denom) < 1e-12:
        return None
    t = (Vector(plane_point) - Vector(point)).dot(plane_normal) / denom
    return Vector(point) + Vector(direction) * t


def sweep_segment(profile_points, profile_normal, pivot, direction, length):
    """One straight sweep segment (manual Follow Me).

    Ring 0 is the profile exactly as-is; ring 1 is the profile
    rotated (normal -> direction) about ``pivot`` and translated
    along ``direction`` by ``length``. Returns (ring1_points,
    side_quads) with quads indexed into the flattened
    profile+ring1 vertex list.
    """
    profile = [Vector(p) for p in profile_points]
    direction = Vector(direction).normalized()
    rotation = _rotation_between(profile_normal, direction)
    pivot = Vector(pivot)
    ring1 = [pivot + rotation @ (p - pivot) + direction * length for p in profile]
    count = len(profile)
    quads = [
        (j, (j + 1) % count, count + (j + 1) % count, count + j)
        for j in range(count)
    ]
    return ring1, quads


def sweep_profile(profile_points, profile_normal, path_points, closed_path):
    """Sweep a profile loop along a path.

    profile_points: ordered loop (world coords); profile_normal:
    the profile plane normal; path_points: ordered path vertices.
    Returns (rings, side_quads) where rings[i] is the profile loop
    at path_points[i] (same vertex count/order as the profile) and
    side_quads are (a, b, c, d) index tuples into the flattened
    ring vertex list. The caller builds caps.
    """
    profile = [Vector(p) for p in profile_points]
    path = [Vector(p) for p in path_points]
    if len(profile) < 3 or len(path) < 2:
        return None
    profile_center = sum(profile, Vector()) / len(profile)
    profile_radius = max((p - profile_center).length for p in profile) or 1.0
    # Segment tangents.
    tangents = []
    seg_count = len(path) if closed_path else len(path) - 1
    for i in range(seg_count):
        a = path[i]
        b = path[(i + 1) % len(path)]
        direction = b - a
        if direction.length < 1e-9:
            return None
        tangents.append(direction.normalized())
    # Initial frame: rotate the profile so its normal aligns with
    # the first tangent, about the first path point.
    initial = _rotation_between(profile_normal, tangents[0])
    base_ring = [path[0] + initial @ (p - profile_center) for p in profile]
    # Parallel-transport the frame along the path.
    frames = [initial]
    for i in range(1, seg_count):
        frames.append(_rotation_between(tangents[i - 1], tangents[i]) @ frames[-1])
    # Rings at each path vertex, cut by miter planes.
    rings = []
    ring_count = len(path)
    for i in range(ring_count):
        if closed_path:
            tangent_in = tangents[i - 1]
            tangent_out = tangents[i]
            miter_normal = (tangent_in + tangent_out).normalized()
            frame = frames[i]
        elif i == 0:
            miter_normal = tangents[0]
            frame = frames[0]
        elif i == ring_count - 1:
            miter_normal = tangents[-1]
            frame = frames[-1]
        else:
            miter_normal = (tangents[i - 1] + tangents[i]).normalized()
            frame = frames[i]
        # Profile points in this frame, then projected onto the
        # miter plane along the outgoing (or incoming) tangent.
        direction = tangents[i] if (closed_path or i < ring_count - 1) else tangents[-1]
        ring = []
        for p in profile:
            moved = path[i] + frame @ (p - profile_center)
            hit = _line_plane_hit(moved, direction, path[i], miter_normal)
            if hit is None:
                hit = moved
            # Clamp runaway miter extensions.
            if (hit - path[i]).length > profile_radius * MAX_MITER_RATIO:
                hit = path[i] + (hit - path[i]).normalized() * profile_radius * MAX_MITER_RATIO
            ring.append(hit)
        rings.append(ring)
    # Side quads between consecutive rings.
    side_quads = []
    profile_count = len(profile)
    quad_segments = ring_count if closed_path else ring_count - 1
    for i in range(quad_segments):
        ring_a = i
        ring_b = (i + 1) % ring_count
        for j in range(profile_count):
            j_next = (j + 1) % profile_count
            side_quads.append(
                (
                    ring_a * profile_count + j,
                    ring_a * profile_count + j_next,
                    ring_b * profile_count + j_next,
                    ring_b * profile_count + j,
                )
            )
    return rings, side_quads
