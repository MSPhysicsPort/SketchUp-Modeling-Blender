"""Standalone geometry-engine test (run inside Blender, any version).

Usage: blender --background --factory-startup --python geometry_suite.py
Exits 0 on success, 1 on failure. Also imported by run_t2.py via exec.
"""

import importlib.util
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon", "core"))

import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

geometry = None


def _load_standalone():
    spec = importlib.util.spec_from_file_location(
        "sketchup_geometry",
        os.path.join(os.path.dirname(__file__), "..", "addon", "core", "geometry.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print("[%s] geometry %s %s" % (status, name, detail))
    if not condition:
        check.failed += 1


check.failed = 0


def rect(bm, size=2.0):
    geometry.apply_line(bm, (0, 0, 0), (size, 0, 0))
    geometry.apply_line(bm, (size, 0, 0), (size, size, 0))
    geometry.apply_line(bm, (size, size, 0), (0, size, 0))
    return geometry.apply_line(bm, (0, size, 0), (0, 0, 0))


def run(geometry_module=None):
    """Run the suite against the given geometry module (or the
    standalone source file when run directly)."""
    global geometry
    geometry = geometry_module or _load_standalone()
    check.failed = 0
    # 1. Rectangle closes into one face, normal +Z.
    bm = bmesh.new()
    result = rect(bm)
    check("rect 1 face", len(bm.faces) == 1, "faces=%d" % len(bm.faces))
    check("rect 4 edges", len(bm.edges) == 4, "edges=%d" % len(bm.edges))
    check("rect 4 verts", len(bm.verts) == 4, "verts=%d" % len(bm.verts))
    bm.faces.ensure_lookup_table()
    face = bm.faces[0]
    check("rect normal +Z", face.normal.z > 0.99, "normal=%s" % (tuple(face.normal),))
    check("rect summary faces", len(result["faces"]) == 1)
    bm.free()

    # 2. Diagonal splits the face into two.
    bm = bmesh.new()
    rect(bm)
    geometry.apply_line(bm, (0, 0, 0), (2, 2, 0))
    check("diagonal 2 faces", len(bm.faces) == 2, "faces=%d" % len(bm.faces))
    check("diagonal 5 edges", len(bm.edges) == 5, "edges=%d" % len(bm.edges))

    # 3. Deleting the diagonal heals back to one face.
    diagonal = None
    for edge in bm.edges:
        coords = sorted(tuple(v.co) for v in edge.verts)
        if coords == [(0.0, 0.0, 0.0), (2.0, 2.0, 0.0)]:
            diagonal = edge
    check("diagonal found", diagonal is not None)
    summary = geometry.delete_edge(bm, diagonal, heal=True)
    check("heal 1 face", len(bm.faces) == 1, "faces=%d" % len(bm.faces))
    check("heal 4 edges", len(bm.edges) == 4, "edges=%d" % len(bm.edges))
    check("heal removed 2", summary["faces_removed"] == 2)
    check("heal created 1", len(summary["faces"]) == 1)

    # 4. Deleting a boundary edge removes the face.
    bm.edges.ensure_lookup_table()
    edge = bm.edges[0]
    deleted_coords = (tuple(edge.verts[0].co), tuple(edge.verts[1].co))
    geometry.delete_edge(bm, edge, heal=True)
    check("del boundary 0 faces", len(bm.faces) == 0, "faces=%d" % len(bm.faces))
    check("del boundary 3 edges", len(bm.edges) == 3, "edges=%d" % len(bm.edges))

    # 5. Redrawing the deleted edge restores the face.
    geometry.apply_line(bm, deleted_coords[0], deleted_coords[1])
    check("redraw 1 face", len(bm.faces) == 1, "faces=%d" % len(bm.faces))
    bm.free()

    # 6. Crossing lines split each other (plus shape, no faces).
    bm = bmesh.new()
    geometry.apply_line(bm, (-1, 0, 0), (1, 0, 0))
    result = geometry.apply_line(bm, (0, -1, 0), (0, 1, 0))
    check("cross 4 edges", len(bm.edges) == 4, "edges=%d" % len(bm.edges))
    check("cross 5 verts", len(bm.verts) == 5, "verts=%d" % len(bm.verts))
    check("cross 0 faces", len(bm.faces) == 0, "faces=%d" % len(bm.faces))
    check("cross splits>0", result["splits"] >= 1, "splits=%d" % result["splits"])
    bm.free()

    # 7. T-junction: edge ending on another edge's interior splits it.
    bm = bmesh.new()
    geometry.apply_line(bm, (0, 0, 0), (2, 0, 0))
    geometry.apply_line(bm, (1, 0, 0), (1, 1, 0))
    check("tee 3 edges", len(bm.edges) == 3, "edges=%d" % len(bm.edges))
    check("tee 4 verts", len(bm.verts) == 4, "verts=%d" % len(bm.verts))
    bm.free()

    # 8. Duplicate / degenerate lines are no-ops.
    bm = bmesh.new()
    geometry.apply_line(bm, (0, 0, 0), (1, 0, 0))
    dup = geometry.apply_line(bm, (0, 0, 0), (1, 0, 0))
    check("dup exists", dup["status"] == "exists" and len(bm.edges) == 1)
    deg = geometry.apply_line(bm, (0, 0, 0), (0, 0, 0))
    check("degenerate", deg["status"] == "degenerate" and len(bm.edges) == 1)
    # Near-duplicate endpoint welds.
    geometry.apply_line(bm, (1, 0, 0), (1, 1, 0))
    check("weld 3 verts", len(bm.verts) == 3, "verts=%d" % len(bm.verts))
    bm.free()

    # 9. Cube wireframe: 6 faces (multi-plane healing).
    bm = bmesh.new()
    corners = [
        (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
        (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1),
    ]
    cube_edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]
    for a, b in cube_edges:
        geometry.apply_line(bm, corners[a], corners[b])
    check("cube 6 faces", len(bm.faces) == 6, "faces=%d" % len(bm.faces))
    check("cube 12 edges", len(bm.edges) == 12, "edges=%d" % len(bm.edges))
    bm.free()

    # 10. Face-only delete keeps edges; soften/hide flags round-trip.
    bm = bmesh.new()
    rect(bm)
    bm.faces.ensure_lookup_table()
    face = bm.faces[0]
    check("face-only delete", geometry.delete_face_only(bm, face) is True)
    check("face-only keeps edges", len(bm.edges) == 4 and len(bm.faces) == 0)
    bm.edges.ensure_lookup_table()
    edge = bm.edges[0]
    flags = geometry.set_edge_flags(bm, edge, soft=True, hidden=False)
    check("soft flag set", flags is not None and flags & geometry.FLAG_SOFT)
    check("soft smooths edge", edge.smooth is True)
    flags = geometry.set_edge_flags(bm, edge, hidden=True)
    check("hidden flag set", flags & geometry.FLAG_HIDDEN)
    check("hidden hides edge", edge.hide is True)
    flags = geometry.clear_edge_flags(bm, edge)
    check("flags cleared", flags == 0)
    bm.free()

    # 11. Triangle + apex: base face forms, side faces form.
    bm = bmesh.new()
    geometry.apply_line(bm, (0, 0, 0), (2, 0, 0))
    geometry.apply_line(bm, (2, 0, 0), (1, 2, 0))
    geometry.apply_line(bm, (1, 2, 0), (0, 0, 0))
    check("tri 1 face", len(bm.faces) == 1, "faces=%d" % len(bm.faces))
    geometry.apply_line(bm, (0, 0, 0), (1, 0.6, 2))
    geometry.apply_line(bm, (2, 0, 0), (1, 0.6, 2))
    geometry.apply_line(bm, (1, 2, 0), (1, 0.6, 2))
    check("pyramid 4 faces", len(bm.faces) == 4, "faces=%d" % len(bm.faces))
    bm.free()

    print("geometry: %s" % ("ALL PASS" if check.failed == 0 else "%d FAILURES" % check.failed))
    return 0 if check.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
