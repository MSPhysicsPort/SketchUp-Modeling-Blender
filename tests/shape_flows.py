"""Shape modal flows: drive the P2 shape tools with synthetic events
and assert mesh state + curve metadata. Runs inside Blender via
run_t2.py (installed module passed to run()) or run_modal_standalone.
"""

import bmesh

from modal_flows import FAILED, approx, check, has_edge  # noqa: F401
from modal_harness import (
    ToolDriver,
    clear_scene,
    edge_coords,
    make_context,
    mesh_stats,
    sketchup_mesh,
    vertex_coords,
)


def curve_records():
    mesh = sketchup_mesh()
    if mesh is None:
        return {}
    prop = mesh.get("su_curves")
    if prop is None:
        return {}
    return {str(k): dict(v) for k, v in prop.items()}


def scenario_rectangle(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_rectangle, context).start()
    driver.click(0, 0)
    driver.click(200, 100)
    check("rect 4/4/1", mesh_stats() == (4, 4, 1), str(mesh_stats()))
    coords = sorted(vertex_coords())
    check(
        "rect coords",
        coords == [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (2.0, 0.0, 0.0), (2.0, 1.0, 0.0)],
        str(coords),
    )
    driver.finish()


def scenario_rectangle_vcb(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_rectangle, context).start()
    driver.click(0, 0)
    driver.type_text("1000,500")
    driver.enter()
    coords = sorted(vertex_coords())
    check(
        "rect vcb dims",
        coords == [(0.0, 0.0, 0.0), (0.0, 0.5, 0.0), (1.0, 0.0, 0.0), (1.0, 0.5, 0.0)],
        str(coords),
    )
    # Retype without moving: resize.
    driver.type_text("2000,1000")
    driver.enter()
    coords = sorted(vertex_coords())
    check(
        "rect vcb retype",
        coords == [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (2.0, 0.0, 0.0), (2.0, 1.0, 0.0)],
        str(coords),
    )
    check("rect retype 1 face", mesh_stats()[2] == 1, str(mesh_stats()))
    driver.finish()


def scenario_rectangle_square_golden(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_rectangle, context).start()
    driver.click(0, 0)
    driver.move(200, 198)
    check("square snap label", driver.op.shape_label == "Square", driver.op.shape_label)
    check("square snap corner", approx(tuple(driver.op.corner2), (2.0, 2.0, 0.0)), str(tuple(driver.op.corner2)))
    driver.move(162, 100)
    check("golden label", driver.op.shape_label == "Golden Section", driver.op.shape_label)
    check(
        "golden corner",
        abs(driver.op.corner2[0] - 1.618033988749895) < 1e-6,
        str(tuple(driver.op.corner2)),
    )
    driver.finish()


def scenario_rectangle_plane_lock(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_rectangle, context).start()
    driver.key("RIGHT_ARROW")  # Lock plane normal to red/X axis.
    driver.click(0, 0)
    driver.click(200, 100)
    check(
        "rect plane lock YZ",
        all(abs(co[0]) < 1e-9 for co in vertex_coords()),
        str(vertex_coords()),
    )
    driver.finish()


def scenario_circle(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_circle, context).start()
    driver.type_text("12")
    driver.enter()
    check("circle sides set", driver.op.segments == 12, str(driver.op.segments))
    driver.click(100, 100)
    driver.click(200, 100)
    check("circle 12/12/1", mesh_stats() == (12, 12, 1), str(mesh_stats()))
    records = curve_records()
    check("circle record", len(records) == 1, str(records))
    record = next(iter(records.values()))
    check("circle record type", record["type"] == "circle", record["type"])
    check("circle record radius", abs(record["radius"] - 1.0) < 1e-9, str(record["radius"]))
    check("circle record segments", record["segments"] == 12, str(record["segments"]))
    # Circle edges are soft+smooth.
    bm = bmesh.new()
    bm.from_mesh(sketchup_mesh())
    bm.edges.ensure_lookup_table()
    check("circle edges smooth", all(e.smooth for e in bm.edges))
    bm.free()
    # Retype radius.
    driver.type_text("500")
    driver.enter()
    record = next(iter(curve_records().values()))
    check("circle retype radius", abs(record["radius"] - 0.5) < 1e-9, str(record["radius"]))
    check("circle retype 12 edges", mesh_stats()[1] == 12, str(mesh_stats()))
    driver.finish()


def scenario_center_inference(module):
    clear_scene()
    context = make_context()
    circle = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_circle, context).start()
    circle.click(100, 100)
    circle.click(200, 100)
    circle.finish()
    line = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    line.move(100, 100)
    inference = line.op._current_inference
    check("center inference", inference is not None and inference.kind == "center",
          str(getattr(inference, "kind", None)))
    line.finish()


def scenario_polygon(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_polygon, context).start()
    driver.click(100, 100)
    driver.click(200, 100)
    check("polygon 6/6/1", mesh_stats() == (6, 6, 1), str(mesh_stats()))
    bm = bmesh.new()
    bm.from_mesh(sketchup_mesh())
    bm.edges.ensure_lookup_table()
    check("polygon edges not smooth", not any(e.smooth for e in bm.edges))
    bm.free()
    driver.finish()


def scenario_arc(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_arc, context).start()
    driver.click(100, 100)
    driver.click(200, 100)
    driver.click(100, 200)
    check("arc 13/12/0", mesh_stats() == (13, 12, 0), str(mesh_stats()))
    coords = vertex_coords()
    check("arc start present", any(approx(c, (2.0, 1.0, 0.0), 1e-6) for c in coords), str(coords))
    check("arc end present", any(approx(c, (1.0, 2.0, 0.0), 1e-6) for c in coords), str(coords))
    driver.finish()


def scenario_arc_quarter_snap(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_arc, context).start()
    driver.click(100, 100)
    driver.click(200, 100)
    driver.move(101, 200)
    check("arc quarter label", driver.op.shape_label == "Quarter Circle", driver.op.shape_label)
    driver.finish()


def scenario_pie(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_pie, context).start()
    driver.click(100, 100)
    driver.click(200, 100)
    driver.click(100, 200)
    check("pie 14/14/1", mesh_stats() == (14, 14, 1), str(mesh_stats()))
    driver.finish()


def scenario_arc_2_point(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_arc_2_point, context).start()
    driver.click(0, 100)
    driver.click(200, 100)
    driver.move(100, 150)
    driver.click(100, 150)
    check("2pt arc 12 edges", mesh_stats()[1] == 12, str(mesh_stats()))
    coords = vertex_coords()
    check("2pt arc endpoints", any(approx(c, (0.0, 1.0, 0.0), 1e-6) for c in coords)
          and any(approx(c, (2.0, 1.0, 0.0), 1e-6) for c in coords), str(coords))
    check("2pt arc bulge side", max(c[1] for c in coords) > 1.0, str(coords))
    driver.finish()


def scenario_arc_2_point_vcb_bulge(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_arc_2_point, context).start()
    driver.click(0, 100)
    driver.click(200, 100)
    driver.type_text("300")
    driver.enter()
    coords = vertex_coords()
    check("2pt arc vcb bulge apex", abs(max(c[1] for c in coords) - 1.3) < 1e-6, str(coords))
    driver.finish()


def scenario_arc_3_point(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_arc_3_point, context).start()
    driver.click(0, 100)
    driver.click(100, 150)
    driver.click(200, 100)
    check("3pt arc 12 edges", mesh_stats()[1] == 12, str(mesh_stats()))
    coords = vertex_coords()
    check("3pt arc through mid", abs(max(c[1] for c in coords) - 1.5) < 1e-6, str(coords))
    driver.finish()


def scenario_rotated_rectangle(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_rotated_rectangle, context).start()
    driver.click(0, 0)
    driver.click(200, 0)
    driver.click(200, 100)
    check("rot rect 4/4/1", mesh_stats() == (4, 4, 1), str(mesh_stats()))
    driver.finish()


def scenario_rotated_rectangle_vcb(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_rotated_rectangle, context).start()
    driver.click(0, 0)
    driver.click(200, 0)
    driver.type_text("500,90")
    driver.enter()
    coords = sorted(vertex_coords())
    check(
        "rot rect vcb width/angle",
        coords == [(0.0, 0.0, 0.0), (0.0, 0.5, 0.0), (2.0, 0.0, 0.0), (2.0, 0.5, 0.0)],
        str(coords),
    )
    driver.finish()


def scenario_freehand(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_freehand, context).start()
    driver.press(0, 0)
    driver.move(50, 0)
    driver.move(100, 10)
    driver.move(150, 0)
    driver.move(200, 0)
    driver.release(200, 0)
    stats = mesh_stats()
    check("freehand polyline", stats[1] >= 2 and stats[2] == 0, str(stats))
    records = curve_records()
    check("freehand record", len(records) == 1 and next(iter(records.values()))["type"] == "freehand", str(records))
    driver.finish()


def _activate_and_select(edge_indices):
    import bpy

    obj = bpy.data.objects.get("SketchUp Model")
    bpy.context.view_layer.objects.active = obj
    mesh = obj.data
    for edge in mesh.edges:
        edge.select = False
    for index in edge_indices:
        mesh.edges[index].select = True
    return obj


def scenario_divide(module):
    import bpy

    clear_scene()
    context = make_context()
    line = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    line.click(0, 0)
    line.click(200, 0)
    line.finish()
    _activate_and_select([0])
    result = bpy.ops.sketchup.divide_edge("EXEC_DEFAULT", segments=3)
    check("divide executes", result == {"FINISHED"}, str(result))
    check("divide 1->3 edges", mesh_stats()[1] == 3, str(mesh_stats()))
    coords = sorted(vertex_coords())
    check(
        "divide equal parts",
        len(coords) == 4 and abs(coords[1][0] - 2.0 / 3.0) < 1e-6,
        str(coords),
    )


def scenario_weld_explode(module):
    import bpy

    clear_scene()
    context = make_context()
    line = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    line.click(0, 0)
    line.click(100, 0)
    line.click(200, 0)
    line.finish()
    _activate_and_select([0, 1])
    result = bpy.ops.sketchup.weld_edges("EXEC_DEFAULT")
    check("weld executes", result == {"FINISHED"}, str(result))
    records = curve_records()
    check("weld record", len(records) == 1 and next(iter(records.values()))["type"] == "curve", str(records))
    _activate_and_select([0, 1])
    result = bpy.ops.sketchup.explode_curve("EXEC_DEFAULT")
    check("explode executes", result == {"FINISHED"}, str(result))
    check("explode removes record", curve_records() == {}, str(curve_records()))
    check("explode keeps edges", mesh_stats()[1] == 2, str(mesh_stats()))


def scenario_convert_to_polygon(module):
    import bpy

    clear_scene()
    context = make_context()
    circle = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_circle, context).start()
    circle.click(100, 100)
    circle.click(200, 100)
    circle.finish()
    _activate_and_select(list(range(24)))
    result = bpy.ops.sketchup.convert_to_polygon("EXEC_DEFAULT")
    check("convert executes", result == {"FINISHED"}, str(result))
    record = next(iter(curve_records().values()))
    check("convert type polygon", record["type"] == "polygon", record["type"])
    bm = bmesh.new()
    bm.from_mesh(sketchup_mesh())
    bm.edges.ensure_lookup_table()
    check("convert unsmooths", not any(e.smooth for e in bm.edges))
    bm.free()


def scenario_curve_edit(module):
    import bpy

    clear_scene()
    context = make_context()
    circle = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_circle, context).start()
    circle.click(100, 100)
    circle.click(200, 100)
    circle.finish()
    _activate_and_select(list(range(24)))
    result = bpy.ops.sketchup.curve_edit("EXEC_DEFAULT", radius=0.5, segments=8)
    check("curve edit executes", result == {"FINISHED"}, str(result))
    record = next(iter(curve_records().values()))
    check("curve edit radius", abs(record["radius"] - 0.5) < 1e-9, str(record["radius"]))
    check("curve edit segments", record["segments"] == 8, str(record["segments"]))
    check("curve edit 8/8/1", mesh_stats() == (8, 8, 1), str(mesh_stats()))


def scenario_rectangle_escape_restart(module):
    # Regression: on_escape hooks used to return bools, crashing the
    # modal loop ("incompatible return value") on real machines.
    clear_scene()
    driver = ToolDriver(module.tools.shapes.SKETCHUP_OT_tool_rectangle, make_context()).start()
    driver.click(0, 0)
    result = driver.escape()
    check("rect esc restart stays modal", result == {"RUNNING_MODAL"}, str(result))
    driver.click(0, 0)
    driver.click(200, 100)
    check("rect after esc restart", mesh_stats() == (4, 4, 1), str(mesh_stats()))
    result = driver.escape()
    check("rect esc at first finishes", result == {"FINISHED"}, str(result))


def run(module):
    FAILED.clear()
    from modal_harness import patch_projections

    patch_projections(module)
    scenario_rectangle(module)
    scenario_rectangle_escape_restart(module)
    scenario_rectangle_vcb(module)
    scenario_rectangle_square_golden(module)
    scenario_rectangle_plane_lock(module)
    scenario_circle(module)
    scenario_center_inference(module)
    scenario_polygon(module)
    scenario_arc(module)
    scenario_arc_quarter_snap(module)
    scenario_pie(module)
    scenario_arc_2_point(module)
    scenario_arc_2_point_vcb_bulge(module)
    scenario_arc_3_point(module)
    scenario_rotated_rectangle(module)
    scenario_rotated_rectangle_vcb(module)
    scenario_freehand(module)
    scenario_divide(module)
    scenario_weld_explode(module)
    scenario_convert_to_polygon(module)
    scenario_curve_edit(module)
    print("shape flows: %s" % ("ALL PASS" if not FAILED else "%d FAILURES: %s" % (len(FAILED), FAILED)))
    return 0 if not FAILED else 1
