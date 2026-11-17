"""Tag commands: add / delete / rename / visibility / assign."""

import bpy

from ..context import undo_push
from ..data import tags as tags_mod
from ..i18n.translations import translate as _T


class SKETCHUP_OT_tag_add(bpy.types.Operator):
    bl_idname = "sketchup.tag_add"
    bl_label = "Add Tag"
    bl_description = "Add a new tag"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        item = tags_mod.add_tag(context.scene)
        context.scene.su_tags_index = context.scene.su_tags.find(item.name)
        undo_push("SketchUp Add Tag")
        return {"FINISHED"}


class SKETCHUP_OT_tag_delete(bpy.types.Operator):
    bl_idname = "sketchup.tag_delete"
    bl_label = "Delete Tag"
    bl_description = "Delete the active tag (its objects become Untagged)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        name = tags_mod.active_tag_name(scene)
        if not tags_mod.delete_tag(scene, name):
            self.report({"WARNING"}, _T("The Untagged tag cannot be deleted"))
            return {"CANCELLED"}
        undo_push("SketchUp Delete Tag")
        return {"FINISHED"}


class SKETCHUP_OT_tag_rename(bpy.types.Operator):
    bl_idname = "sketchup.tag_rename"
    bl_label = "Rename Tag"
    bl_description = "Rename the active tag"
    bl_options = {"REGISTER", "UNDO"}

    new_name: bpy.props.StringProperty(name="Name", default="")

    def invoke(self, context, event):
        self.new_name = tags_mod.active_tag_name(context.scene)
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        scene = context.scene
        old = tags_mod.active_tag_name(scene)
        if not tags_mod.rename_tag(scene, old, self.new_name.strip()):
            self.report({"WARNING"}, _T("Could not rename the tag"))
            return {"CANCELLED"}
        undo_push("SketchUp Rename Tag")
        return {"FINISHED"}


class SKETCHUP_OT_tag_toggle_visible(bpy.types.Operator):
    bl_idname = "sketchup.tag_toggle_visible"
    bl_label = "Toggle Tag Visibility"
    bl_description = "Show or hide all objects on a tag"
    bl_options = {"REGISTER", "UNDO"}

    tag_name: bpy.props.StringProperty(name="Tag", default="")

    def execute(self, context):
        scene = context.scene
        tag = tags_mod.find_tag(scene, self.tag_name)
        if tag is None:
            return {"CANCELLED"}
        tag.visible = not tag.visible
        tags_mod.apply_visibility(scene)
        undo_push("SketchUp Tag Visibility")
        return {"FINISHED"}


class SKETCHUP_OT_tag_assign(bpy.types.Operator):
    bl_idname = "sketchup.tag_assign"
    bl_label = "Assign Active Tag"
    bl_description = "Assign the active tag to the selected objects"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        name = tags_mod.active_tag_name(scene)
        targets = [o for o in context.selected_objects]
        if context.mode == "EDIT_MESH" and context.active_object is not None:
            targets = [context.active_object]
        if not targets:
            self.report({"WARNING"}, _T("Select something to tag first"))
            return {"CANCELLED"}
        for obj in targets:
            tags_mod.set_object_tag(obj, name)
        undo_push("SketchUp Assign Tag")
        self.report({"INFO"}, _T("Tagged %d objects: %s") % (len(targets), name))
        return {"FINISHED"}


TAG_OPERATORS = [
    SKETCHUP_OT_tag_add,
    SKETCHUP_OT_tag_delete,
    SKETCHUP_OT_tag_rename,
    SKETCHUP_OT_tag_toggle_visible,
    SKETCHUP_OT_tag_assign,
]
