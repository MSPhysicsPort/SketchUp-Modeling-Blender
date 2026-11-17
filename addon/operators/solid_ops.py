"""Solid Tools menu commands: Outer Shell, Union, Subtract, Trim,
Intersect, Split. The active object is the tool; other selected
solids are the targets.
"""

import bpy

from ..context import undo_push
from ..core import solid as solid_mod
from ..i18n.translations import translate as _T


def _make_operator(op_id, label, operation):
    class SolidToolOperator(bpy.types.Operator):
        bl_idname = op_id
        bl_label = label
        bl_description = "Solid Tool: %s" % label
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            ok, message = solid_mod.run_solid_tool(context, operation)
            if not ok:
                self.report({"WARNING"}, _T(message))
                return {"CANCELLED"}
            undo_push("SketchUp Solid %s" % operation.title())
            self.report({"INFO"}, _T(message))
            return {"FINISHED"}

    SolidToolOperator.__name__ = "SKETCHUP_OT_solid_" + operation.lower()
    return SolidToolOperator


SKETCHUP_OT_solid_outer_shell = _make_operator(
    "sketchup.solid_outer_shell", "Outer Shell", "UNION"
)
SKETCHUP_OT_solid_union = _make_operator(
    "sketchup.solid_union", "Union", "UNION"
)
SKETCHUP_OT_solid_subtract = _make_operator(
    "sketchup.solid_subtract", "Subtract", "SUBTRACT"
)
SKETCHUP_OT_solid_trim = _make_operator(
    "sketchup.solid_trim", "Trim", "TRIM"
)
SKETCHUP_OT_solid_intersect = _make_operator(
    "sketchup.solid_intersect", "Intersect", "INTERSECT"
)
SKETCHUP_OT_solid_split = _make_operator(
    "sketchup.solid_split", "Split", "SPLIT"
)

SOLID_OPERATORS = [
    SKETCHUP_OT_solid_outer_shell,
    SKETCHUP_OT_solid_union,
    SKETCHUP_OT_solid_subtract,
    SKETCHUP_OT_solid_trim,
    SKETCHUP_OT_solid_intersect,
    SKETCHUP_OT_solid_split,
]
