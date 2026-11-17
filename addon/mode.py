"""SketchUp Mode: one master switch between SU modeling and Blender.

Sen's framework (2026-11-17): the plug-in has an activation switch.
ON = "SU modeling mode": SketchUp shortcut keys take over, SU-style
snapping is configured, and the SketchUp Model object is put in
Edit Mode for mesh editing. OFF = plain Blender: the SU keymaps are
removed, the conflicting Blender defaults are re-activated, and the
previous snap/pivot settings and object mode are restored.

The switch is ``WindowManager.sketchup_mode`` (a checkbox in the
N-panel, a button in the 3D View header, and the
``sketchup.toggle_mode`` operator). Changing it runs the full
switch; the operator and the checkbox share one code path. The
default state is OFF: enabling the add-on never touches Blender's
behavior until the user flips the switch.
"""

import bpy

from . import keymaps
from .context import EditContext
from .i18n.translations import translate as _T

# SU-style snapping for native transform tools: endpoints, edges,
# edge midpoints, faces and face centers (SU inference equivalents
# available in Blender's snap system; curve centers are not).
SU_SNAP_ELEMENTS = {"VERTEX", "EDGE", "EDGE_MIDPOINT", "FACE", "FACE_MIDPOINT"}
SU_SNAP_TARGET = "CLOSEST"

# Native Rotate/Scale pivot at the 3D cursor: the wrappers place the
# cursor at the selection center before delegating, so rotation and
# scaling pivot around the selection like SU's center grips.
SU_PIVOT_POINT = "CURSOR"

_SAVED = None  # dict of previous tool settings + mode, while ON.


def is_on(context):
    try:
        return bool(context.window_manager.sketchup_mode)
    except (AttributeError, ReferenceError):
        return False


def _tool_settings(context):
    try:
        return context.scene.tool_settings
    except (AttributeError, ReferenceError):
        return None


def _valid_snap_elements(tool_settings):
    try:
        items = tool_settings.bl_rna.properties["snap_elements"].enum_items
        return {entry.identifier for entry in items}
    except Exception:
        return set(SU_SNAP_ELEMENTS)


def _enter(context):
    """Apply the SU Mode state. Idempotent: safe to call twice."""
    global _SAVED
    if _SAVED is None:
        saved = {"mode": getattr(context, "mode", None)}
        tool_settings = _tool_settings(context)
        if tool_settings is not None:
            saved["use_snap"] = tool_settings.use_snap
            saved["snap_elements"] = set(tool_settings.snap_elements)
            saved["snap_target"] = tool_settings.snap_target
            saved["use_snap_align_rotation"] = tool_settings.use_snap_align_rotation
            saved["transform_pivot_point"] = tool_settings.transform_pivot_point
        _SAVED = saved
    tool_settings = _tool_settings(context)
    if tool_settings is not None:
        try:
            tool_settings.use_snap = True
            valid = _valid_snap_elements(tool_settings)
            tool_settings.snap_elements = SU_SNAP_ELEMENTS & valid or {"VERTEX"}
            tool_settings.snap_target = SU_SNAP_TARGET
            tool_settings.use_snap_align_rotation = False
            tool_settings.transform_pivot_point = SU_PIVOT_POINT
        except Exception:
            pass
    # SU keymaps on, conflicting Blender defaults off.
    level = keymaps._preferred_level()
    if level == 0:
        level = 1
    keymaps.apply_level(level)
    keymaps.disable_conflicts(level)
    # Editing happens on the SketchUp Model object in Edit Mode.
    try:
        edit = EditContext(context)
        from .core import containers

        containers.reset_context_stack(edit.object.name)
    except Exception:
        pass
    # Persistent overlay: guides, sections, axes, annotations.
    try:
        from .draw import viewport_overlay

        viewport_overlay.attach()
    except Exception:
        pass


def _exit(context):
    """Restore the pre-mode state. Idempotent: safe to call twice."""
    global _SAVED
    keymaps.apply_level(0)
    keymaps.restore_conflicts()
    try:
        from .draw import viewport_overlay

        viewport_overlay.detach()
    except Exception:
        pass
    try:
        from .core import containers

        containers.reset_context_stack("")
    except Exception:
        pass
    if _SAVED is not None:
        tool_settings = _tool_settings(context)
        if tool_settings is not None:
            try:
                tool_settings.use_snap = _SAVED.get("use_snap", False)
                tool_settings.snap_elements = _SAVED.get("snap_elements", {"INCREMENT"})
                tool_settings.snap_target = _SAVED.get("snap_target", "CLOSEST")
                tool_settings.use_snap_align_rotation = _SAVED.get(
                    "use_snap_align_rotation", False
                )
                tool_settings.transform_pivot_point = _SAVED.get(
                    "transform_pivot_point", "MEDIAN_POINT"
                )
            except Exception:
                pass
        prev_mode = _SAVED.get("mode")
        _SAVED = None
        if prev_mode != "EDIT_MESH" and getattr(context, "mode", None) == "EDIT_MESH":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:
                pass


def _apply(context, on):
    if on:
        _enter(context)
    else:
        _exit(context)


def set_mode(context, on):
    """Switch SU Mode on/off and keep the flag in sync."""
    _apply(context, on)
    try:
        if context.window_manager.sketchup_mode != on:
            # The update callback re-enters _apply; guard by only
            # assigning when the value actually changes (assignment
            # of the same value does not fire the callback, and a
            # second _apply is idempotent anyway).
            context.window_manager.sketchup_mode = on
    except (AttributeError, ReferenceError):
        pass


def _on_mode_changed(self, context):
    _apply(context, bool(self.sketchup_mode))


class SKETCHUP_OT_toggle_mode(bpy.types.Operator):
    bl_idname = "sketchup.toggle_mode"
    bl_label = "Toggle SketchUp Mode"
    bl_description = "Switch between SketchUp modeling mode and plain Blender"
    bl_options = {"REGISTER"}

    def execute(self, context):
        on = not is_on(context)
        set_mode(context, on)
        if on:
            count = keymaps.our_key_count("3D View")
            self.report(
                {"INFO"},
                _T("SketchUp Mode ON: %d shortcuts active") % count,
            )
        else:
            self.report({"INFO"}, _T("SketchUp Mode OFF: Blender shortcuts restored"))
        return {"FINISHED"}


def _draw_header_button(self, context):
    try:
        active = bool(context.window_manager.sketchup_mode)
    except (AttributeError, ReferenceError):
        active = False
    self.layout.operator(
        "sketchup.toggle_mode", text=_T("SU Mode"), depress=active
    )


def register():
    bpy.types.WindowManager.sketchup_mode = bpy.props.BoolProperty(
        name="SketchUp Mode",
        description="SketchUp modeling mode: SU shortcuts, snapping and Edit Mode",
        default=False,
        update=_on_mode_changed,
    )
    bpy.utils.register_class(SKETCHUP_OT_toggle_mode)
    bpy.types.VIEW3D_HT_header.append(_draw_header_button)


def unregister():
    try:
        if _SAVED is not None:
            _exit(bpy.context)
    except Exception:
        pass
    try:
        from .draw import viewport_overlay

        viewport_overlay.detach()
    except Exception:
        pass
    try:
        bpy.types.VIEW3D_HT_header.remove(_draw_header_button)
    except Exception:
        pass
    bpy.utils.unregister_class(SKETCHUP_OT_toggle_mode)
    try:
        del bpy.types.WindowManager.sketchup_mode
    except Exception:
        pass
