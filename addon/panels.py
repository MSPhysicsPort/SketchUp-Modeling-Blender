"""N-panel (VIEW_3D / UI / SketchUp), generated from the data table."""

import bpy

from .data.menu_data import MENUS
from .i18n.translations import translate as _T


def _draw_panel_items(layout, items, depth=0):
    for item in items:
        if item.get("separator"):
            layout.separator()
            continue
        if "note" in item or item.get("scope", "in") == "out":
            continue
        label = item.get("label")
        if label is None:
            continue
        prefix = "  " * depth
        if "submenu" in item:
            layout.label(text=prefix + _T(label))
            _draw_panel_items(layout, item["submenu"], depth + 1)
        else:
            operator_id = item.get("operator", "sketchup.stub")
            operator = layout.operator(operator_id, text=prefix + _T(label))
            if operator_id == "sketchup.stub":
                operator.tool_id = item["id"]


class SKETCHUP_PT_tools(bpy.types.Panel):
    bl_idname = "SKETCHUP_PT_tools"
    bl_label = "SketchUp Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SketchUp"

    def draw(self, context):
        layout = self.layout
        wm = getattr(context, "window_manager", None)
        if wm is not None and hasattr(wm, "sketchup_mode"):
            box = layout.box()
            box.prop(wm, "sketchup_mode", text=_T("SketchUp Mode"), toggle=True)
            if wm.sketchup_mode:
                box.label(text=_T("SU shortcuts active"), icon="CHECKMARK")
            else:
                box.label(text=_T("Blender shortcuts active"))
            layout.separator()
        for menu in MENUS:
            layout.label(text=_T(menu["label"]))
            column = layout.column(align=True)
            _draw_panel_items(column, menu["items"])
            layout.separator()


class SKETCHUP_PT_vcb(bpy.types.Panel):
    bl_idname = "SKETCHUP_PT_vcb"
    bl_label = "Measurements (VCB)"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SketchUp"

    def draw(self, context):
        layout = self.layout
        addon = None
        try:
            addon = context.preferences.addons.get(__package__)
        except (AttributeError, ReferenceError):
            pass
        unit = addon.preferences.default_unit if addon is not None else "mm"
        row = layout.row()
        row.label(text=_T("Default unit:"))
        row.label(text=unit)
        vcb_text = ""
        try:
            session = context.window_manager.sketchup_session
            if session is not None:
                vcb_text = session.vcb_text
        except (AttributeError, ReferenceError):
            pass
        row = layout.row()
        row.label(text=_T("VCB:"))
        row.label(text=vcb_text)


PANEL_CLASSES = [SKETCHUP_PT_tools, SKETCHUP_PT_vcb]


def register():
    for cls in PANEL_CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(PANEL_CLASSES):
        bpy.utils.unregister_class(cls)
