"""Triangle-triangle intersection for Intersect Faces (P4).

Pure segment math plus a bmesh driver: candidate pairs come from
BVHTree overlap (naive fallback), each pair yields intersection
segments (including the coplanar-overlap case), and the segments
are inserted with geometry.apply_line, which splits crossed edges
and heals faces.
"""

from mathutils import Vector

EPS = 1e-7


def _plane_basis(normal):
    n = Vector(normal).normalized()
    helper = Vector((1, 0, 0)) if abs(n.x) < 0.9 else Vector((0, 1, 0))
    u = n.cross(helper).normalized()
    v = n.cross(u)
    return u, v


def _segment_in_triangle(p0, p1, tri):
    """Clip a segment lying in the triangle's plane to the triangle.

    Liang-Barsky over the three half-planes. Returns (q0, q1) or
    None."""
    a, b, c = tri
    normal = (b - a).cross(c - a)
    if normal.length < 1e-12:
        return None
    u, v = _plane_basis(normal)
    origin = a

    def to2(p):
        d = p - origin
        return (d.dot(u), d.dot(v))

    t2 = [to2(p) for p in tri]
    s0, s1 = to2(p0), to2(p1)
    area = (t2[1][0] - t2[0][0]) * (t2[2][1] - t2[0][1]) - (
        t2[1][1] - t2[0][1]
    ) * (t2[2][0] - t2[0][0])
    if abs(area) < 1e-14:
        return None
    sign = 1.0 if area > 0 else -1.0
    t_lo, t_hi = 0.0, 1.0
    for i in range(3):
        e0, e1 = t2[i], t2[(i + 1) % 3]
        ex, ey = e1[0] - e0[0], e1[1] - e0[1]
        if sign > 0:
            nx, ny = -ey, ex
        else:
            nx, ny = ey, -ex
        f0 = (s0[0] - e0[0]) * nx + (s0[1] - e0[1]) * ny
        f1 = (s1[0] - e0[0]) * nx + (s1[1] - e0[1]) * ny
        if f0 < 0 and f1 < 0:
            return None
        if f0 >= 0 and f1 >= 0:
            continue
        t = f0 / (f0 - f1)
        if f0 < 0:
            t_lo = max(t_lo, t)
        else:
            t_hi = min(t_hi, t)
        if t_lo > t_hi:
            return None
    if t_hi - t_lo < 1e-12:
        return None
    q0 = p0 + (p1 - p0) * t_lo
    q1 = p0 + (p1 - p0) * t_hi
    if (q0 - q1).length < 1e-7:
        return None
    return (q0, q1)


def _coplanar_segments(tri_a, tri_b):
    """Boundary edges of the overlap polygon of two coplanar
    triangles (Sutherland-Hodgman in the shared plane)."""
    a, b = tri_a, tri_b
    normal = (b[1] - b[0]).cross(b[2] - b[0])
    if normal.length < 1e-12:
        return []
    u, v = _plane_basis(normal)
    origin = b[0]

    def to2(p):
        d = p - origin
        return (d.dot(u), d.dot(v))

    def to3(xy):
        return origin + u * xy[0] + v * xy[1]

    poly = [to2(p) for p in a]
    tri = [to2(p) for p in b]
    area = (tri[1][0] - tri[0][0]) * (tri[2][1] - tri[0][1]) - (
        tri[1][1] - tri[0][1]
    ) * (tri[2][0] - tri[0][0])
    if abs(area) < 1e-14:
        return []
    sign = 1.0 if area > 0 else -1.0
    for i in range(3):
        e0, e1 = tri[i], tri[(i + 1) % 3]
        ex, ey = e1[0] - e0[0], e1[1] - e0[1]
        if sign > 0:
            nx, ny = -ey, ex
        else:
            nx, ny = ey, -ex

        def dist(p):
            return (p[0] - e0[0]) * nx + (p[1] - e0[1]) * ny

        clipped = []
        for j, cur in enumerate(poly):
            nxt = poly[(j + 1) % len(poly)]
            f_cur, f_nxt = dist(cur), dist(nxt)
            if f_cur >= -1e-9:
                clipped.append(cur)
            if (f_cur < 0) != (f_nxt < 0):
                t = f_cur / (f_cur - f_nxt)
                clipped.append(
                    (cur[0] + (nxt[0] - cur[0]) * t,
                     cur[1] + (nxt[1] - cur[1]) * t)
                )
        poly = clipped
        if not poly:
            return []
    # Deduplicate consecutive points.
    cleaned = []
    for p in poly:
        if not cleaned or (abs(p[0] - cleaned[-1][0]) > 1e-9
                           or abs(p[1] - cleaned[-1][1]) > 1e-9):
            cleaned.append(p)
    if len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
        cleaned.pop()
    if len(cleaned) < 2:
        return []
    segments = []
    for i in range(len(cleaned)):
        p = to3(cleaned[i])
        q = to3(cleaned[(i + 1) % len(cleaned)])
        if (p - q).length > 1e-7:
            segments.append((p, q))
    return segments


def tri_tri_segments(tri_a, tri_b):
    """Intersection segments of two triangles (coordinate triples).
    Returns a list of (p, q) coordinate pairs, possibly empty."""
    a = [Vector(p) for p in tri_a]
    b = [Vector(p) for p in tri_b]
    nb = (b[1] - b[0]).cross(b[2] - b[0])
    if nb.length < 1e-12:
        return []
    nb.normalize()
    d = [(p - b[0]).dot(nb) for p in a]
    if all(x > EPS for x in d) or all(x < -EPS for x in d):
        return []
    if all(abs(x) <= EPS for x in d):
        return _coplanar_segments(a, b)
    points = []
    for i in range(3):
        j = (i + 1) % 3
        di, dj = d[i], d[j]
        if abs(di) <= EPS and abs(dj) <= EPS:
            points.extend((a[i], a[j]))
        elif di * dj < 0:
            t = di / (di - dj)
            points.append(a[i] + (a[j] - a[i]) * t)
        elif abs(di) <= EPS:
            points.append(a[i])
        elif abs(dj) <= EPS:
            points.append(a[j])
    unique = []
    for p in points:
        if all((p - q).length > 1e-7 for q in unique):
            unique.append(p)
    if len(unique) < 2:
        return []
    best = None
    best_len = 0.0
    for i in range(len(unique)):
        for j in range(i + 1, len(unique)):
            length = (unique[i] - unique[j]).length
            if length > best_len:
                best_len = length
                best = (unique[i], unique[j])
    if best is None:
        return []
    clipped = _segment_in_triangle(best[0], best[1], b)
    return [clipped] if clipped is not None else []


# ---------------------------------------------------------------------------
# Drivers.
# ---------------------------------------------------------------------------


def _overlap_pairs(target_tris, scope_tris):
    try:
        from mathutils.bvhtree import BVHTree

        def build(tris):
            verts = []
            polys = []
            for _key, tri in tris:
                base = len(verts)
                verts.extend(tri)
                polys.append((base, base + 1, base + 2))
            # Epsilon fattens the boxes so coplanar triangles (zero
            # overlap volume) still register as candidate pairs;
            # the exact math below filters false positives.
            return BVHTree.FromPolygons(verts, polys, epsilon=1e-4)

        return build(target_tris).overlap(build(scope_tris))
    except Exception:
        return [
            (i, j)
            for i in range(len(target_tris))
            for j in range(len(scope_tris))
        ]


def _segment_key(seg):
    def rounded(p):
        return (round(p[0], 6), round(p[1], 6), round(p[2], 6))

    a, b = rounded(seg[0]), rounded(seg[1])
    return (a, b) if a <= b else (b, a)


def _plane_group_pairs(target_tris, scope_tris):
    """Candidate pairs missed by BVHTree.overlap: exactly coplanar
    triangles have zero overlap volume, so they are grouped by
    plane (normal + distance) and filtered by 2D bbox overlap."""
    groups = {}

    def plane_key(tri):
        normal = (tri[1] - tri[0]).cross(tri[2] - tri[0])
        length = normal.length
        if length < 1e-12:
            return None
        normal = normal / length
        dominant = max(range(3), key=lambda k: abs(normal[k]))
        if normal[dominant] < 0:
            normal = -normal
        distance = normal.dot(tri[0])
        return (
            round(normal.x, 4),
            round(normal.y, 4),
            round(normal.z, 4),
            round(distance, 4),
        )

    def bbox_2d(tri, normal):
        u, v = _plane_basis(normal)
        origin = tri[0]
        pts = [((p - origin).dot(u), (p - origin).dot(v)) for p in tri]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    indexed = []
    for side, tris in (("t", target_tris), ("s", scope_tris)):
        for index, (_key, tri) in enumerate(tris):
            key = plane_key(tri)
            if key is None:
                continue
            normal = Vector((key[0], key[1], key[2]))
            indexed.append((side, index, key, bbox_2d(tri, normal)))
            groups.setdefault(key, []).append(len(indexed) - 1)
    pairs = []
    for members in groups.values():
        targets = [indexed[i] for i in members if indexed[i][0] == "t"]
        scopes = [indexed[i] for i in members if indexed[i][0] == "s"]
        for _s1, ti, _k1, box_t in targets:
            for _s2, si, _k2, box_s in scopes:
                if (
                    box_t[0] <= box_s[2] + 1e-6
                    and box_s[0] <= box_t[2] + 1e-6
                    and box_t[1] <= box_s[3] + 1e-6
                    and box_s[1] <= box_t[3] + 1e-6
                ):
                    pairs.append((ti, si))
    return pairs


def compute_intersection_segments(target_tris, scope_tris):
    """target_tris / scope_tris: lists of (key, (p0, p1, p2)).
    Pairs with equal keys (same source face) are skipped. Returns
    (deduplicated (p, q) segments, involved face keys)."""
    segments = []
    seen = set()
    involved = set()
    pairs = set(_overlap_pairs(target_tris, scope_tris))
    pairs.update(_plane_group_pairs(target_tris, scope_tris))
    for ti, si in pairs:
        key_t, tri_t = target_tris[ti]
        key_s, tri_s = scope_tris[si]
        if key_t == key_s:
            continue
        found = tri_tri_segments(tri_t, tri_s)
        if found:
            involved.add(key_t)
            involved.add(key_s)
        for seg in found:
            key = _segment_key(seg)
            if key not in seen:
                seen.add(key)
                segments.append(seg)
    return segments, involved


def _fan_tris(coords, key):
    return [
        (key, (coords[0], coords[k], coords[k + 1]))
        for k in range(1, len(coords) - 1)
    ]


def collect_scope_tris(bm, scope, context_obj):
    """Scope triangles in the edit-mesh local frame. MODEL adds
    other visible mesh objects, transformed into this frame."""
    from .geometry import refresh

    refresh(bm)
    tris = []
    for face in bm.faces:
        coords = [v.co.copy() for v in face.verts]
        tris.extend(_fan_tris(coords, ("local", face.index)))
    if scope == "MODEL" and context_obj is not None:
        import bpy

        inverse = context_obj.matrix_world.inverted()
        for obj in bpy.context.scene.objects:
            if obj is context_obj or obj.type != "MESH":
                continue
            try:
                if obj.hide_viewport or obj.hide_get():
                    continue
            except Exception:
                pass
            matrix = inverse @ obj.matrix_world
            mesh = obj.data
            for poly in mesh.polygons:
                coords = [matrix @ mesh.vertices[i].co for i in poly.vertices]
                tris.extend(_fan_tris(coords, ("ext", obj.name, poly.index)))
    return tris


def _point_in_polygon_2d(point, polygon):
    """Ray-casting point-in-polygon test (2D tuples)."""
    x, y = point
    inside = False
    count = len(polygon)
    for i in range(count):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % count]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                inside = not inside
    return inside


def _face_material_record(face):
    coords = [v.co.copy() for v in face.verts]
    normal = Vector(face.normal)
    u, v = _plane_basis(normal)
    origin = coords[0]
    polygon_2d = [((c - origin).dot(u), (c - origin).dot(v)) for c in coords]
    return {
        "normal": normal,
        "origin": origin,
        "u": u,
        "v": v,
        "polygon_2d": polygon_2d,
        "material_index": face.material_index,
    }


def _restore_materials(bm, records, survivor_keys):
    if not records:
        return
    for face in bm.faces:
        key = frozenset(
            (round(v.co.x, 6), round(v.co.y, 6), round(v.co.z, 6))
            for v in face.verts
        )
        if key in survivor_keys:
            continue
        center = face.calc_center_median()
        normal = Vector(face.normal)
        for record in records:
            if abs(normal.dot(record["normal"])) < 0.999:
                continue
            if abs((center - record["origin"]).dot(record["normal"])) > 1e-6:
                continue
            delta = center - record["origin"]
            point_2d = (delta.dot(record["u"]), delta.dot(record["v"]))
            if _point_in_polygon_2d(point_2d, record["polygon_2d"]):
                face.material_index = record["material_index"]
                break


def _remove_container_faces(bm, survivor_keys):
    """Delete rebuilt faces that strictly contain another rebuilt
    coplanar face: the healer's chord check misses dividers that
    run through an off-cycle vertex, so the outer loop is rebuilt
    alongside its split parts. Survivors (pre-existing faces) are
    never touched."""
    import bmesh

    from .geometry import refresh

    refresh(bm)
    new_faces = []
    for face in bm.faces:
        key = frozenset(
            (round(v.co.x, 6), round(v.co.y, 6), round(v.co.z, 6))
            for v in face.verts
        )
        if key not in survivor_keys:
            new_faces.append(face)
    doomed = set()
    for i, face_a in enumerate(new_faces):
        if face_a in doomed:
            continue
        normal_a = Vector(face_a.normal)
        origin_a = face_a.verts[0].co.copy()
        u, v = _plane_basis(normal_a)
        poly_a = [
            ((w.co - origin_a).dot(u), (w.co - origin_a).dot(v))
            for w in face_a.verts
        ]
        area_a = face_a.calc_area()
        for face_b in new_faces:
            if face_b is face_a or face_b in doomed:
                continue
            if abs(Vector(face_b.normal).dot(normal_a)) < 0.999:
                continue
            center_b = face_b.calc_center_median()
            if abs((center_b - origin_a).dot(normal_a)) > 1e-6:
                continue
            if face_b.calc_area() >= area_a * 0.999:
                continue
            delta = center_b - origin_a
            if _point_in_polygon_2d(
                (delta.dot(u), delta.dot(v)), poly_a
            ):
                doomed.add(face_a)
                break
    if doomed:
        bmesh.ops.delete(bm, geom=list(doomed), context="FACES_ONLY")
        refresh(bm)


def intersect_in_bmesh(bm, target_face_indices, scope, context_obj):
    """Intersect the target faces with the scope; insert the
    resulting edges into ``bm``. Faces crossed by an intersection
    segment are deleted and rebuilt by the healer (otherwise the
    original face survives as a duplicate over its split parts);
    their materials are restored onto the rebuilt faces. Returns
    the number of new edges added."""
    import bmesh

    from .geometry import apply_line, heal_faces, refresh

    refresh(bm)
    target_tris = []
    for face_index in target_face_indices:
        face = bm.faces[face_index]
        coords = [v.co.copy() for v in face.verts]
        target_tris.extend(_fan_tris(coords, ("local", face.index)))
    if scope == "SELECTION":
        scope_tris = list(target_tris)
    else:
        scope_tris = collect_scope_tris(bm, scope, context_obj)
    segments, involved = compute_intersection_segments(target_tris, scope_tris)
    if not segments:
        return 0
    # Delete crossed local faces (record materials first); their
    # boundary edges stay, so the healer rebuilds the split faces.
    records = []
    doomed = []
    for key in involved:
        if key[0] != "local":
            continue
        face = bm.faces[key[1]]
        records.append(_face_material_record(face))
        doomed.append(face)
    if doomed:
        bmesh.ops.delete(bm, geom=doomed, context="FACES_ONLY")
        refresh(bm)
    survivor_keys = {
        frozenset(
            (round(v.co.x, 6), round(v.co.y, 6), round(v.co.z, 6))
            for v in face.verts
        )
        for face in bm.faces
    }
    added = 0
    for p, q in segments:
        result = apply_line(bm, p, q)
        if result["status"] == "ok":
            added += 1
    heal_faces(bm)
    _remove_container_faces(bm, survivor_keys)
    _restore_materials(bm, records, survivor_keys)
    return added
