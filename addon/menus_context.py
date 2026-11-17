"""Right-click context menus: a SketchUp section appended to
Blender's Object and Edit Mesh context menus while SU Mode is on.
"""

import bpy

from .core import containers
from .i18n.translations import translate as _T
from .mode import is_on


def _draw_object_menu(self, context):
    if not is_on(context):
        return
    layout = self.layout
    layout.separator()
    layout.label(text="SketchUp")
    active = context.active_object
    selected = [o for o in context.selected_objects if o.type == "MESH"]
    has_container = active is not None and containers.is_container(active)
    if has_container:
        layout.operator("sketchup.edit_container", text=_T("Edit Group/Component"))
        layout.operator("sketchup.explode", text=_T("Explode"))
        layout.operator("sketchup.make_unique", text=_T("Make Unique"))
    if selected:
        layout.operator("sketchup.make_group", text=_T("Make Group"))
        layout.operator("sketchup.make_component", text=_T("Make Component"))
        layout.operator("sketchup.tag_assign", text=_T("Assign Active Tag"))
    if active is not None and containers.is_container(active):
        if containers.is_locked(active):
            layout.operator("sketchup.unlock_selection", text=_T("Unlock"))
        else:
            layout.operator("sketchup.lock_selection", text=_T("Lock"))
    if len(selected) >= 2:
        layout.operator("sketchup.solid_union", text=_T("Union"))
        layout.operator("sketchup.solid_subtract", text=_T("Subtract"))
        layout.operator("sketchup.solid_intersect", text=_T("Intersect"))
    layout.operator("sketchup.hide", text=_T("Hide"))
    layout.operator("sketchup.unhide_all", text=_T("Unhide All"))


def _draw_edit_mesh_menu(self, context):
    if not is_on(context):
        return
    layout = self.layout
    layout.separator()
    layout.label(text="SketchUp")
    layout.operator("sketchup.make_group", text=_T("Make Group"))
    layout.operator("sketchup.make_component", text=_T("Make Component"))
    layout.operator("sketchup.soften_edges", text=_T("Soften Edges"))
    for scope, label in (
        ("MODEL", _T("Intersect Faces With Model")),
        ("CONTEXT", _T("Intersect Faces With Context")),
        ("SELECTION", _T("Intersect Faces With Selection")),
    ):
        operator = layout.operator("sketchup.intersect_faces", text=label)
        operator.scope = scope
    layout.operator("sketchup.hide", text=_T("Hide"))
    layout.operator("sketchup.unhide_all", text=_T("Unhide All"))
    layout.operator("sketchup.unhide_last", text=_T("Unhide Last"))
    layout.operator("sketchup.delete_guides", text=_T("Delete Guides"))


def register():
    bpy.types.VIEW3D_MT_object_context_menu.append(_draw_object_menu)
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.append(_draw_edit_mesh_menu)


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(_draw_edit_mesh_menu)
    bpy.types.VIEW3D_MT_object_context_menu.remove(_draw_object_menu)
