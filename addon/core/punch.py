"""Push/Pull punch-through (proposal §3.3, P4).

Pushing a face inward until it reaches the opposite surface cuts a
through opening: the pushed prism is subtracted from the mesh with
an evaluated boolean (EXACT solver), which deletes the pushed face
and the exit face region and heals the opening walls in one step.
The commit runs on a timer because replacing mesh data requires
leaving and re-entering Edit Mode, which must not happen inside the
modal handler.
"""

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import boolean_eval


def find_push_limit(bm, face_center, direction, skip_face_index=None):
    """Distance from ``face_center`` along ``direction`` to the next
    surface, or None when the ray hits nothing (open space)."""
    bvh = BVHTree.FromBMesh(bm)
    origin = Vector(face_center) + Vector(direction) * 1e-4
    location, _normal, index, distance = bvh.ray_cast(origin, Vector(direction))
    if location is None:
        return None
    if skip_face_index is not None and index == skip_face_index:
        # The ray started inside the start face's own volume; cast
        # again from just past the hit.
        origin = location + Vector(direction) * 1e-4
        location, _normal, index, distance2 = bvh.ray_cast(origin, Vector(direction))
        if location is None:
            return None
        distance = distance + distance2
    if distance < 1e-3:
        return None
    return distance


def build_prism_mesh(loop_coords, direction, travel):
    """Closed prism mesh: footprint ring extruded along direction.

    Winding is derived from the loop's Newell normal so every face
    points outward: an inside-out prism inverts the boolean.
    """
    from .geometry import _newell_normal

    direction = Vector(direction)
    loop = [Vector(co) for co in loop_coords]
    ccw = _newell_normal(loop).dot(direction) > 0
    bm = bmesh.new()
    try:
        bottom = [bm.verts.new(co) for co in loop]
        top = [bm.verts.new(co + direction * travel) for co in loop]
        bm.verts.ensure_lookup_table()
        if ccw:
            bm.faces.new(tuple(reversed(bottom)))
            bm.faces.new(tuple(top))
        else:
            bm.faces.new(tuple(bottom))
            bm.faces.new(tuple(reversed(top)))
        count = len(loop)
        for i in range(count):
            j = (i + 1) % count
            if ccw:
                bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
            else:
                bm.faces.new((bottom[i], top[i], top[j], bottom[j]))
        mesh = bpy.data.meshes.new("SU_PunchPrism")
        bm.to_mesh(mesh)
    finally:
        bm.free()
    return mesh


def punch_through_mesh(mesh, loop_coords, push_direction, travel):
    """Subtract the pushed prism from ``mesh`` in place. Returns
    True when the boolean produced a usable mesh."""
    from mathutils import Matrix

    prism = build_prism_mesh(loop_coords, push_direction, travel)
    try:
        identity = Matrix.Identity(4)
        result = boolean_eval.boolean_meshes(
            mesh, identity, prism, identity, "DIFFERENCE"
        )
    finally:
        bpy.data.meshes.remove(prism)
    if result is None or len(result.polygons) == 0:
        if result is not None:
            bpy.data.meshes.remove(result)
        return False
    boolean_eval.replace_mesh_contents(mesh, result)
    bpy.data.meshes.remove(result)
    return True


# -- deferred commit ------------------------------------------------------

_pending = None


def request_punch(obj_name, loop_coords, push_direction, travel):
    """Queue a punch-through commit (runs after the modal ends)."""
    global _pending
    _pending = (
        obj_name,
        [tuple(co) for co in loop_coords],
        tuple(push_direction),
        float(travel),
    )
    try:
        bpy.app.timers.register(_run_pending, first_interval=0.0)
    except Exception:
        pass


def run_pending_punch():
    """Execute the queued punch now (timer callback; tests call it
    directly). Returns True when a punch was applied."""
    global _pending
    params = _pending
    _pending = None
    if params is None:
        return False
    obj_name, loop_coords, push_direction, travel = params
    obj = bpy.data.objects.get(obj_name)
    if obj is None or obj.type != "MESH":
        return False
    try:
        bpy.context.view_layer.objects.active = obj
    except Exception:
        pass
    was_edit = False
    try:
        was_edit = obj.mode == "EDIT"
    except Exception:
        pass
    if was_edit:
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass
    ok = punch_through_mesh(obj.data, loop_coords, push_direction, travel)
    if was_edit:
        try:
            bpy.ops.object.mode_set(mode="EDIT")
        except Exception:
            pass
    if ok:
        try:
            bpy.ops.ed.undo_push(message="SketchUp Push/Pull")
        except Exception:
            pass
    return ok


def _run_pending():
    from ..context import view_3d_override

    override = view_3d_override()
    if override:
        with bpy.context.temp_override(**override):
            run_pending_punch()
    else:
        run_pending_punch()
    return None
