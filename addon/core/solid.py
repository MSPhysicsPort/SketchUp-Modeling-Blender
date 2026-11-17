"""Solid Tools (proposal §3.7, P6): boolean operations between
solid groups/components. A solid is a closed manifold mesh (every
edge has exactly two faces, no boundary). The active object is the
cutting tool; the other selected solids are the targets. Results
replace the target's mesh in place (world frame baked through the
object matrices).
"""

import bmesh
import bpy
from mathutils import Matrix

from . import boolean_eval


def is_solid(obj):
    """Closed-manifold check on the object's mesh data."""
    if obj is None or obj.type != "MESH":
        return False
    mesh = obj.data
    if not mesh.polygons:
        return False
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        for edge in bm.edges:
            if len(edge.link_faces) != 2:
                return False
        return True
    finally:
        bm.free()


def _world_matrix(obj):
    return obj.matrix_world.copy()


def solid_operate(target, tool, operation):
    """Apply the boolean to the target in place; the tool object is
    untouched. Returns True on success. ``operation`` is UNION,
    DIFFERENCE, INTERSECT, or SPLIT (handled by the caller)."""
    target_matrix = _world_matrix(target)
    tool_matrix = _world_matrix(tool)
    result = boolean_eval.boolean_meshes(
        target.data, target_matrix, tool.data, tool_matrix, operation
    )
    if result is None:
        return False
    # Bake the world-frame result back into the target's local frame.
    inverse = target_matrix.inverted()
    result.transform(inverse)
    boolean_eval.replace_mesh_contents(target.data, result)
    bpy.data.meshes.remove(result)
    return True


def solid_split(target, tool):
    """Split: the target is divided by the tool into two objects:
    the intersection part and the difference part. Returns the new
    object (the intersection piece) or None. The target keeps the
    difference part."""
    target_matrix = _world_matrix(target)
    tool_matrix = _world_matrix(tool)
    inter = boolean_eval.boolean_meshes(
        target.data, target_matrix, tool.data, tool_matrix, "INTERSECT"
    )
    diff = boolean_eval.boolean_meshes(
        target.data, target_matrix, tool.data, tool_matrix, "DIFFERENCE"
    )
    if inter is None or diff is None:
        for mesh in (inter, diff):
            if mesh is not None:
                bpy.data.meshes.remove(mesh)
        return None
    inverse = target_matrix.inverted()
    inter.transform(inverse)
    diff.transform(inverse)
    boolean_eval.replace_mesh_contents(target.data, diff)
    bpy.data.meshes.remove(diff)
    new_mesh = inter
    new_obj = bpy.data.objects.new(target.name + " Split", new_mesh)
    new_obj.matrix_world = target_matrix
    for slot in target.data.materials:
        new_mesh.materials.append(slot)
    collections = target.users_collection
    if collections:
        collections[0].objects.link(new_obj)
    else:
        bpy.context.scene.collection.objects.link(new_obj)
    from .containers import PROP_KIND, kind_of

    kind = kind_of(target)
    if kind:
        new_obj[PROP_KIND] = kind
    return new_obj


def solid_trim(target, tool):
    """Trim: like Subtract, but the tool object is kept (same as
    Subtract here; kept as a named entry for the menu)."""
    return solid_operate(target, tool, "DIFFERENCE")


def union_all(objects):
    """Union every object into the first one (world-frame
    accumulation); the other objects are deleted. Returns True."""
    identity = Matrix.Identity(4)
    current = None
    try:
        for obj in objects:
            world_mesh = obj.data.copy()
            world_mesh.transform(_world_matrix(obj))
            if current is None:
                current = world_mesh
                continue
            merged = boolean_eval.boolean_meshes(
                current, identity, world_mesh, identity, "UNION"
            )
            bpy.data.meshes.remove(current)
            bpy.data.meshes.remove(world_mesh)
            current = merged
            if current is None:
                return False
        current.transform(_world_matrix(objects[0]).inverted())
        boolean_eval.replace_mesh_contents(objects[0].data, current)
    finally:
        if current is not None:
            bpy.data.meshes.remove(current)
    for obj in objects[1:]:
        bpy.data.objects.remove(obj, do_unlink=True)
    return True


OPERATIONS = ("UNION", "SUBTRACT", "TRIM", "INTERSECT", "SPLIT")


def run_solid_tool(context, operation):
    """Execute a Solid Tool on the selection. Returns (ok, message).
    The active object is the tool; every other selected solid is a
    target."""
    tool = context.active_object
    targets = [
        o for o in context.selected_objects if o is not tool and o.type == "MESH"
    ]
    if tool is None or tool.type != "MESH" or not targets:
        return False, "Select at least two solids (active object is the tool)"
    if not is_solid(tool):
        return False, "The active object is not a solid"
    bad = [o for o in targets if not is_solid(o)]
    if bad:
        return False, "Not a solid: %s" % bad[0].name
    if context.mode == "EDIT_MESH":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass
    made = []
    if operation == "UNION":
        if not union_all([tool] + targets):
            return False, "Boolean failed"
        return True, "Union applied to %d object(s)" % (len(targets) + 1)
    for target in targets:
        if operation in ("SUBTRACT", "TRIM"):
            ok = solid_operate(target, tool, "DIFFERENCE")
        elif operation == "INTERSECT":
            ok = solid_operate(target, tool, "INTERSECT")
        elif operation == "SPLIT":
            made.append(solid_split(target, tool))
            ok = made[-1] is not None
        else:
            ok = False
        if not ok:
            return False, "Boolean failed on %s" % target.name
    return True, "%s applied to %d object(s)" % (operation.title(), len(targets))
