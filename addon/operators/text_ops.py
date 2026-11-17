"""Text input dialog, 3D Text, and annotation deletion."""

import bpy
from mathutils import Vector

from ..context import undo_push
from ..data import annotations as annotations_mod
from ..draw.overlay import find_cjk_font
from ..i18n.translations import translate as _T


def _has_cjk(text):
    return any(
        "\u4e00" <= ch <= "\u9fff"
        or "\u3040" <= ch <= "\u30ff"
        or "\uac00" <= ch <= "\ud7a3"
        for ch in text
    )


class SKETCHUP_OT_text_input(bpy.types.Operator):
    bl_idname = "sketchup.text_input"
    bl_label = "Text Note"
    bl_description = "Type the text for the leader note"
    bl_options = {"REGISTER", "UNDO"}

    text: bpy.props.StringProperty(name="Text", default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def execute(self, context):
        from ..tools.annotate import _pending_text

        point = _pending_text["point"]
        if point is None or not self.text.strip():
            return {"CANCELLED"}
        annotations_mod.add_text(
            context.scene,
            Vector(point),
            self.text.strip(),
            _pending_text["anchor_offset"],
        )
        _pending_text["point"] = None
        undo_push("SketchUp Text")
        return {"FINISHED"}


class SKETCHUP_OT_text_3d(bpy.types.Operator):
    bl_idname = "sketchup.text_3d"
    bl_label = "3D Text"
    bl_description = "Create extruded 3D text as a mesh object"
    bl_options = {"REGISTER", "UNDO"}

    text: bpy.props.StringProperty(name="Text", default="SketchUp")
    height: bpy.props.FloatProperty(
        name="Height (m)", default=0.3, min=0.001
    )
    depth: bpy.props.FloatProperty(
        name="Depth (m)", default=0.0, min=0.0
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def execute(self, context):
        if not self.text.strip():
            self.report({"WARNING"}, _T("Enter some text first"))
            return {"CANCELLED"}
        curve_data = bpy.data.curves.new("SU 3D Text", "FONT")
        curve_data.body = self.text
        curve_data.size = self.height
        curve_data.extrude = self.depth * 0.5
        if _has_cjk(self.text):
            font_path = find_cjk_font()
            if font_path is not None:
                try:
                    curve_data.font = bpy.data.fonts.load(font_path)
                except Exception:
                    pass
        curve_obj = bpy.data.objects.new("SU 3D Text", curve_data)
        context.scene.collection.objects.link(curve_obj)
        try:
            cursor = context.scene.cursor.location
        except Exception:
            cursor = Vector((0, 0, 0))
        curve_obj.location = Vector(cursor)
        depsgraph = context.evaluated_depsgraph_get()
        evaluated = curve_obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        kept = mesh.copy() if mesh is not None else None
        evaluated.to_mesh_clear()
        bpy.data.objects.remove(curve_obj, do_unlink=True)
        bpy.data.curves.remove(curve_data)
        if kept is None or not kept.polygons:
            if kept is not None:
                bpy.data.meshes.remove(kept)
            self.report({"WARNING"}, _T("Could not build 3D text"))
            return {"CANCELLED"}
        obj = bpy.data.objects.new("3D Text", kept)
        obj.location = Vector(cursor)
        context.scene.collection.objects.link(obj)
        undo_push("SketchUp 3D Text")
        return {"FINISHED"}


class SKETCHUP_OT_annotation_delete(bpy.types.Operator):
    bl_idname = "sketchup.annotation_delete"
    bl_label = "Delete Annotation"
    bl_description = "Delete a dimension or text note"
    bl_options = {"REGISTER", "UNDO"}

    index: bpy.props.IntProperty(name="Index", default=-1)

    def execute(self, context):
        if annotations_mod.remove_annotation(context.scene, self.index):
            undo_push("SketchUp Delete Annotation")
            return {"FINISHED"}
        return {"CANCELLED"}


class SKETCHUP_OT_annotations_clear(bpy.types.Operator):
    bl_idname = "sketchup.annotations_clear"
    bl_label = "Delete All Annotations"
    bl_description = "Delete all dimensions and text notes"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        annotations_mod.save_annotations(context.scene, [])
        undo_push("SketchUp Delete Annotations")
        return {"FINISHED"}


TEXT_OPERATORS = [
    SKETCHUP_OT_text_input,
    SKETCHUP_OT_text_3d,
    SKETCHUP_OT_annotation_delete,
    SKETCHUP_OT_annotations_clear,
]
