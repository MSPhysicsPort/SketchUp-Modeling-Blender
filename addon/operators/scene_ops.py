"""Scene commands and style presets."""

import bpy

from ..context import undo_push
from ..data import scenes as scenes_mod
from ..i18n.translations import translate as _T


class SKETCHUP_OT_scene_add(bpy.types.Operator):
    bl_idname = "sketchup.scene_add"
    bl_label = "Add Scene"
    bl_description = "Save the current view and visibility as a scene"
    bl_options = {"REGISTER", "UNDO"}

    name: bpy.props.StringProperty(name="Name", default="Scene")

    def invoke(self, context, event):
        count = len(scenes_mod.get_scenes(context.scene))
        self.name = "Scene %d" % (count + 1)
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        name = scenes_mod.add_scene(context, self.name.strip() or "Scene")
        undo_push("SketchUp Add Scene")
        self.report({"INFO"}, _T("Scene added: %s") % name)
        return {"FINISHED"}


class SKETCHUP_OT_scene_apply(bpy.types.Operator):
    bl_idname = "sketchup.scene_apply"
    bl_label = "Apply Scene"
    bl_description = "Restore a saved scene"
    bl_options = {"REGISTER", "UNDO"}

    index: bpy.props.IntProperty(name="Index", default=-1)

    def execute(self, context):
        entries = scenes_mod.get_scenes(context.scene)
        if not (0 <= self.index < len(entries)):
            return {"CANCELLED"}
        scenes_mod.apply_scene(context, entries[self.index])
        undo_push("SketchUp Apply Scene")
        return {"FINISHED"}


class SKETCHUP_OT_scene_update(bpy.types.Operator):
    bl_idname = "sketchup.scene_update"
    bl_label = "Update Scene"
    bl_description = "Overwrite a scene with the current state"
    bl_options = {"REGISTER", "UNDO"}

    index: bpy.props.IntProperty(name="Index", default=-1)

    def execute(self, context):
        if scenes_mod.update_scene(context, self.index):
            undo_push("SketchUp Update Scene")
            return {"FINISHED"}
        return {"CANCELLED"}


class SKETCHUP_OT_scene_delete(bpy.types.Operator):
    bl_idname = "sketchup.scene_delete"
    bl_label = "Delete Scene"
    bl_description = "Delete a saved scene"
    bl_options = {"REGISTER", "UNDO"}

    index: bpy.props.IntProperty(name="Index", default=-1)

    def execute(self, context):
        if scenes_mod.delete_scene(context.scene, self.index):
            undo_push("SketchUp Delete Scene")
            return {"FINISHED"}
        return {"CANCELLED"}


STYLE_PRESETS = {
    "SHADED": {"type": "SOLID", "color_type": "MATERIAL", "show_xray": False, "show_shadows": True},
    "TEXTURED": {"type": "MATERIAL", "show_xray": False},
    "HIDDEN_LINE": {"type": "SOLID", "color_type": "SINGLE", "show_xray": False, "show_shadows": False},
    "WIREFRAME": {"type": "WIREFRAME"},
    "XRAY": {"type": "SOLID", "color_type": "MATERIAL", "show_xray": True},
}


class SKETCHUP_OT_style_preset(bpy.types.Operator):
    bl_idname = "sketchup.style_preset"
    bl_label = "Style Preset"
    bl_description = "Apply a SketchUp-style display preset"
    bl_options = {"REGISTER"}

    preset: bpy.props.StringProperty(name="Preset", default="SHADED")

    def execute(self, context):
        shading = getattr(context.space_data, "shading", None)
        if shading is None:
            return {"CANCELLED"}
        settings = STYLE_PRESETS.get(self.preset)
        if settings is None:
            return {"CANCELLED"}
        for key, value in settings.items():
            try:
                setattr(shading, key, value)
            except Exception:
                pass
        if self.preset == "HIDDEN_LINE":
            try:
                shading.single_color = (1.0, 1.0, 1.0)
            except Exception:
                pass
        return {"FINISHED"}


SCENE_OPERATORS = [
    SKETCHUP_OT_scene_add,
    SKETCHUP_OT_scene_apply,
    SKETCHUP_OT_scene_update,
    SKETCHUP_OT_scene_delete,
    SKETCHUP_OT_style_preset,
]
