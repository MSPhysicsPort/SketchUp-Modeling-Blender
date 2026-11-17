"""Transform flows: native Move/Rotate/Scale execute paths plus the
P3 PushPull/
Offset/FollowMe/Flip tools with synthetic events and assert mesh
state. Runs inside Blender via run_t2.py or run_modal_standalone.
"""

import bpy
from modal_flows import FAILED, approx, check  # noqa: F401
from modal_harness import (
    ToolDriver,
    clear_scene,
    edge_coords,
    make_context,
    mesh_stats,
    sketchup_mesh,
    vertex_coords,
)


def draw_rect(module, x1=0, y1=0, x2=200, y2=100):
    context = make_context()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_rectangle, context).start()
    driver.click(x1, y1)
    driver.click(x2, y2)
    driver.finish()
    return context


def select_all():
    mesh = sketchup_mesh()
    for vert in mesh.vertices:
        vert.select = True
    for edge in mesh.edges:
        edge.select = True
    for poly in mesh.polygons:
        poly.select = True
    bpy.context.view_layer.objects.active = bpy.data.objects.get("SketchUp Model")


def select_edges(predicate):
    mesh = sketchup_mesh()
    for edge in mesh.edges:
        edge.select = False
    for vert in mesh.vertices:
        vert.select = False
    for poly in mesh.polygons:
        poly.select = False
    verts = [tuple(v.co) for v in mesh.vertices]
    for edge in mesh.edges:
        a, b = verts[edge.vertices[0]], verts[edge.vertices[1]]
        if predicate(a, b):
            edge.select = True
    bpy.context.view_layer.objects.active = bpy.data.objects.get("SketchUp Model")


def rounded_coords(places=6):
    return sorted(
        tuple(round(c, places) for c in co) for co in vertex_coords()
    )


# ---------------------------------------------------------------------------
# Move / Rotate / Scale: native-transform delegates (0.5.0).
#
# The modal tools were replaced by thin wrappers over
# transform.translate/rotate/resize, so these scenarios drive the
# operators' execute() paths in real Edit Mode (headless mode_set
# works) and flush to Object Mode before asserting mesh data.
# ---------------------------------------------------------------------------


def edit_mode():
    bpy.ops.object.mode_set(mode="EDIT")


def object_mode():
    if bpy.context.mode == "EDIT_MESH":
        bpy.ops.object.mode_set(mode="OBJECT")


def scenario_move_execute(module):
    clear_scene()
    draw_rect(module)
    select_all()
    edit_mode()
    result = bpy.ops.sketchup.tool_move(vector=(1.0, 0.0, 0.0))
    object_mode()
    check("move execute ok", result == {"FINISHED"}, str(result))
    check(
        "move execute +1x",
        rounded_coords() == [(1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (3.0, 0.0, 0.0), (3.0, 1.0, 0.0)],
        str(rounded_coords()),
    )


def scenario_move_copy_execute(module):
    clear_scene()
    draw_rect(module)
    select_all()
    edit_mode()
    bpy.ops.sketchup.tool_move(vector=(1.0, 0.0, 0.0), copy=True)
    object_mode()
    check("move copy 8/8/2", mesh_stats() == (8, 8, 2), str(mesh_stats()))
    check(
        "move copy coords",
        rounded_coords()
        == [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0),
            (2.0, 0.0, 0.0), (2.0, 1.0, 0.0), (3.0, 0.0, 0.0), (3.0, 1.0, 0.0)],
        str(rounded_coords()),
    )


def scenario_move_array_external(module):
    clear_scene()
    draw_rect(module)
    select_all()
    edit_mode()
    bpy.ops.sketchup.tool_move(vector=(1.0, 0.0, 0.0), copy=True)
    object_mode()
    bpy.ops.sketchup.array_repeat(count=3)
    object_mode()
    check("move array 3x 16/16/4", mesh_stats() == (16, 16, 4), str(mesh_stats()))
    xs = sorted({round(c[0], 6) for c in vertex_coords()})
    check("move array xs", xs == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0], str(xs))


def scenario_move_array_internal(module):
    clear_scene()
    draw_rect(module)
    select_all()
    edit_mode()
    bpy.ops.sketchup.tool_move(vector=(2.0, 0.0, 0.0), copy=True)
    object_mode()
    bpy.ops.sketchup.array_repeat(count=2, internal=True)
    object_mode()
    check("move array /2 16/16/4", mesh_stats() == (16, 16, 4), str(mesh_stats()))
    xs = sorted({round(c[0], 6) for c in vertex_coords()})
    expected = [0.0, 0.666667, 1.333333, 2.0, 2.666667, 3.333333, 4.0]
    check("move array /2 xs", xs == expected, str(xs))


def scenario_move_array_requires_copy(module):
    clear_scene()
    draw_rect(module)
    select_all()
    edit_mode()
    bpy.ops.sketchup.tool_move(vector=(1.0, 0.0, 0.0))
    object_mode()
    result = bpy.ops.sketchup.array_repeat(count=3)
    object_mode()
    check("array w/o copy cancelled", result == {"CANCELLED"}, str(result))
    check("array w/o copy unchanged", mesh_stats() == (4, 4, 1), str(mesh_stats()))


def scenario_move_stretch(module):
    clear_scene()
    draw_rect(module)
    # Select only the right edge (x == 2).
    select_edges(lambda a, b: abs(a[0] - 2.0) < 1e-9 and abs(b[0] - 2.0) < 1e-9)
    edit_mode()
    bpy.ops.sketchup.tool_move(vector=(1.0, 0.0, 0.0))
    object_mode()
    check("move stretch 4/4/1", mesh_stats() == (4, 4, 1), str(mesh_stats()))
    check(
        "move stretch coords",
        rounded_coords() == [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (3.0, 0.0, 0.0), (3.0, 1.0, 0.0)],
        str(rounded_coords()),
    )


def scenario_move_no_selection(module):
    clear_scene()
    result = bpy.ops.sketchup.tool_move(vector=(1.0, 0.0, 0.0))
    object_mode()
    check("move empty cancelled", result == {"CANCELLED"}, str(result))


# ---------------------------------------------------------------------------
# Rotate.
# ---------------------------------------------------------------------------


def scenario_rotate_execute_90(module):
    clear_scene()
    draw_rect(module)
    select_all()
    edit_mode()
    bpy.ops.sketchup.tool_rotate(angle=90.0, axis="Z")
    object_mode()
    check(
        "rotate 90 about center",
        rounded_coords() == [(0.5, -0.5, 0.0), (0.5, 1.5, 0.0), (1.5, -0.5, 0.0), (1.5, 1.5, 0.0)],
        str(rounded_coords()),
    )


def scenario_rotate_copy(module):
    clear_scene()
    draw_rect(module)
    select_all()
    edit_mode()
    bpy.ops.sketchup.tool_rotate(angle=90.0, axis="Z", copy=True)
    object_mode()
    check("rotate copy 8/8/2", mesh_stats() == (8, 8, 2), str(mesh_stats()))


def scenario_rotate_array(module):
    clear_scene()
    draw_rect(module)
    select_all()
    edit_mode()
    bpy.ops.sketchup.tool_rotate(angle=90.0, axis="Z", copy=True)
    object_mode()
    bpy.ops.sketchup.array_repeat(count=3, angle=90.0, axis="Z")
    object_mode()
    check("rotate array 16/16/4", mesh_stats() == (16, 16, 4), str(mesh_stats()))


def scenario_rotate_cursor(module):
    clear_scene()
    draw_rect(module)
    select_all()
    edit_mode()
    bpy.ops.sketchup.tool_rotate(angle=45.0, axis="Z")
    object_mode()
    cursor = tuple(round(c, 6) for c in bpy.context.scene.cursor.location)
    check("rotate cursor at center", cursor == (1.0, 0.5, 0.0), str(cursor))


# ---------------------------------------------------------------------------
# Scale.
# ---------------------------------------------------------------------------


def scenario_scale_execute(module):
    clear_scene()
    draw_rect(module)
    select_all()
    edit_mode()
    bpy.ops.sketchup.tool_scale(factors=(2.0, 2.0, 1.0))
    object_mode()
    check(
        "scale 2x about center",
        rounded_coords() == [(-1.0, -0.5, 0.0), (-1.0, 1.5, 0.0), (3.0, -0.5, 0.0), (3.0, 1.5, 0.0)],
        str(rounded_coords()),
    )


def scenario_scale_axis(module):
    clear_scene()
    draw_rect(module)
    select_all()
    edit_mode()
    bpy.ops.sketchup.tool_scale(factors=(1.0, 2.0, 1.0))
    object_mode()
    check(
        "scale y2 about center",
        rounded_coords() == [(0.0, -0.5, 0.0), (0.0, 1.5, 0.0), (2.0, -0.5, 0.0), (2.0, 1.5, 0.0)],
        str(rounded_coords()),
    )


# ---------------------------------------------------------------------------
# Push/Pull.
# ---------------------------------------------------------------------------


def scenario_push_pull_vcb(module):
    clear_scene()
    draw_rect(module)
    driver = ToolDriver(module.tools.extrude.SKETCHUP_OT_tool_push_pull, make_context()).start()
    driver.click(100, 50)
    driver.type_text("500")
    driver.enter()
    check("pushpull box 8/12/6", mesh_stats() == (8, 12, 6), str(mesh_stats()))
    zs = sorted({round(c[2], 6) for c in vertex_coords()})
    check("pushpull top z 0.5", zs == [0.0, 0.5], str(zs))
    driver.finish()


def scenario_push_pull_retype(module):
    clear_scene()
    draw_rect(module)
    driver = ToolDriver(module.tools.extrude.SKETCHUP_OT_tool_push_pull, make_context()).start()
    driver.click(100, 50)
    driver.type_text("500")
    driver.enter()
    driver.type_text("1000")
    driver.enter()
    check("pushpull retype 8/12/6", mesh_stats() == (8, 12, 6), str(mesh_stats()))
    zs = sorted({round(c[2], 6) for c in vertex_coords()})
    check("pushpull retype z 1.0", zs == [0.0, 1.0], str(zs))
    driver.finish()


def scenario_push_pull_ctrl(module):
    clear_scene()
    draw_rect(module)
    driver = ToolDriver(module.tools.extrude.SKETCHUP_OT_tool_push_pull, make_context()).start()
    driver.click(100, 50, ctrl=True)
    driver.type_text("500")
    driver.enter()
    check("pushpull ctrl 12/16/7", mesh_stats() == (12, 16, 7), str(mesh_stats()))
    driver.finish()


def scenario_push_pull_double_click(module):
    clear_scene()
    draw_rect(module, 0, 0, 200, 100)
    draw_rect(module, 300, 0, 500, 100)
    driver = ToolDriver(module.tools.extrude.SKETCHUP_OT_tool_push_pull, make_context()).start()
    driver.click(100, 50)
    driver.type_text("500")
    driver.enter()
    driver.click(400, 50)
    driver.click(400, 50)
    check("pushpull dblclick 16/24/12", mesh_stats() == (16, 24, 12), str(mesh_stats()))
    zs = sorted({round(c[2], 6) for c in vertex_coords()})
    check("pushpull dblclick z", zs == [0.0, 0.5], str(zs))
    driver.finish()


# ---------------------------------------------------------------------------
# Offset.
# ---------------------------------------------------------------------------


def scenario_offset_preselected(module):
    # Regression: on_setup called a missing _order_chain when edges
    # were preselected (0.4.0 GUI crash on the default cube).
    clear_scene()
    draw_rect(module)
    select_all()
    driver = ToolDriver(module.tools.extrude.SKETCHUP_OT_tool_offset, make_context()).start()
    driver.move(120, 60)
    driver.click(120, 60)
    # 1.0.1: the outer face ring-splits (8 triangles) + inner face,
    # instead of two overlapping quads.
    check("offset preselected 8/16/9", mesh_stats() == (8, 16, 9), str(mesh_stats()))
    driver.finish()


def scenario_offset_vcb(module):
    clear_scene()
    draw_rect(module)
    driver = ToolDriver(module.tools.extrude.SKETCHUP_OT_tool_offset, make_context()).start()
    driver.click(100, 50)
    driver.type_text("100")
    driver.enter()
    # 1.0.1: ring-split counts (see scenario_offset_preselected).
    check("offset vcb 8/16/9", mesh_stats() == (8, 16, 9), str(mesh_stats()))
    coords = rounded_coords()
    check(
        "offset inner loop",
        (0.1, 0.1, 0.0) in coords and (1.9, 0.9, 0.0) in coords,
        str(coords),
    )
    driver.finish()


def scenario_offset_mouse(module):
    clear_scene()
    draw_rect(module)
    driver = ToolDriver(module.tools.extrude.SKETCHUP_OT_tool_offset, make_context()).start()
    driver.click(100, 50)
    driver.move(120, 60)
    driver.click(120, 60)
    coords = rounded_coords()
    check(
        "offset mouse 0.4 inward",
        (0.4, 0.4, 0.0) in coords and (1.6, 0.6, 0.0) in coords,
        str(coords),
    )
    driver.finish()


# ---------------------------------------------------------------------------
# Follow Me.
# ---------------------------------------------------------------------------


def scenario_follow_me(module):
    clear_scene()
    context = make_context()
    line = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    line.click(0, 0)
    line.click(100, 0)
    line.click(200, 0)
    line.finish()
    # Profile away from the path: a profile on the path would split
    # the path edges when its loop is healed in.
    draw_rect(module, 0, 100, 20, 120)
    # Path edges are the first two created (length 1.0 each).
    select_edges(
        lambda a, b: abs((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 - 1.0) < 1e-9
    )
    driver = ToolDriver(module.tools.extrude.SKETCHUP_OT_tool_follow_me, make_context()).start()
    driver.click(10, 110)
    check("followme 19/26/10", mesh_stats() == (19, 26, 10), str(mesh_stats()))
    driver.finish()


# ---------------------------------------------------------------------------
# Flip.
# ---------------------------------------------------------------------------


def draw_triangle(module):
    context = make_context()
    line = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    line.click(0, 0)
    line.click(200, 0)
    line.click(200, 100)
    line.click(0, 0)
    line.finish()


def scenario_flip_x(module):
    clear_scene()
    draw_triangle(module)
    select_all()
    driver = ToolDriver(module.tools.extrude.SKETCHUP_OT_tool_flip, make_context()).start()
    driver.click(100, 50)
    check(
        "flip x",
        rounded_coords() == [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (2.0, 0.0, 0.0)],
        str(rounded_coords()),
    )
    driver.finish()


def scenario_flip_axis_key(module):
    clear_scene()
    draw_triangle(module)
    select_all()
    driver = ToolDriver(module.tools.extrude.SKETCHUP_OT_tool_flip, make_context()).start()
    driver.key("LEFT_ARROW")
    driver.click(100, 50)
    check(
        "flip y via arrow",
        rounded_coords() == [(0.0, 1.0, 0.0), (2.0, 0.0, 0.0), (2.0, 1.0, 0.0)],
        str(rounded_coords()),
    )
    driver.finish()


def run(module):
    FAILED.clear()
    from modal_harness import patch_projections

    patch_projections(module)
    scenario_move_execute(module)
    scenario_move_copy_execute(module)
    scenario_move_array_external(module)
    scenario_move_array_internal(module)
    scenario_move_array_requires_copy(module)
    scenario_move_stretch(module)
    scenario_move_no_selection(module)
    scenario_rotate_execute_90(module)
    scenario_rotate_copy(module)
    scenario_rotate_array(module)
    scenario_rotate_cursor(module)
    scenario_scale_execute(module)
    scenario_scale_axis(module)
    scenario_push_pull_vcb(module)
    scenario_push_pull_retype(module)
    scenario_push_pull_ctrl(module)
    scenario_push_pull_double_click(module)
    scenario_offset_preselected(module)
    scenario_offset_vcb(module)
    scenario_offset_mouse(module)
    scenario_follow_me(module)
    scenario_flip_x(module)
    scenario_flip_axis_key(module)
    print("transform flows: %s" % ("ALL PASS" if not FAILED else "%d FAILURES: %s" % (len(FAILED), FAILED)))
    return 1 if FAILED else 0
