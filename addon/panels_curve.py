"""Entity Info curve panel (P2 slice): show the selected curve's
type/radius/segments and open the curve edit dialog. The full
Entity Info panel arrives with P5.
"""

import bpy

from .core import curves as curve_mod
from .core import geometry as geometry_mod
from .i18n.translations import translate as _T


class SKETCHUP_PT_curve(bpy.types.Panel):
    bl_idname = "SKETCHUP_PT_curve"
    bl_label = "SketchUp Curve"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SketchUp"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "MESH"

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        mesh = obj.data
        records = curve_mod.get_curves(mesh)
        if not records:
            layout.label(text=_T("No curves in this object."))
            return
        # Show the first curve that has a selected edge.
        shown = None
        try:
            import bmesh

            bm = bmesh.from_edit_mesh(mesh) if obj.mode == "EDIT" else None
            if bm is not None:
                geometry_mod.refresh(bm)
                for edge in bm.edges:
                    if edge.select:
                        curve_id = curve_mod.curve_id_of(bm, edge)
                        if curve_id:
                            shown = records.get(str(curve_id))
                            break
        except Exception:
            shown = None
        if shown is None:
            shown = next(iter(records.values()))
        layout.label(text=_T("Type: %s") % shown.get("type", "?"))
        layout.label(text=_T("Radius: %.3f m") % shown.get("radius", 0.0))
        layout.label(text=_T("Segments: %d") % shown.get("segments", 0))
        layout.operator("sketchup.curve_edit", text=_T("Edit Curve…"))


PANEL_CLASSES = [SKETCHUP_PT_curve]


def register():
    for cls in PANEL_CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(PANEL_CLASSES):
        bpy.utils.unregister_class(cls)
