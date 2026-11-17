"""Outliner and Entity Info panels (SketchUp Default Tray equivalents).

Outliner: the model tree (nesting = object parenting), with rename,
visibility, select and edit-context navigation. Entity Info: the
active object's identity, size and contents.
"""

import bpy

from .core import containers
from .i18n.translations import translate as _T


def _kind_icon(obj):
    if containers.is_component(obj):
        return "OUTLINER_OB_MESH"
    if containers.is_group(obj):
        return "OUTLINER_COLLECTION"
    if obj.type == "MESH":
        return "MESH_DATA"
    if obj.type == "EMPTY":
        return "EMPTY_DATA"
    return "OBJECT_DATA"


def _draw_tree(layout, obj, depth, context):
    row = layout.row(align=True)
    row.label(text="  " * depth + "", icon="BLANK1")
    row.label(text="", icon=_kind_icon(obj))
    row.prop(obj, "name", text="")
    row.prop(obj, "hide_viewport", text="", icon="HIDE_OFF", toggle=True)
    if containers.is_container(obj):
        row.operator("sketchup.edit_container", text=_T("Edit"))
    for child in obj.children:
        if depth < 12:
            _draw_tree(layout, child, depth + 1, context)


class SKETCHUP_PT_outliner(bpy.types.Panel):
    bl_idname = "SKETCHUP_PT_outliner"
    bl_label = "Outliner"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SketchUp"

    def draw(self, context):
        layout = self.layout
        roots = [o for o in context.scene.objects if o.parent is None]
        if not roots:
            layout.label(text=_T("Empty model"))
            return
        for obj in roots:
            _draw_tree(layout, obj, 0, context)
        layout.separator()
        row = layout.row(align=True)
        row.operator("sketchup.make_group", text=_T("Make Group"))
        row.operator("sketchup.make_component", text=_T("Make Component"))


def _mesh_stats(obj):
    mesh = obj.data
    verts = len(mesh.vertices)
    edges = len(mesh.edges)
    faces = len(mesh.polygons)
    area = sum(p.area for p in mesh.polygons)
    volume = 0.0
    try:
        import bmesh

        bm = bmesh.new()
        bm.from_mesh(mesh)
        try:
            volume = bm.calc_volume()
        finally:
            bm.free()
    except Exception:
        pass
    return verts, edges, faces, area, volume


class SKETCHUP_PT_entity_info(bpy.types.Panel):
    bl_idname = "SKETCHUP_PT_entity_info"
    bl_label = "Entity Info"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SketchUp"

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        if obj is None:
            layout.label(text=_T("Nothing selected"))
            return
        layout.prop(obj, "name", text=_T("Name"))
        kind = containers.kind_of(obj)
        if kind:
            row = layout.row()
            row.label(text=_T("Type:"))
            row.label(
                text=_T("Component") if kind == "COMPONENT" else _T("Group")
            )
            if kind == "COMPONENT":
                row = layout.row()
                row.label(text=_T("Definition:"))
                row.label(text=containers.definition_name(obj))
                row = layout.row()
                row.label(text=_T("Instances:"))
                row.label(text=str(len(containers.instances_of(obj.data))))
        row = layout.row()
        row.label(text=_T("Locked:"))
        row.label(text=_T("Yes") if containers.is_locked(obj) else _T("No"))
        if obj.type == "MESH":
            verts, edges, faces, area, volume = _mesh_stats(obj)
            for label, value in (
                (_T("Vertices:"), str(verts)),
                (_T("Edges:"), str(edges)),
                (_T("Faces:"), str(faces)),
                (_T("Area:"), "%.4f m²" % area),
                (_T("Volume:"), "%.4f m³" % volume),
            ):
                row = layout.row()
                row.label(text=label)
                row.label(text=value)
            row = layout.row()
            row.label(text=_T("Dimensions:"))
            row.label(
                text="%.3f × %.3f × %.3f" % tuple(obj.dimensions)
            )
        if containers.is_container(obj):
            layout.separator()
            row = layout.row(align=True)
            row.operator("sketchup.edit_container", text=_T("Edit"))
            row.operator("sketchup.explode", text=_T("Explode"))
            row = layout.row(align=True)
            row.operator("sketchup.make_unique", text=_T("Make Unique"))
            row.operator("sketchup.reset_scale", text=_T("Reset Scale"))


ORGANIZE_PANEL_CLASSES = [SKETCHUP_PT_outliner, SKETCHUP_PT_entity_info]


def register():
    for cls in ORGANIZE_PANEL_CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(ORGANIZE_PANEL_CLASSES):
        bpy.utils.unregister_class(cls)
