"""SketchUp materials on top of Blender materials.

Faces carry a material_index into the mesh's material slots. The
default material is a node setup that renders white on the front
and blue-gray on the back (Geometry/Backfacing mix), matching
SketchUp's default face colors in Material Preview / Rendered
views. Per-face back materials are not possible in Blender (D8):
only the default material has a distinct back color; painted faces
show the same material on both sides.
"""

import bpy
from mathutils import Vector

DEFAULT_MATERIAL_NAME = "SU Default"
DEFAULT_FRONT_COLOR = (0.95, 0.95, 0.95, 1.0)
DEFAULT_BACK_COLOR = (0.55, 0.62, 0.72, 1.0)
UV_LAYER_NAME = "SU_UV"


def ensure_default_material():
    """Create (once) or return the SU default material."""
    material = bpy.data.materials.get(DEFAULT_MATERIAL_NAME)
    if material is not None:
        return material
    material = bpy.data.materials.new(DEFAULT_MATERIAL_NAME)
    material.use_nodes = True
    material["su_default"] = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    geometry = nodes.new("ShaderNodeNewGeometry")
    mix = nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "MIX"
    mix.inputs["Color1"].default_value = DEFAULT_FRONT_COLOR
    mix.inputs["Color2"].default_value = DEFAULT_BACK_COLOR
    links.new(geometry.outputs["Backfacing"], mix.inputs["Fac"])
    links.new(mix.outputs["Color"], principled.inputs["Base Color"])
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    output.location = (300, 0)
    principled.location = (100, 0)
    mix.location = (-100, 0)
    geometry.location = (-300, -100)
    return material


def is_default_material(material):
    return material is not None and bool(material.get("su_default", False))


def get_active_material(scene):
    name = scene.get("su_active_material", "")
    if name:
        material = bpy.data.materials.get(name)
        if material is not None:
            return material
    return ensure_default_material()


def set_active_material(scene, material):
    scene["su_active_material"] = material.name if material else ""


def material_slot_index(mesh, material):
    for index, slot in enumerate(mesh.materials):
        if slot == material:
            return index
    mesh.materials.append(material)
    return len(mesh.materials) - 1


def assign_material(bm, face_indices, material, mesh):
    """Set material_index on bmesh faces (slot ensured on mesh)."""
    from ..core.geometry import refresh

    refresh(bm)
    slot = material_slot_index(mesh, material)
    for face_index in face_indices:
        bm.faces[face_index].material_index = slot
    return slot


def face_material(mesh, face_index):
    try:
        polygon = mesh.polygons[face_index]
    except IndexError:
        return None
    if polygon.material_index < len(mesh.materials):
        return mesh.materials[polygon.material_index]
    return None


def has_image_texture(material):
    if material is None or not material.use_nodes:
        return False
    return any(
        node.type == "TEX_IMAGE" and node.image is not None
        for node in material.node_tree.nodes
    )


def material_texture_size(material):
    try:
        return float(material.get("su_texture_size", 1.0))
    except (TypeError, ValueError):
        return 1.0


def apply_true_size_uv(bm, face_indices, size):
    """Planar UVs at real-world scale: texture repeats every
    ``size`` meters, projected along the face's dominant axis."""
    from ..core.geometry import ensure_layers, refresh

    ensure_layers(bm)
    refresh(bm)
    uv_layer = bm.loops.layers.uv.get(UV_LAYER_NAME)
    if uv_layer is None:
        uv_layer = bm.loops.layers.uv.new(UV_LAYER_NAME)
    if size <= 0:
        size = 1.0
    for face_index in face_indices:
        face = bm.faces[face_index]
        normal = Vector(face.normal)
        dominant = max(range(3), key=lambda k: abs(normal[k]))
        u_axis = (dominant + 1) % 3
        v_axis = (dominant + 2) % 3
        for loop in face.loops:
            co = loop.vert.co
            loop[uv_layer].uv = (co[u_axis] / size, co[v_axis] / size)


def connected_same_material_faces(bm, seed_index):
    """Flood fill from a face over edge-adjacent faces sharing its
    material_index (Paint Bucket Shift behavior)."""
    from ..core.geometry import refresh

    refresh(bm)
    seed = bm.faces[seed_index]
    target = seed.material_index
    seen = {seed.index}
    stack = [seed]
    while stack:
        face = stack.pop()
        for edge in face.edges:
            for link in edge.link_faces:
                if link.material_index == target and link.index not in seen:
                    seen.add(link.index)
                    stack.append(link)
    return sorted(seen)


def all_same_material_faces(bm, seed_index):
    from ..core.geometry import refresh

    refresh(bm)
    target = bm.faces[seed_index].material_index
    return [f.index for f in bm.faces if f.material_index == target]
