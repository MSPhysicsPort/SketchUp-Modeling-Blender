"""Boolean evaluation via temporary objects + depsgraph (no bpy.ops).

Used by Push/Pull punch-through and the Solid Tools. EXACT solver
first, FLOAT fallback on failure. Pure ``bpy.data`` API, so it runs
headless and inside timer callbacks. The caller owns Edit Mode sync:
leave Edit Mode before replacing mesh data, re-enter after.
"""

import bpy


def _eval_once(mesh_a, matrix_a, mesh_b, matrix_b, operation, solver):
    scene = bpy.context.scene
    temp_coll = bpy.data.collections.new("SU_BooleanTemp")
    scene.collection.children.link(temp_coll)
    mesh_a_copy = mesh_a.copy()
    mesh_a_copy.transform(matrix_a)
    mesh_b_copy = mesh_b.copy()
    mesh_b_copy.transform(matrix_b)
    kept = None
    try:
        obj_a = bpy.data.objects.new("SU_BoolA", mesh_a_copy)
        obj_b = bpy.data.objects.new("SU_BoolB", mesh_b_copy)
        temp_coll.objects.link(obj_a)
        temp_coll.objects.link(obj_b)
        modifier = obj_a.modifiers.new("SU_Boolean", "BOOLEAN")
        modifier.operation = operation
        modifier.solver = solver
        modifier.object = obj_b
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = obj_a.evaluated_get(depsgraph)
        result = evaluated.to_mesh()
        if result is not None:
            kept = result.copy()
        evaluated.to_mesh_clear()
    finally:
        for obj in list(temp_coll.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        scene.collection.children.unlink(temp_coll)
        bpy.data.collections.remove(temp_coll)
        for mesh in (mesh_a_copy, mesh_b_copy):
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
    return kept


def boolean_meshes(mesh_a, matrix_a, mesh_b, matrix_b, operation):
    """Evaluate ``mesh_a <operation> mesh_b`` (both transformed into
    a common frame by their matrices). Returns a new Mesh in that
    frame, or None on failure. ``operation`` is DIFFERENCE, UNION
    or INTERSECT."""
    try:
        result = _eval_once(mesh_a, matrix_a, mesh_b, matrix_b, operation, "EXACT")
    except Exception:
        result = None
    if result is None:
        try:
            result = _eval_once(mesh_a, matrix_a, mesh_b, matrix_b, operation, "FLOAT")
        except Exception:
            result = None
    return result


def replace_mesh_contents(mesh, source_mesh):
    """Replace ``mesh``'s contents with ``source_mesh``'s (same
    frame). The mesh datablock identity (and its users) is kept."""
    import bmesh

    bm = bmesh.new()
    try:
        bm.from_mesh(source_mesh)
        bm.to_mesh(mesh)
    finally:
        bm.free()
    mesh.update()
    return True
