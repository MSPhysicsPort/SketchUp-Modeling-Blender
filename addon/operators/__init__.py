"""Operators package: the placeholder stub plus one-shot commands."""

import bpy

from ..i18n.translations import translate as _T
from .edit_ops import EDIT_OPERATORS
from .groups import GROUP_OPERATORS
from .scene_ops import SCENE_OPERATORS
from .section_ops import SECTION_OPERATORS
from .solid_ops import SOLID_OPERATORS
from .tag_ops import TAG_OPERATORS
from .text_ops import TEXT_OPERATORS

__all__ = ["SKETCHUP_OT_stub", "GROUP_OPERATORS", "EDIT_OPERATORS", "TAG_OPERATORS", "SECTION_OPERATORS", "SOLID_OPERATORS", "TEXT_OPERATORS", "SCENE_OPERATORS"]


class SKETCHUP_OT_stub(bpy.types.Operator):
    """Placeholder for SketchUp tools not yet implemented (P0 skeleton)."""

    bl_idname = "sketchup.stub"
    bl_label = "SketchUp (Not Yet Implemented)"
    bl_description = "Placeholder for SketchUp tools not yet implemented"

    tool_id: bpy.props.StringProperty(
        name="Tool ID",
        description="Identifier of the SketchUp tool from the data table",
        default="",
    )

    def execute(self, context):
        self.report(
            {"INFO"},
            _T("SketchUp tool '%s' is not implemented yet (P0 skeleton).")
            % (self.tool_id or "unknown",),
        )
        return {"FINISHED"}
