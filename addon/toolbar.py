"""Toolbar: WorkSpaceTool entries for the Large Tool Set.

P1: Select / Line / Eraser are real tools whose keymap invokes the
modal operators (the tool stays active; each click re-invokes the
operator, SketchUp-style). They register in both OBJECT and EDIT_MESH
modes under the same idname (standard Blender pattern). The remaining
entries are P0 placeholders until their tools land. Icons are Blender
built-in placeholders; custom SketchUp-style icons arrive later.
"""

import bpy

# (tool id, label, description, Blender icon name, operator idname or None)
_TOOL_SPECS = [
    (
        "select",
        "Select",
        "SketchUp Select tool.",
        "ops.generic.select_box",
        "sketchup.tool_select",
    ),
    (
        "line",
        "Line",
        "SketchUp Line tool.",
        "ops.gpencil.draw",
        "sketchup.tool_line",
    ),
    (
        "eraser",
        "Eraser",
        "SketchUp Eraser tool.",
        "ops.gpencil.eraser",
        "sketchup.tool_eraser",
    ),
    (
        "rectangle",
        "Rectangle",
        "SketchUp Rectangle tool.",
        "ops.mesh.primitive_plane_add",
        "sketchup.tool_rectangle",
    ),
    (
        "rotated_rectangle",
        "Rotated Rectangle",
        "SketchUp Rotated Rectangle tool.",
        "ops.mesh.primitive_plane_add",
        "sketchup.tool_rotated_rectangle",
    ),
    (
        "circle",
        "Circle",
        "SketchUp Circle tool.",
        "ops.mesh.primitive_circle_add",
        "sketchup.tool_circle",
    ),
    (
        "polygon",
        "Polygon",
        "SketchUp Polygon tool.",
        "ops.mesh.primitive_circle_add",
        "sketchup.tool_polygon",
    ),
    (
        "arc",
        "Arc",
        "SketchUp Arc tool.",
        "ops.mesh.primitive_torus_add",
        "sketchup.tool_arc",
    ),
    (
        "arc_2_point",
        "2-Point Arc",
        "SketchUp 2-Point Arc tool.",
        "ops.mesh.primitive_torus_add",
        "sketchup.tool_arc_2_point",
    ),
    (
        "arc_3_point",
        "3-Point Arc",
        "SketchUp 3-Point Arc tool.",
        "ops.mesh.primitive_torus_add",
        "sketchup.tool_arc_3_point",
    ),
    (
        "pie",
        "Pie",
        "SketchUp Pie tool.",
        "ops.mesh.primitive_cone_add",
        "sketchup.tool_pie",
    ),
    (
        "freehand",
        "Freehand",
        "SketchUp Freehand tool.",
        "ops.gpencil.draw",
        "sketchup.tool_freehand",
    ),
    (
        "move",
        "Move",
        "SketchUp Move tool.",
        "ops.transform.translate",
        "sketchup.tool_move",
    ),
    (
        "push_pull",
        "Push/Pull",
        "SketchUp Push/Pull tool.",
        "ops.mesh.extrude_region_move",
        "sketchup.tool_push_pull",
    ),
    (
        "rotate",
        "Rotate",
        "SketchUp Rotate tool.",
        "ops.transform.rotate",
        "sketchup.tool_rotate",
    ),
    (
        "follow_me",
        "Follow Me",
        "SketchUp Follow Me tool.",
        "ops.mesh.extrude_faces_move",
        "sketchup.tool_follow_me",
    ),
    (
        "scale",
        "Scale",
        "SketchUp Scale tool.",
        "ops.transform.resize",
        "sketchup.tool_scale",
    ),
    (
        "offset",
        "Offset",
        "SketchUp Offset tool.",
        "ops.mesh.offset_edge_loops_slide",
        "sketchup.tool_offset",
    ),
    (
        "flip",
        "Flip",
        "SketchUp Flip tool.",
        "ops.gpencil.edit_mirror",
        "sketchup.tool_flip",
    ),
    (
        "tape_measure",
        "Tape Measure",
        "SketchUp Tape Measure tool.",
        "ops.view3d.ruler",
        "sketchup.tool_tape_measure",
    ),
    (
        "protractor",
        "Protractor",
        "SketchUp Protractor tool.",
        "ops.view3d.ruler",
        "sketchup.tool_protractor",
    ),
    (
        "axes",
        "Axes",
        "SketchUp Axes tool.",
        "ops.view3d.view_orbit",
        "sketchup.tool_axes",
    ),
    (
        "dimension",
        "Dimension",
        "SketchUp Dimension tool.",
        "ops.view3d.ruler",
        "sketchup.tool_dimension",
    ),
    (
        "text",
        "Text",
        "SketchUp Text tool.",
        "ops.gpencil.draw",
        "sketchup.tool_text",
    ),
    (
        "paint_bucket",
        "Paint Bucket",
        "SketchUp Paint Bucket tool.",
        "ops.paint.sample_color",
        "sketchup.tool_paint_bucket",
    ),
    (
        "tag",
        "Tag",
        "SketchUp Tag tool.",
        "ops.generic.select_box",
        "sketchup.tool_tag",
    ),
    (
        "section_plane",
        "Section Plane",
        "SketchUp Section Plane tool.",
        "ops.mesh.knife_tool",
        "sketchup.tool_section_plane",
    ),
    (
        "lasso",
        "Lasso",
        "SketchUp Lasso tool.",
        "ops.generic.select_lasso",
        "sketchup.tool_lasso",
    ),
    (
        "orbit",
        "Orbit",
        "SketchUp Orbit tool.",
        "ops.view3d.view_orbit",
        "sketchup.tool_orbit",
    ),
    (
        "pan",
        "Pan",
        "SketchUp Pan tool.",
        "ops.view3d.view_pan",
        "sketchup.tool_pan",
    ),
    (
        "zoom",
        "Zoom",
        "SketchUp Zoom tool.",
        "ops.view3d.zoom",
        "sketchup.tool_zoom",
    ),
    (
        "zoom_window",
        "Zoom Window",
        "SketchUp Zoom Window tool.",
        "ops.view3d.zoom_border",
        "sketchup.tool_zoom_window",
    ),
    (
        "position_camera",
        "Position Camera",
        "SketchUp Position Camera tool.",
        "ops.view3d.view_camera",
        "sketchup.tool_position_camera",
    ),
    (
        "walk",
        "Walk",
        "SketchUp Walk tool.",
        "ops.view3d.view_camera",
        "sketchup.tool_walk",
    ),
    (
        "look_around",
        "Look Around",
        "SketchUp Look Around tool.",
        "ops.view3d.view_camera",
        "sketchup.tool_look_around",
    ),
]


def _make_tool_class(tool_id, label, description, icon, operator_id, mode):
    attrs = {
        "bl_space_type": "VIEW_3D",
        "bl_context_mode": mode,
        "bl_idname": "sketchup." + tool_id + ("_stub" if operator_id is None else ""),
        "bl_label": label,
        "bl_description": description,
        "bl_icon": icon,
        "__module__": __name__,
    }
    if operator_id is not None:
        attrs["bl_keymap"] = (
            (operator_id, {"type": "LEFTMOUSE", "value": "PRESS"}, {}),
        )
    return type(
        "SketchUpTool_" + tool_id + "_" + mode.lower(),
        (bpy.types.WorkSpaceTool,),
        attrs,
    )


def _collect_classes():
    classes = []
    for spec in _TOOL_SPECS:
        tool_id, label, description, icon, operator_id = spec
        if operator_id is not None:
            for mode in ("OBJECT", "EDIT_MESH"):
                classes.append(
                    _make_tool_class(tool_id, label, description, icon, operator_id, mode)
                )
        else:
            classes.append(
                _make_tool_class(tool_id, label, description, icon, None, "OBJECT")
            )
    return classes


TOOL_CLASSES = _collect_classes()


def register():
    for index, cls in enumerate(TOOL_CLASSES):
        bpy.utils.register_tool(
            cls, separator=(index == 0), group=(index == 0)
        )


def unregister():
    for cls in reversed(TOOL_CLASSES):
        bpy.utils.unregister_tool(cls)
