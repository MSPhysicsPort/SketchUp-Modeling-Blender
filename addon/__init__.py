"""SketchUp Modeling: model in Blender with SketchUp tools and logic.

P1: inference engine, face creation/healing, VCB input, and the
Select / Line / Eraser modal tools, on top of the P0 skeleton
(Extension packaging, menu/panel/toolbar skeletons driven by one
data table, keymap switch, version adaptation layer, translation).

Extension format only: no ``bl_info``. Registration order follows
proposal §5.1; register() never touches bpy.context / bpy.data.
"""

import bpy

from . import keymaps, menus, menus_context, mode, panels, panels_annotations, panels_curve, panels_materials, panels_organize, panels_scenes, panels_sections, panels_tags, preferences, scene_props, session_props, toolbar, vcb_display
from .core.state import reset_session
from .i18n import translations
from .operators import EDIT_OPERATORS, GROUP_OPERATORS, SCENE_OPERATORS, SECTION_OPERATORS, SKETCHUP_OT_stub, SOLID_OPERATORS, TAG_OPERATORS, TEXT_OPERATORS
from .tools import TOOL_OPERATORS
from .tools.curve_ops import CURVE_OPERATORS


def _deferred_restore_conflicts():
    """Restore defaults disabled by a previous session.

    Runs once shortly after startup, when the active keyconfig's
    keymaps are guaranteed loaded (they may not be during
    register()). Skipped while SU Mode is on: the mode-off path
    owns the restore then.
    """
    try:
        if not mode.is_on(bpy.context):
            keymaps.restore_conflicts()
    except Exception:
        pass
    return None


def register():
    translations.register(__package__)
    bpy.utils.register_class(preferences.SketchUpPreferences)
    session_props.register()
    scene_props.register()
    bpy.utils.register_class(SKETCHUP_OT_stub)
    for cls in GROUP_OPERATORS:
        bpy.utils.register_class(cls)
    for cls in EDIT_OPERATORS:
        bpy.utils.register_class(cls)
    for cls in TAG_OPERATORS:
        bpy.utils.register_class(cls)
    for cls in SECTION_OPERATORS:
        bpy.utils.register_class(cls)
    for cls in SOLID_OPERATORS:
        bpy.utils.register_class(cls)
    for cls in TEXT_OPERATORS:
        bpy.utils.register_class(cls)
    for cls in SCENE_OPERATORS:
        bpy.utils.register_class(cls)
    for cls in TOOL_OPERATORS:
        bpy.utils.register_class(cls)
    for cls in CURVE_OPERATORS:
        bpy.utils.register_class(cls)
    menus.register()
    menus_context.register()
    panels.register()
    panels_curve.register()
    panels_organize.register()
    panels_tags.register()
    panels_materials.register()
    panels_sections.register()
    panels_annotations.register()
    panels_scenes.register()
    toolbar.register()
    vcb_display.register()
    mode.register()
    # SU Mode defaults to OFF: no keymaps are registered until the
    # user flips the switch. Restore anything a previous session
    # left disabled (e.g. prefs saved while the mode was on).
    if not bpy.app.background:
        bpy.app.timers.register(_deferred_restore_conflicts, first_interval=1.0)


def unregister():
    mode.unregister()
    keymaps.unregister_keymaps()
    vcb_display.unregister()
    toolbar.unregister()
    panels_scenes.unregister()
    panels_annotations.unregister()
    panels_sections.unregister()
    panels_materials.unregister()
    panels_tags.unregister()
    panels_organize.unregister()
    panels_curve.unregister()
    panels.unregister()
    menus_context.unregister()
    menus.unregister()
    for cls in reversed(CURVE_OPERATORS):
        bpy.utils.unregister_class(cls)
    for cls in reversed(TOOL_OPERATORS):
        bpy.utils.unregister_class(cls)
    for cls in reversed(EDIT_OPERATORS):
        bpy.utils.unregister_class(cls)
    for cls in reversed(TAG_OPERATORS):
        bpy.utils.unregister_class(cls)
    for cls in reversed(SECTION_OPERATORS):
        bpy.utils.unregister_class(cls)
    for cls in reversed(SOLID_OPERATORS):
        bpy.utils.unregister_class(cls)
    for cls in reversed(TEXT_OPERATORS):
        bpy.utils.unregister_class(cls)
    for cls in reversed(SCENE_OPERATORS):
        bpy.utils.unregister_class(cls)
    for cls in reversed(GROUP_OPERATORS):
        bpy.utils.unregister_class(cls)
    bpy.utils.unregister_class(SKETCHUP_OT_stub)
    scene_props.unregister()
    session_props.unregister()
    bpy.utils.unregister_class(preferences.SketchUpPreferences)
    translations.unregister(__package__)
    reset_session()
