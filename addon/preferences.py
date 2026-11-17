"""Add-on preferences (L1 user settings, proposal §5.7)."""

import bpy

from .i18n.translations import translate as _T


def _on_keymap_level_changed(self, context):
    from . import keymaps, mode

    # The level is only the key variant; keys exist only while SU
    # Mode is on. Changing the variant while the mode is off must
    # not register anything.
    if mode.is_on(context):
        keymaps.apply_level(int(self.keymap_level))
    else:
        keymaps.apply_level(0)


class SketchUpPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    keymap_level: bpy.props.EnumProperty(
        name="Keymap Level",
        description="Which SketchUp shortcut keys are registered",
        items=[
            ("0", "Off", "Register no SketchUp shortcut keys"),
            ("1", "SketchUp Mode", "Register the full SketchUp single-letter keys"),
            ("2", "Combo Keys Only", "SketchUp tools only on Alt/Ctrl combinations"),
        ],
        default="1",
        update=_on_keymap_level_changed,
    )
    default_unit: bpy.props.EnumProperty(
        name="Default Unit",
        description="Unit assumed for bare numbers in VCB input",
        items=[
            ("mm", "Millimeters", "Millimeters"),
            ("cm", "Centimeters", "Centimeters"),
            ("m", "Meters", "Meters"),
            ("in", "Inches", "Inches"),
            ("ft", "Feet", "Feet"),
        ],
        default="mm",
    )
    inference_enabled: bpy.props.BoolProperty(
        name="Enable Inference",
        description="Show SketchUp-style inference markers while drawing",
        default=True,
    )
    disabled_conflicts_json: bpy.props.StringProperty(
        name="Disabled Conflicts",
        description="Blender default shortcuts temporarily disabled by SU Mode (restored on mode off)",
        default="",
        options={"HIDDEN"},
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "keymap_level")
        layout.label(text=_T("Shortcut keys: Space = Select, L = Line, E = Eraser (level 1)."))
        layout.label(
            text=_T(
                "Shortcuts apply only while SketchUp Mode is ON (SU Mode button in the 3D View header)."
            )
        )
        layout.prop(self, "default_unit")
        layout.prop(self, "inference_enabled")
        layout.label(text=_T("Interface language follows Blender preferences."))
