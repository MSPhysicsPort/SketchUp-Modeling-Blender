"""Scenes and Styles N-panels."""

import bpy

from .data import scenes as scenes_mod
from .i18n.translations import translate as _T


class SKETCHUP_PT_scenes(bpy.types.Panel):
    bl_label = "Scenes"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SketchUp"

    def draw(self, context):
        layout = self.layout
        entries = scenes_mod.get_scenes(context.scene)
        if not entries:
            layout.label(text=_T("No scenes yet"))
        for index, entry in enumerate(entries):
            row = layout.row(align=True)
            apply = row.operator(
                "sketchup.scene_apply", text=entry["name"]
            )
            apply.index = index
            update = row.operator(
                "sketchup.scene_update", text="", icon="FILE_REFRESH"
            )
            update.index = index
            delete = row.operator(
                "sketchup.scene_delete", text="", icon="X"
            )
            delete.index = index
        layout.operator("sketchup.scene_add", text=_T("Add Scene"))


class SKETCHUP_PT_styles(bpy.types.Panel):
    bl_label = "Styles"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SketchUp"

    def draw(self, context):
        layout = self.layout
        presets = [
            ("SHADED", _T("Shaded")),
            ("TEXTURED", _T("Shaded with Textures")),
            ("HIDDEN_LINE", _T("Hidden Line")),
            ("WIREFRAME", _T("Wireframe")),
            ("XRAY", _T("X-Ray")),
        ]
        for preset_id, label in presets:
            button = layout.operator(
                "sketchup.style_preset", text=label
            )
            button.preset = preset_id
        shading = getattr(context.space_data, "shading", None)
        if shading is not None:
            layout.separator()
            try:
                layout.prop(shading, "show_xray", text=_T("X-Ray"))
                layout.prop(shading, "show_shadows", text=_T("Shadows"))
                layout.prop(
                    shading, "show_backface_culling", text=_T("Backface Culling")
                )
            except Exception:
                pass
        layout.separator()
        layout.prop(
            context.scene, "su_color_by_axis", text=_T("Color by Axis")
        )


def register():
    bpy.utils.register_class(SKETCHUP_PT_scenes)
    bpy.utils.register_class(SKETCHUP_PT_styles)


def unregister():
    bpy.utils.unregister_class(SKETCHUP_PT_styles)
    bpy.utils.unregister_class(SKETCHUP_PT_scenes)
