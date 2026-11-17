"""Section commands: activate / reverse / delete / slice / toggle."""

import bpy

from ..context import undo_push
from ..data import sections as sections_mod
from ..i18n.translations import translate as _T


def _plane_or_report(operator, context, name):
    plane = bpy.data.objects.get(name)
    if plane is None or not plane.get(sections_mod.PROP_SECTION, False):
        operator.report({"WARNING"}, _T("Section plane not found"))
        return None
    return plane


class SKETCHUP_OT_section_activate(bpy.types.Operator):
    bl_idname = "sketchup.section_activate"
    bl_label = "Activate Section"
    bl_description = "Make this section plane the active cut"
    bl_options = {"REGISTER", "UNDO"}

    plane_name: bpy.props.StringProperty(name="Plane", default="")

    def execute(self, context):
        plane = _plane_or_report(self, context, self.plane_name)
        if plane is None:
            return {"CANCELLED"}
        sections_mod.set_active_section(context.scene, plane)
        undo_push("SketchUp Section")
        return {"FINISHED"}


class SKETCHUP_OT_section_deactivate(bpy.types.Operator):
    bl_idname = "sketchup.section_deactivate"
    bl_label = "Deactivate Section"
    bl_description = "Remove the active section cut"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sections_mod.set_active_section(context.scene, None)
        undo_push("SketchUp Section")
        return {"FINISHED"}


class SKETCHUP_OT_section_reverse(bpy.types.Operator):
    bl_idname = "sketchup.section_reverse"
    bl_label = "Reverse Section"
    bl_description = "Flip the section plane to cut the other side"
    bl_options = {"REGISTER", "UNDO"}

    plane_name: bpy.props.StringProperty(name="Plane", default="")

    def execute(self, context):
        plane = _plane_or_report(self, context, self.plane_name)
        if plane is None:
            return {"CANCELLED"}
        sections_mod.reverse_section(plane)
        sections_mod.refresh_section_cut(context.scene)
        undo_push("SketchUp Section")
        return {"FINISHED"}


class SKETCHUP_OT_section_delete(bpy.types.Operator):
    bl_idname = "sketchup.section_delete"
    bl_label = "Delete Section"
    bl_description = "Delete the section plane"
    bl_options = {"REGISTER", "UNDO"}

    plane_name: bpy.props.StringProperty(name="Plane", default="")

    def execute(self, context):
        plane = _plane_or_report(self, context, self.plane_name)
        if plane is None:
            return {"CANCELLED"}
        was_active = bool(plane.get(sections_mod.PROP_ACTIVE, False))
        bpy.data.objects.remove(plane, do_unlink=True)
        if was_active:
            sections_mod.refresh_section_cut(context.scene)
        undo_push("SketchUp Section")
        return {"FINISHED"}


class SKETCHUP_OT_section_slice(bpy.types.Operator):
    bl_idname = "sketchup.section_slice"
    bl_label = "Create Group from Slice"
    bl_description = "Create a group of edges where the active section cuts the model"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        plane = sections_mod.get_active_section(context.scene)
        if plane is None:
            self.report({"WARNING"}, _T("No active section plane"))
            return {"CANCELLED"}
        sliced = sections_mod.slice_section(context.scene, plane)
        undo_push("SketchUp Section Slice")
        self.report(
            {"INFO"},
            _T("Slice created: %d edges") % len(sliced.data.edges),
        )
        return {"FINISHED"}


class SKETCHUP_OT_section_toggle_cuts(bpy.types.Operator):
    bl_idname = "sketchup.section_toggle_cuts"
    bl_label = "Toggle Section Cuts"
    bl_description = "Show or hide the active section cut"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        scene["su_sections_enabled"] = not scene.get(
            "su_sections_enabled", True
        )
        sections_mod.refresh_section_cut(scene)
        undo_push("SketchUp Section")
        return {"FINISHED"}


SECTION_OPERATORS = [
    SKETCHUP_OT_section_activate,
    SKETCHUP_OT_section_deactivate,
    SKETCHUP_OT_section_reverse,
    SKETCHUP_OT_section_delete,
    SKETCHUP_OT_section_slice,
    SKETCHUP_OT_section_toggle_cuts,
]
