"""SketchUp modeling tools (modal operators)."""

import bpy

from .annotate import ANNOTATE_TOOL_OPERATORS
from .camera_tools import CAMERA_OPERATORS
from .eraser import SKETCHUP_OT_tool_eraser
from .lasso import LASSO_OPERATORS
from .extrude import EXTRUDE_OPERATORS
from .line import SKETCHUP_OT_tool_line
from .measure import MEASURE_OPERATORS
from .paint import PAINT_TOOL_OPERATORS
from .section import SECTION_TOOL_OPERATORS
from .select import SKETCHUP_OT_tool_select
from .shapes import SHAPE_OPERATORS
from .tag_tool import TAG_TOOL_OPERATORS
from .transforms import TRANSFORM_OPERATORS

TOOL_OPERATORS = (
    [
        SKETCHUP_OT_tool_select,
        SKETCHUP_OT_tool_line,
        SKETCHUP_OT_tool_eraser,
    ]
    + SHAPE_OPERATORS
    + TRANSFORM_OPERATORS
    + EXTRUDE_OPERATORS
    + TAG_TOOL_OPERATORS
    + PAINT_TOOL_OPERATORS
    + SECTION_TOOL_OPERATORS
    + MEASURE_OPERATORS
    + ANNOTATE_TOOL_OPERATORS
    + CAMERA_OPERATORS
    + LASSO_OPERATORS
)


def register():
    for cls in TOOL_OPERATORS:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(TOOL_OPERATORS):
        bpy.utils.unregister_class(cls)
