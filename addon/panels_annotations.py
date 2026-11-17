"""Annotations N-panel: dimensions / text notes list."""

import bpy

from .core.units import format_length
from .data import annotations as annotations_mod
from .i18n.translations import translate as _T


class SKETCHUP_PT_annotations(bpy.types.Panel):
    bl_label = "Annotations"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SketchUp"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        annotations = annotations_mod.get_annotations(scene)
        if not annotations:
            layout.label(text=_T("No dimensions or notes"))
        for index, entry in enumerate(annotations):
            row = layout.row(align=True)
            if entry.get("type") == "dimension":
                p1 = annotations_mod.resolve_point(scene, entry, "ref1")
                p2 = annotations_mod.resolve_point(scene, entry, "ref2")
                label = _T("Dimension: %s") % format_length(
                    (p2 - p1).length, "mm", precision=1
                )
            else:
                label = _T("Note: %s") % entry.get("text", "")[:24]
            row.label(text=label)
            delete = row.operator(
                "sketchup.annotation_delete", text="", icon="X"
            )
            delete.index = index
        row = layout.row(align=True)
        row.operator("sketchup.tool_dimension", text=_T("Dimension"))
        row.operator("sketchup.tool_text", text=_T("Text"))
        row = layout.row(align=True)
        row.operator("sketchup.text_3d", text=_T("3D Text"))
        row.operator("sketchup.annotations_clear", text=_T("Delete All"))


def register():
    bpy.utils.register_class(SKETCHUP_PT_annotations)


def unregister():
    bpy.utils.unregister_class(SKETCHUP_PT_annotations)
