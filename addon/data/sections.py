"""Section planes: Empty objects carrying a cut plane, applied as
a Boolean DIFFERENCE modifier (EXACT) against a shared cutter box
covering the half-space on the plane normal's side. One section is
active at a time; Create Group from Slice intersects the plane
with every visible mesh via bisect_plane.
"""

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

MODIFIER_NAME = "SU_SectionCut"
CUTTER_NAME = "SU_SectionCutter"
PROP_SECTION = "su_section"
PROP_ACTIVE = "su_section_active"


def list_sections(scene):
    return [o for o in scene.objects if o.get(PROP_SECTION, False)]


def get_active_section(scene):
    for obj in list_sections(scene):
        if obj.get(PROP_ACTIVE, False):
            return obj
    return None


def create_section_plane(scene, location, normal, name=None):
    if name is None:
        base = "Section Plane"
        name = base
        index = 1
        while name in bpy.data.objects:
            index += 1
            name = "%s %d" % (base, index)
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.5
    obj.location = Vector(location)
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(
        Vector(normal).normalized()
    )
    obj[PROP_SECTION] = True
    obj[PROP_ACTIVE] = False
    scene.collection.objects.link(obj)
    return obj


def plane_frame(obj):
    """(origin, normal) in world coordinates."""
    matrix = obj.matrix_world
    return Vector(matrix.translation), Vector(matrix.to_3x3() @ Vector((0, 0, 1))).normalized()


def _scene_bounds(scene):
    low = Vector((1e9, 1e9, 1e9))
    high = Vector((-1e9, -1e9, -1e9))
    for obj in scene.objects:
        if obj.type != "MESH" or obj.name == CUTTER_NAME:
            continue
        try:
            corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        except Exception:
            continue
        for corner in corners:
            low = Vector(map(min, low, corner))
            high = Vector(map(max, high, corner))
    if low.x > high.x:
        return 10.0
    return max((high - low).length, 1.0)


def _cutter_object(scene, plane):
    """Shared cutter box: spans the +normal half-space in the
    plane's frame, sized to the scene bounds."""
    size = _scene_bounds(scene) * 2.0 + 10.0
    cutter = bpy.data.objects.get(CUTTER_NAME)
    if cutter is None:
        mesh = bpy.data.meshes.new(CUTTER_NAME)
        bm = bmesh.new()
        half = size / 2.0
        verts = [
            bm.verts.new((x, y, z))
            for x in (-half, half)
            for y in (-half, half)
            for z in (0.0, size)
        ]
        bm.verts.ensure_lookup_table()
        # Vertices: index bits (x, y, z) with x/y in {-half, half}
        # and z in {0, size}. Faces wound outward.
        faces = [
            (0, 2, 6, 4),  # z=0
            (1, 5, 7, 3),  # z=size
            (0, 4, 5, 1),  # y=-half
            (2, 3, 7, 6),  # y=+half
            (0, 1, 3, 2),  # x=-half
            (4, 6, 7, 5),  # x=+half
        ]
        for quad in faces:
            bm.faces.new(tuple(verts[i] for i in quad))
        bm.to_mesh(mesh)
        bm.free()
        cutter = bpy.data.objects.new(CUTTER_NAME, mesh)
        scene.collection.objects.link(cutter)
    else:
        # Rebuild the mesh if the scene grew.
        mesh = cutter.data
        if mesh.vertices and max(v.co.z for v in mesh.vertices) < size:
            bm = bmesh.new()
            bm.from_mesh(mesh)
            scale = size / max(v.co.z for v in mesh.vertices)
            for vert in bm.verts:
                vert.co *= scale
            bm.to_mesh(mesh)
            bm.free()
    cutter.matrix_world = plane.matrix_world.copy()
    cutter.hide_viewport = True
    cutter.hide_render = True
    cutter.hide_select = True
    return cutter


def apply_section_cut(scene, plane):
    """Attach the cut modifier to every mesh object (except the
    cutter itself). Idempotent."""
    cutter = _cutter_object(scene, plane)
    for obj in scene.objects:
        if obj.type != "MESH" or obj is cutter:
            continue
        modifier = obj.modifiers.get(MODIFIER_NAME)
        if modifier is None:
            modifier = obj.modifiers.new(MODIFIER_NAME, "BOOLEAN")
        modifier.operation = "DIFFERENCE"
        modifier.solver = "EXACT"
        modifier.object = cutter
        modifier.show_viewport = True
        modifier.show_render = True


def clear_section_cut(scene):
    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        modifier = obj.modifiers.get(MODIFIER_NAME)
        if modifier is not None:
            obj.modifiers.remove(modifier)
    cutter = bpy.data.objects.get(CUTTER_NAME)
    if cutter is not None:
        cutter.hide_viewport = True


def set_active_section(scene, plane):
    for obj in list_sections(scene):
        obj[PROP_ACTIVE] = obj is plane
    clear_section_cut(scene)
    if plane is not None and scene.get("su_sections_enabled", True):
        apply_section_cut(scene, plane)


def refresh_section_cut(scene):
    plane = get_active_section(scene)
    clear_section_cut(scene)
    if plane is not None and scene.get("su_sections_enabled", True):
        apply_section_cut(scene, plane)


def reverse_section(plane):
    flip = Matrix.Rotation(3.141592653589793, 4, "X")
    plane.matrix_world = plane.matrix_world @ flip


def slice_section(scene, plane):
    """Intersect the plane with every visible mesh; returns a new
    object holding the cut edges (marked as a group)."""
    origin, normal = plane_frame(plane)
    world_edges = []
    for obj in scene.objects:
        if obj.type != "MESH" or obj.name == CUTTER_NAME:
            continue
        try:
            if obj.hide_viewport or obj.hide_get():
                continue
        except Exception:
            pass
        inverse = obj.matrix_world.inverted()
        plane_co = inverse @ origin
        normal_local = (
            inverse.to_3x3().transposed() @ normal
        ).normalized()
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            result = bmesh.ops.bisect_plane(
                bm,
                geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                plane_co=plane_co,
                plane_no=normal_local,
                clear_inner=False,
                clear_outer=False,
            )
            matrix = obj.matrix_world
            for element in result["geom_cut"]:
                if isinstance(element, bmesh.types.BMEdge):
                    world_edges.append(
                        tuple(
                            matrix @ v.co for v in element.verts
                        )
                    )
        finally:
            bm.free()
    mesh = bpy.data.meshes.new("Section Slice")
    verts = []
    index_of = {}

    def vert_index(co):
        key = (round(co.x, 6), round(co.y, 6), round(co.z, 6))
        if key not in index_of:
            index_of[key] = len(verts)
            verts.append(Vector(co))
        return index_of[key]

    edges = []
    seen_edges = set()
    for a, b in world_edges:
        ia, ib = vert_index(a), vert_index(b)
        if ia != ib:
            key = (ia, ib) if ia < ib else (ib, ia)
            if key not in seen_edges:
                seen_edges.add(key)
                edges.append((ia, ib))
    mesh.from_pydata([tuple(v) for v in verts], edges, [])
    mesh.update()
    from ..core.containers import KIND_GROUP, PROP_KIND

    obj = bpy.data.objects.new("Section Slice", mesh)
    obj[PROP_KIND] = KIND_GROUP
    scene.collection.objects.link(obj)
    return obj
