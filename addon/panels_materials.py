"""Materials N-panel: active material, paint mode, new material."""

import bpy

from .data import materials as materials_mod
from .i18n.translations import translate as _T


def _principled_base_color(material):
    if material is None or not material.use_nodes:
        return None
    for node in material.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            return node.inputs["Base Color"]
    return None


class SKETCHUP_OT_material_new(bpy.types.Operator):
    bl_idname = "sketchup.material_new"
    bl_label = "New Material"
    bl_description = "Create a material and make it active"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        material = bpy.data.materials.new("SU Material")
        material.use_nodes = True
        material["su_texture_size"] = 1.0
        materials_mod.set_active_material(context.scene, material)
        return {"FINISHED"}


class SKETCHUP_PT_materials(bpy.types.Panel):
    bl_label = "Materials"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SketchUp"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        material = materials_mod.get_active_material(scene)
        layout.prop_search(
            scene, "su_active_material", bpy.data, "materials", text=""
        )
        color_input = _principled_base_color(material)
        if color_input is not None:
            layout.prop(color_input, "default_value", text=_T("Color"))
        if "su_texture_size" in material:
            layout.prop(
                material, '["su_texture_size"]', text=_T("Texture Size (m)")
            )
        layout.prop(scene, "su_paint_mode", expand=True)
        row = layout.row(align=True)
        row.operator("sketchup.material_new", text=_T("New Material"))
        row.operator("sketchup.tool_paint_bucket", text=_T("Paint Bucket"))


def register():
    bpy.utils.register_class(SKETCHUP_OT_material_new)
    bpy.utils.register_class(SKETCHUP_PT_materials)


def unregister():
    bpy.utils.unregister_class(SKETCHUP_PT_materials)
    bpy.utils.unregister_class(SKETCHUP_OT_material_new)
