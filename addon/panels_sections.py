"""Sections N-panel: plane list, activation, slice."""

import bpy

from .data import sections as sections_mod
from .i18n.translations import translate as _T


class SKETCHUP_PT_sections(bpy.types.Panel):
    bl_label = "Sections"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SketchUp"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        planes = sections_mod.list_sections(scene)
        if not planes:
            layout.label(text=_T("No section planes"))
        for plane in planes:
            row = layout.row(align=True)
            active = bool(plane.get(sections_mod.PROP_ACTIVE, False))
            activate = row.operator(
                "sketchup.section_activate", text="",
                icon="CHECKBOX_HLT" if active else "CHECKBOX_DEHLT",
            )
            activate.plane_name = plane.name
            row.label(text=plane.name)
            reverse = row.operator(
                "sketchup.section_reverse", text="", icon="ARROW_LEFTRIGHT"
            )
            reverse.plane_name = plane.name
            delete = row.operator(
                "sketchup.section_delete", text="", icon="X"
            )
            delete.plane_name = plane.name
        layout.operator(
            "sketchup.tool_section_plane", text=_T("Section Plane Tool")
        )
        row = layout.row(align=True)
        row.operator(
            "sketchup.section_slice", text=_T("Create Group from Slice")
        )
        row.operator(
            "sketchup.section_toggle_cuts", text=_T("Toggle Cuts")
        )


def register():
    bpy.utils.register_class(SKETCHUP_PT_sections)


def unregister():
    bpy.utils.unregister_class(SKETCHUP_PT_sections)
