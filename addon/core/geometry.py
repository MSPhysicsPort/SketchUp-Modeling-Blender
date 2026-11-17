"""Face creation / healing engine (bmesh, Blender-only, T2-tested).

SketchUp semantics implemented here (research/02 §2):
- joining edges into a closed, coplanar loop creates a face;
- drawing across a face splits it;
- deleting an edge deletes its adjacent faces;
- deleting a divider heals the face back into one;
- a new edge crossing existing edges splits them at the crossing.

Blender/bmesh has no automatic face creation, so every geometric
edit runs through this module. Functions take a BMesh and mutate it
in place; callers own the edit-mesh / object-mesh sync.

Known P1 limitations (honest, see proposal §3.2):
- A closed loop drawn fully INSIDE an existing face creates an
  overlapping inner face; the ring/disk split needs the logical-face
  model of P4 (Blender faces cannot have holes).
- Plane fitting for cycle detection tries a few vertex triples; a
  component whose loops lie on several different planes is only
  healed on the first fitting plane per seed component.
"""

import bmesh
from mathutils import Vector

try:
    from .inference import segment_segment_closest, segments_intersect_2d
except ImportError:  # Standalone import (core/ directory on sys.path).
    from inference import segment_segment_closest, segments_intersect_2d

# Configurable tolerances (meters). The 0.001-inch cleanup threshold
# is community lore, not official: no official number is encoded.
MERGE_DISTANCE = 1e-5
PLANAR_TOLERANCE = 1e-4
MIN_FACE_AREA = 1e-12

# Edge flags stored in the "su_flags" int layer (research/02 §5.3).
FLAG_SOFT = 1
FLAG_HIDDEN = 2

EDGE_FLAGS_LAYER = "su_flags"
FACE_ID_LAYER = "su_face_id"


def ensure_layers(bm):
    """Create custom layers if missing. MUST be called before any
    element access in an operation: creating a layer invalidates
    previously fetched element wrappers (probe-verified)."""
    edge_layer = bm.edges.layers.int.get(EDGE_FLAGS_LAYER)
    if edge_layer is None:
        edge_layer = bm.edges.layers.int.new(EDGE_FLAGS_LAYER)
    face_layer = bm.faces.layers.int.get(FACE_ID_LAYER)
    if face_layer is None:
        face_layer = bm.faces.layers.int.new(FACE_ID_LAYER)
    return edge_layer, face_layer


def refresh(bm):
    """Rebuild indices and lookup tables after topology changes.

    `ensure_lookup_table()` alone does NOT assign `.index` (probe:
    indices stay -1); `index_update()` must run first.
    """
    bm.verts.index_update()
    bm.edges.index_update()
    bm.faces.index_update()
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()


def find_vert_near(bm, co, tol=MERGE_DISTANCE):
    target = Vector(co)
    best = None
    best_dist = tol
    for vert in bm.verts:
        dist = (vert.co - target).length
        if dist <= best_dist:
            best = vert
            best_dist = dist
    return best


def get_or_create_vert(bm, co, tol=MERGE_DISTANCE):
    found = find_vert_near(bm, co, tol)
    if found is not None:
        return found
    return bm.verts.new(Vector(co))


def _edge_param(edge, point):
    a, b = edge.verts[0].co, edge.verts[1].co
    ab = b - a
    denom = ab.length_squared
    if denom == 0.0:
        return 0.0
    return (Vector(point) - a).dot(ab) / denom


def _point_on_edge_distance(point, edge):
    a, b = edge.verts[0].co, edge.verts[1].co
    ab = b - a
    denom = ab.length_squared
    if denom == 0.0:
        return (Vector(point) - a).length, 0.0
    t = (Vector(point) - a).dot(ab) / denom
    t_clamped = max(0.0, min(1.0, t))
    closest = a + ab * t_clamped
    return (Vector(point) - closest).length, t


def point_on_edge_distance(point, edge):
    """Public alias: (distance, t) of a point to an edge segment."""
    return _point_on_edge_distance(point, edge)


def find_edge_containing(bm, point, direction, tol=MERGE_DISTANCE):
    """Find a live edge whose interior contains the point and whose
    direction is parallel to the given direction."""
    target = Vector(point)
    direction = Vector(direction).normalized()
    for edge in bm.edges:
        dist, t = _point_on_edge_distance(target, edge)
        if dist > tol or t <= 1e-6 or t >= 1.0 - 1e-6:
            continue
        edge_dir = (edge.verts[1].co - edge.verts[0].co).normalized()
        if abs(edge_dir.dot(direction)) > 1.0 - 1e-6:
            return edge
    return None


def split_edge_at_point(bm, edge, point, tol=MERGE_DISTANCE):
    """Split one edge at an interior point; returns the live sub-edges
    (empty list when the point is at/near an endpoint)."""
    if not edge.is_valid:
        return []
    target = Vector(point)
    dist, t = _point_on_edge_distance(target, edge)
    if dist > tol or t <= 1e-6 or t >= 1.0 - 1e-6:
        return [edge]
    bmesh.ops.bisect_edges(bm, edges=[edge], cuts=1, edge_percents={edge: t})
    refresh(bm)
    # The two sub-edges are the edges incident to the new vertex that
    # lie on the original line; find them by position.
    new_vert = find_vert_near(bm, target, tol)
    if new_vert is None:
        return []
    return [link for link in new_vert.link_edges if link.is_valid]


def _weld_at(bm, point, tol=MERGE_DISTANCE):
    """Merge all vertices within tolerance of a point into one."""
    target = Vector(point)
    near = [v for v in bm.verts if (v.co - target).length <= tol]
    if len(near) < 2:
        return 0
    keeper = near[0]
    bmesh.ops.weld_verts(bm, targetmap={v: keeper for v in near[1:]})
    refresh(bm)
    return len(near) - 1


def split_edges_at_crossings(bm, edge, tol=MERGE_DISTANCE):
    """Split `edge` and every edge it crosses; returns
    (live edges covering the new segment, split count).

    A crossing splits the OTHER edge when the point is interior to
    it (even at the new edge's endpoint: the T-junction case), and
    splits the NEW edge when the point is interior to it. Duplicate
    vertices created by bisecting at the same point are welded.
    """
    if not edge.is_valid:
        return [], 0
    origin = Vector(edge.verts[0].co)
    end = Vector(edge.verts[1].co)
    direction = end - origin
    if direction.length < tol:
        return [edge], 0
    direction.normalize()
    splits = 0

    # Collect crossings against a snapshot of the other edges.
    # (point, t_on_edge, other_edge, t_on_other, other_dir,
    #  split_other, split_self)
    crossings = []
    for other in list(bm.edges):
        if other is edge or not other.is_valid:
            continue
        _, _, dist, pa, _ = segment_segment_closest(
            tuple(origin), tuple(end),
            tuple(other.verts[0].co), tuple(other.verts[1].co),
        )
        if dist > tol:
            continue
        t_edge = _edge_param(edge, pa)
        t_other = _edge_param(other, pa)
        split_other = 1e-6 < t_other < 1.0 - 1e-6
        split_self = 1e-6 < t_edge < 1.0 - 1e-6
        if not split_other and not split_self:
            continue
        crossings.append(
            (Vector(pa), t_edge, other, t_other,
             other.verts[1].co - other.verts[0].co, split_other, split_self)
        )
    # Vertices lying on the new segment's interior split it.
    for vert in list(bm.verts):
        if vert in edge.verts:
            continue
        dist, t = _point_on_edge_distance(vert.co, edge)
        if dist <= tol and 1e-6 < t < 1.0 - 1e-6:
            crossings.append((Vector(vert.co), t, None, None, None, False, True))

    # Split the other edges first (re-locate the live sub-edge for
    # repeated crossings on the same original edge).
    for point, _t_edge, other, t_other, other_dir, split_other, _split_self in crossings:
        if other is None or not split_other:
            continue
        if t_other <= 1e-6 or t_other >= 1.0 - 1e-6:
            continue
        live = other if other.is_valid else find_edge_containing(bm, point, other_dir, tol)
        if live is not None and live.is_valid:
            before = len(bm.edges)
            split_edge_at_point(bm, live, point, tol)
            if len(bm.edges) > before:
                splits += 1

    # Split the new edge itself at every interior crossing point,
    # processing points in order along the segment.
    self_points = sorted(
        {tuple(p) for p, _t, _o, _to, _d, _so, ss in crossings if ss},
        key=lambda p: _edge_param(edge, p) if edge.is_valid else 0.0,
    )
    live_edges = [edge] if edge.is_valid else []
    for point in self_points:
        target = Vector(point)
        live = None
        for candidate in live_edges:
            if candidate.is_valid:
                dist, t = _point_on_edge_distance(target, candidate)
                if dist <= tol and 1e-6 < t < 1.0 - 1e-6:
                    live = candidate
                    break
        if live is None:
            live = find_edge_containing(bm, target, direction, tol)
        if live is None:
            continue
        before = len(bm.edges)
        subs = split_edge_at_point(bm, live, target, tol)
        if len(bm.edges) > before:
            splits += 1
        if live in live_edges:
            live_edges.remove(live)
        live_edges.extend(s for s in subs if s.is_valid)

    # Weld duplicate vertices created at shared crossing points.
    for point in {tuple(p) for p, *_rest in crossings}:
        _weld_at(bm, Vector(point), tol)

    # Recompute the live covering: every edge collinear with the new
    # segment whose endpoints lie within its bounds (computed against
    # the original segment coordinates: the original edge object may
    # have been replaced by the splits).
    seg_length = (end - origin).length
    live_edges = []
    for candidate in bm.edges:
        ok = True
        for vert in candidate.verts:
            delta = vert.co - origin
            along = delta.dot(direction)
            closest = origin + direction * along
            if (vert.co - closest).length > tol:
                ok = False
                break
            t = along / seg_length
            if t < -1e-6 or t > 1.0 + 1e-6:
                ok = False
                break
        if ok:
            live_edges.append(candidate)
    return live_edges, splits


# ---------------------------------------------------------------------------
# Cycle detection / face healing.
#
# Approach: enumerate simple cycles per connected component (DFS,
# bounded), keep planar cycles with no chord (a chord means smaller
# faces already cover the loop, e.g. a square with a diagonal yields
# two triangles, not the square). Each cycle is checked for
# planarity individually, so multi-plane wireframes (cube, pyramid)
# heal correctly — a single component-level plane fit cannot do that.
# ---------------------------------------------------------------------------

MAX_CYCLE_LENGTH = 16
MAX_CYCLES_PER_COMPONENT = 1000
MAX_DFS_STEPS_PER_COMPONENT = 20000


def _enumerate_cycles(adjacency):
    """Enumerate simple cycles (lists of vertex indices).

    Each cycle is found once per direction; callers dedupe by vertex
    set. Bounded by MAX_CYCLE_LENGTH / MAX_CYCLES / MAX_DFS_STEPS.
    """
    cycles = []
    steps = [0]

    def dfs(start, current, path, in_path):
        if len(cycles) >= MAX_CYCLES_PER_COMPONENT:
            return
        for neighbor in sorted(adjacency.get(current, ())):
            steps[0] += 1
            if steps[0] > MAX_DFS_STEPS_PER_COMPONENT:
                return
            if neighbor == start:
                if len(path) >= 3:
                    cycles.append(list(path))
                continue
            if neighbor <= start or neighbor in in_path:
                continue
            if len(path) >= MAX_CYCLE_LENGTH:
                continue
            in_path.add(neighbor)
            path.append(neighbor)
            dfs(start, neighbor, path, in_path)
            path.pop()
            in_path.discard(neighbor)
            if len(cycles) >= MAX_CYCLES_PER_COMPONENT:
                return

    for start in sorted(adjacency):
        dfs(start, start, [start], {start})
        if len(cycles) >= MAX_CYCLES_PER_COMPONENT:
            break
    return cycles


def _cycle_plane(points):
    """Plane through a cycle's points; None when degenerate."""
    origin = points[0]
    for i in range(1, len(points)):
        for j in range(i + 1, len(points)):
            normal = (points[i] - origin).cross(points[j] - origin)
            if normal.length > 1e-12:
                normal.normalize()
                if all(abs((p - origin).dot(normal)) <= PLANAR_TOLERANCE for p in points):
                    return origin, normal
                return None
    return None


def _cycle_has_chord(cycle, adjacency):
    n = len(cycle)
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if cycle[j] in adjacency.get(cycle[i], ()):
                return True
    return False


def _cycle_self_intersects(points_2d, cycle):
    """True when two non-adjacent cycle edges cross in 2D."""
    n = len(cycle)
    for i in range(n):
        a1, a2 = points_2d[cycle[i]], points_2d[cycle[(i + 1) % n]]
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            b1, b2 = points_2d[cycle[j]], points_2d[cycle[(j + 1) % n]]
            if segments_intersect_2d(a1, a2, b1, b2) is not None:
                return True
    return False


def _newell_normal(points):
    normal = Vector((0.0, 0.0, 0.0))
    for i in range(len(points)):
        a, b = points[i], points[(i + 1) % len(points)]
        normal.x += (a.y - b.y) * (a.z + b.z)
        normal.y += (a.z - b.z) * (a.x + b.x)
        normal.z += (a.x - b.x) * (a.y + b.y)
    return normal


def heal_faces(bm, seed_edges=None, tol=MERGE_DISTANCE):
    """Create faces for closed coplanar loops; returns new faces.

    seed_edges: edges whose connected components are (re)checked, or
    None for the whole mesh. Faces whose vertex set already exists
    are skipped. New face normals use a deterministic sign rule
    (dominant axis component positive).
    """
    ensure_layers(bm)
    refresh(bm)
    if seed_edges is None:
        seed_edges = list(bm.edges)
    else:
        seed_edges = [e for e in seed_edges if e.is_valid]
    if not seed_edges:
        return []

    all_edges = list(bm.edges)
    adjacency = {}
    for edge in all_edges:
        a, b = edge.verts[0].index, edge.verts[1].index
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    seed_verts = {v.index for e in seed_edges for v in e.verts}
    seen = set()
    components = []
    for start in sorted(adjacency):
        if start in seen:
            continue
        stack = [start]
        component = set()
        while stack:
            node = stack.pop()
            if node in component:
                continue
            component.add(node)
            seen.add(node)
            stack.extend(adjacency.get(node, ()))
        if component & seed_verts:
            components.append(component)

    vert_by_index = {v.index: v for v in bm.verts}
    existing = {frozenset(v.index for v in face.verts) for face in bm.faces}
    created = []

    for component in components:
        if len(component) < 3:
            continue
        sub_adjacency = {
            i: {nb for nb in adjacency[i] if nb in component} for i in component
        }
        tried = set()
        for cycle in _enumerate_cycles(sub_adjacency):
            key = frozenset(cycle)
            if key in tried or key in existing:
                continue
            tried.add(key)
            if _cycle_has_chord(cycle, sub_adjacency):
                continue
            points = [vert_by_index[i].co for i in cycle]
            fitted = _cycle_plane(points)
            if fitted is None:
                continue
            origin, normal = fitted
            # 2D projection for area / self-intersection checks.
            u = None
            for i in range(1, len(points)):
                delta = points[i] - origin
                if delta.length > 1e-12:
                    u = delta.normalized()
                    break
            if u is None:
                continue
            v = normal.cross(u).normalized()
            points_2d = {}
            for i, point in zip(cycle, points):
                delta = point - origin
                points_2d[i] = (delta.dot(u), delta.dot(v))
            area = 0.0
            for i in range(len(cycle)):
                x1, y1 = points_2d[cycle[i]]
                x2, y2 = points_2d[cycle[(i + 1) % len(cycle)]]
                area += x1 * y2 - x2 * y1
            if abs(area * 0.5) <= MIN_FACE_AREA:
                continue
            if _cycle_self_intersects(points_2d, cycle):
                continue
            # Orient: Newell normal's dominant component positive.
            newell = _newell_normal(points)
            dominant = max(range(3), key=lambda k: abs(newell[k]))
            if newell[dominant] < 0:
                cycle = list(reversed(cycle))
                points = [vert_by_index[i].co for i in cycle]
            verts = [vert_by_index[i] for i in cycle]
            try:
                face = bm.faces.new(verts)
            except ValueError:
                continue
            existing.add(key)
            created.append(face)
    if created:
        bm.normal_update()
    return created


# ---------------------------------------------------------------------------
# Public editing operations.
# ---------------------------------------------------------------------------


def apply_line(bm, p1, p2, tol=MERGE_DISTANCE):
    """Add one edge between two points (SketchUp Line semantics).

    Welds endpoints to nearby vertices, splits crossed edges, splits
    shared faces, and heals new faces. Returns a summary dict.
    """
    ensure_layers(bm)
    co1, co2 = Vector(p1), Vector(p2)
    if (co1 - co2).length < tol:
        return {"status": "degenerate", "edges": [], "faces": [], "splits": 0}
    v1 = get_or_create_vert(bm, co1, tol)
    v2 = get_or_create_vert(bm, co2, tol)
    if v1 == v2:
        return {"status": "degenerate", "edges": [], "faces": [], "splits": 0}
    existing = bm.edges.get((v1, v2))
    if existing is not None:
        return {"status": "exists", "edges": [existing], "faces": [], "splits": 0}
    shared = set(v1.link_faces) & set(v2.link_faces)
    if shared:
        result = bmesh.ops.connect_verts(bm, verts=[v1, v2])
        new_edges = [e for e in result["edges"] if e.is_valid]
        if not new_edges:
            new_edges = [bm.edges.new((v1, v2))]
    else:
        new_edges = [bm.edges.new((v1, v2))]
    refresh(bm)
    splits = 0
    live_edges = []
    for edge in new_edges:
        if not edge.is_valid:
            continue
        live, count = split_edges_at_crossings(bm, edge, tol)
        splits += count
        live_edges.extend(live)
    created = heal_faces(bm, seed_edges=live_edges, tol=tol)
    bm.normal_update()
    return {"status": "ok", "edges": live_edges, "faces": created, "splits": splits}


def delete_edge(bm, edge, heal=True, tol=MERGE_DISTANCE):
    """Delete an edge and its adjacent faces (Eraser semantics);
    optionally heal the surrounding loops back into faces."""
    ensure_layers(bm)
    if not edge.is_valid:
        return {"status": "invalid", "faces_removed": 0, "faces": []}
    faces_removed = len(edge.link_faces)
    neighbor_verts = {v.index for v in edge.verts}
    for face in list(edge.link_faces):
        for vert in face.verts:
            neighbor_verts.add(vert.index)
    bmesh.ops.delete(bm, geom=[edge], context="EDGES")
    refresh(bm)
    created = []
    if heal:
        seed = [
            e
            for e in bm.edges
            if e.verts[0].index in neighbor_verts or e.verts[1].index in neighbor_verts
        ]
        created = heal_faces(bm, seed_edges=seed, tol=tol)
    bm.normal_update()
    return {"status": "ok", "faces_removed": faces_removed, "faces": created}


def delete_face_only(bm, face):
    """Delete a face but keep its boundary edges (right-click Erase)."""
    ensure_layers(bm)
    if not face.is_valid:
        return False
    bm.faces.remove(face)
    bm.normal_update()
    return True


def edge_flags(bm, edge):
    layer = bm.edges.layers.int.get(EDGE_FLAGS_LAYER)
    if layer is None:
        return 0
    return edge[layer]


def set_edge_flags(bm, edge, soft=None, hidden=None):
    """Set Soft / Hidden flags; Soft also smooths the edge and its
    adjacent faces (Eraser+Ctrl = Soft+Smooth).

    The edge is re-fetched by vertex coordinates: ensure_layers()
    may create the flag layer, which invalidates element wrappers
    fetched before the call (including ``edge`` itself).
    """
    try:
        coords = (edge.verts[0].co.copy(), edge.verts[1].co.copy())
    except ReferenceError:
        return None
    ensure_layers(bm)
    refresh(bm)
    v1 = find_vert_near(bm, coords[0])
    v2 = find_vert_near(bm, coords[1])
    if v1 is None or v2 is None:
        return None
    live = bm.edges.get((v1, v2))
    if live is None:
        return None
    layer = bm.edges.layers.int.get(EDGE_FLAGS_LAYER)
    flags = live[layer]
    if soft is not None:
        flags = (flags | FLAG_SOFT) if soft else (flags & ~FLAG_SOFT)
        live.smooth = bool(soft)
        for face in live.link_faces:
            face.smooth = bool(soft)
    if hidden is not None:
        flags = (flags | FLAG_HIDDEN) if hidden else (flags & ~FLAG_HIDDEN)
        live.hide = bool(hidden)
    live[layer] = flags
    return flags


def clear_edge_flags(bm, edge):
    """Remove Soft / Hidden flags (Eraser+Alt per QRC 2025; the
    Ctrl+Shift claim is the D14 conflict, unverified)."""
    return set_edge_flags(bm, edge, soft=False, hidden=False)


def is_soft(bm, edge):
    return bool(edge_flags(bm, edge) & FLAG_SOFT)


def is_hidden_edge(bm, edge):
    return bool(edge_flags(bm, edge) & FLAG_HIDDEN)


def flood_surface_faces(bm, seed_face):
    """Faces of the Surface containing ``seed_face``: flood across
    soft edges only (proposal §3.5). A face with no soft neighbors
    is a Surface of one."""
    seen = {seed_face.index}
    stack = [seed_face]
    while stack:
        face = stack.pop()
        for edge in face.edges:
            if not is_soft(bm, edge):
                continue
            for other in edge.link_faces:
                if other.index not in seen:
                    seen.add(other.index)
                    stack.append(other)
    return seen
