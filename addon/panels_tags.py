"""Tags N-panel: the tag list, visibility, and Color by Tag."""

import bpy

from .data import tags as tags_mod
from .i18n.translations import translate as _T


class SKETCHUP_UL_tags(bpy.types.UIList):
    bl_idname = "SKETCHUP_UL_tags"

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "color", text="")
        row.label(text=item.name)
        toggle = row.operator(
            "sketchup.tag_toggle_visible", text="",
            icon="HIDE_OFF" if item.visible else "HIDE_ON",
        )
        toggle.tag_name = item.name


class SKETCHUP_PT_tags(bpy.types.Panel):
    bl_label = "Tags"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SketchUp"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        tags_mod.ensure_defaults(scene)
        layout.template_list(
            "SKETCHUP_UL_tags", "", scene, "su_tags",
            scene, "su_tags_index", rows=5,
        )
        row = layout.row(align=True)
        row.operator("sketchup.tag_add", text=_T("Add"))
        row.operator("sketchup.tag_delete", text=_T("Delete"))
        row.operator("sketchup.tag_rename", text=_T("Rename"))
        layout.operator("sketchup.tag_assign", text=_T("Assign to Selection"))
        layout.operator("sketchup.tool_tag", text=_T("Tag Tool"))
        layout.prop(scene, "su_color_by_tag", text=_T("Color by Tag"))
        layout.label(
            text=_T("Active tag: %s") % tags_mod.active_tag_name(scene)
        )


def register():
    bpy.utils.register_class(SKETCHUP_UL_tags)
    bpy.utils.register_class(SKETCHUP_PT_tags)


def unregister():
    bpy.utils.unregister_class(SKETCHUP_PT_tags)
    bpy.utils.unregister_class(SKETCHUP_UL_tags)
