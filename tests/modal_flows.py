"""Modal flow scenarios: drive the real Select/Line/Eraser operators
with synthetic events (see modal_harness.py) and assert the mesh
state after each flow. Runs inside Blender, installed add-on module
passed to run().

Usage (Blender): blender --background --factory-startup
    --python tests/run_modal_standalone.py -- <zip_path>
"""

import sys

import bmesh

from modal_harness import (
    ToolDriver,
    clear_scene,
    edge_coords,
    make_context,
    mesh_stats,
    patch_projections,
    selected_counts,
    sketchup_mesh,
    vertex_coords,
)

FAILED = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print("[%s] modal %s %s" % (status, name, detail))
    if not condition:
        FAILED.append(name)


def approx(point, target, tol=1e-6):
    return all(abs(a - b) <= tol for a, b in zip(point, target))


def has_edge(a, b, tol=1e-6):
    for p1, p2 in edge_coords():
        if (approx(p1, a, tol) and approx(p2, b, tol)) or (
            approx(p1, b, tol) and approx(p2, a, tol)
        ):
            return True
    return False


def draw_rect(driver, size_px=200):
    driver.click(0, 0)
    driver.click(size_px, 0)
    driver.click(size_px, size_px)
    driver.click(0, size_px)
    driver.click(0, 0)


def scenario_line_rectangle(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    draw_rect(driver)
    check("line rect 1 face", mesh_stats() == (4, 4, 1), str(mesh_stats()))
    result = driver.finish()
    check("line right-click finishes", result == {"FINISHED"}, str(result))
    check("line session cleared", module.core.state.get_session().active_tool_id is None)


def scenario_line_inference_kinds(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    draw_rect(driver)
    driver.move(0, 0)
    check(
        "inference endpoint",
        driver.op._current_inference is not None
        and driver.op._current_inference.kind == "endpoint",
        str(getattr(driver.op._current_inference, "kind", None)),
    )
    driver.move(100, 0)
    check(
        "inference midpoint",
        driver.op._current_inference.kind == "midpoint",
        driver.op._current_inference.kind,
    )
    driver.move(50, 0)
    check(
        "inference on_edge",
        driver.op._current_inference.kind == "on_edge",
        driver.op._current_inference.kind,
    )
    driver.move(100, 100)
    check(
        "inference on_face",
        driver.op._current_inference.kind == "on_face",
        driver.op._current_inference.kind,
    )
    driver.move(500, 500)
    check(
        "inference free",
        driver.op._current_inference.kind == "free",
        driver.op._current_inference.kind,
    )
    driver.finish()


def scenario_line_axis_snap_and_lock(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    driver.click(0, 0)
    driver.move(200, 10)
    inference = driver.op._current_inference
    check("axis snap kind", inference.kind == "axis", inference.kind)
    check("axis snap point", approx(inference.point, (2.0, 0.0, 0.0)), str(inference.point))
    driver.key("RIGHT_ARROW")
    driver.move(200, 100)
    check(
        "arrow lock holds axis",
        approx(driver.op.current_point, (2.0, 0.0, 0.0)),
        str(tuple(driver.op.current_point)),
    )
    driver.key("RIGHT_ARROW")
    driver.move(200, 100)
    check(
        "arrow lock toggles off",
        abs(driver.op.current_point[1] - 1.0) < 1e-6,
        str(tuple(driver.op.current_point)),
    )
    driver.finish()


def scenario_line_vcb_length(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    driver.click(0, 0)
    driver.move(300, 0)
    driver.type_text("500")
    check("vcb buffer", driver.op.session.vcb.text == "500")
    driver.enter()
    check("vcb length edge", has_edge((0, 0, 0), (0.5, 0, 0)), str(edge_coords()))
    # Re-type without moving the mouse: modifies the last segment.
    driver.type_text("250")
    driver.enter()
    check("vcb retype modifies", has_edge((0, 0, 0), (0.25, 0, 0)), str(edge_coords()))
    check("vcb retype 1 edge", mesh_stats()[1] == 1, str(mesh_stats()))
    driver.finish()


def scenario_line_vcb_coordinate(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    driver.type_text("[1000,500,0]")
    driver.enter()
    check("vcb coord sets start", driver.op.state == "WAIT_SECOND", driver.op.state)
    check("vcb coord start", approx(tuple(driver.op.start), (1.0, 0.5, 0.0)), str(tuple(driver.op.start)))
    driver.type_text("<0,500,0>")
    driver.enter()
    check(
        "vcb relative coord edge",
        has_edge((1.0, 0.5, 0), (1.0, 1.0, 0)),
        str(edge_coords()),
    )
    driver.finish()


def scenario_line_vcb_invalid(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    driver.click(0, 0)
    driver.type_text("xyz")
    result = driver.enter()
    check("vcb invalid stays modal", result == {"RUNNING_MODAL"}, str(result))
    check("vcb invalid keeps text", driver.op.session.vcb.text == "xyz")
    check("vcb invalid no edge", mesh_stats()[1] == 0, str(mesh_stats()))
    driver.finish()


def scenario_line_escape_restart(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    driver.click(0, 0)
    driver.click(100, 0)
    result = driver.escape()
    check("esc restarts segment", result == {"RUNNING_MODAL"}, str(result))
    check("esc state first", driver.op.state == "WAIT_FIRST", driver.op.state)
    driver.click(0, 100)
    driver.click(100, 100)
    check("esc restart draws", has_edge((0, 1, 0), (1, 1, 0)), str(edge_coords()))
    driver.finish()


def scenario_line_alt_cycle(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    lock = driver.op.session.lock
    check("alt initial all_on", lock.line_mode == "all_on", lock.line_mode)
    driver.key("LEFT_ALT")
    check("alt all_off", lock.line_mode == "all_off", lock.line_mode)
    driver.key("LEFT_ALT")
    check("alt parallel_perp", lock.line_mode == "parallel_perp", lock.line_mode)
    driver.key("LEFT_ALT")
    check("alt back all_on", lock.line_mode == "all_on", lock.line_mode)
    driver.finish()


def scenario_line_navigation_passthrough(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    result = driver.key("MIDDLEMOUSE", value="PRESS")
    check("nav passthrough", result == {"PASS_THROUGH"}, str(result))
    driver.finish()


def scenario_line_diagonal_split(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    draw_rect(driver)
    driver.click(0, 0)
    driver.click(200, 200)
    check("diagonal 2 faces", mesh_stats() == (4, 5, 2), str(mesh_stats()))
    driver.finish()


def scenario_select_click_and_box(module):
    clear_scene()
    context = make_context()
    line = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    draw_rect(line)
    line.finish()
    select_cls = module.tools.select.SKETCHUP_OT_tool_select
    driver = ToolDriver(select_cls, context).start()
    driver.click(100, 100)
    check("select click face", selected_counts() == (4, 4, 1), str(selected_counts()))
    driver.click(500, 500)
    check("select click empty clears", selected_counts() == (0, 0, 0), str(selected_counts()))
    # Right-drag box fully containing the rect.
    driver.press(-50, -50)
    driver.move(250, 250)
    driver.release(250, 250)
    check("select box inside", selected_counts() == (4, 4, 1), str(selected_counts()))
    driver.click(500, 500)
    # Right-drag box partially overlapping: nothing selected.
    driver.press(50, 50)
    driver.move(250, 250)
    driver.release(250, 250)
    check("select box partial right", selected_counts() == (0, 0, 0), str(selected_counts()))
    # Left-drag box partially overlapping: crossing selects.
    driver.press(250, 250)
    driver.move(50, 50)
    driver.release(50, 50)
    check("select box crossing", selected_counts()[2] == 1, str(selected_counts()))
    driver.finish()


def scenario_select_double_triple(module):
    clear_scene()
    context = make_context()
    line = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    draw_rect(line)
    line.click(0, 0)
    line.click(200, 200)
    line.finish()
    select_cls = module.tools.select.SKETCHUP_OT_tool_select
    driver = ToolDriver(select_cls, context).start()
    driver.click(50, 150)  # Upper-left triangle face.
    driver.click(50, 150)  # Double-click: face + boundary edges.
    counts = selected_counts()
    check("double-click face+edges", counts == (3, 3, 1), str(counts))
    driver.click(50, 150)  # Triple-click: everything connected.
    counts = selected_counts()
    check("triple-click connected", counts == (4, 5, 2), str(counts))
    driver.finish()


def scenario_select_modifiers(module):
    clear_scene()
    context = make_context()
    line = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    draw_rect(line)
    line.click(0, 0)
    line.click(200, 200)
    line.finish()
    select_cls = module.tools.select.SKETCHUP_OT_tool_select
    driver = ToolDriver(select_cls, context).start()
    driver.click(50, 150)
    check("mod baseline", selected_counts() == (3, 3, 1), str(selected_counts()))
    driver.click(150, 50, ctrl=True)
    check("mod ctrl adds", selected_counts() == (4, 5, 2), str(selected_counts()))
    driver.click(150, 50, shift=True, ctrl=True)
    check("mod ctrl+shift subtracts", selected_counts()[2] == 1, str(selected_counts()))
    driver.click(150, 50, shift=True)
    check("mod shift toggles on", selected_counts()[2] == 2, str(selected_counts()))
    driver.click(150, 50, shift=True)
    check("mod shift toggles off", selected_counts()[2] == 1, str(selected_counts()))
    driver.finish()


def scenario_eraser_click_and_heal(module):
    clear_scene()
    context = make_context()
    line = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    draw_rect(line)
    line.click(0, 0)
    line.click(200, 200)
    line.finish()
    check("eraser setup 2 faces", mesh_stats() == (4, 5, 2), str(mesh_stats()))
    eraser_cls = module.tools.eraser.SKETCHUP_OT_tool_eraser
    driver = ToolDriver(eraser_cls, context).start()
    driver.click(100, 100)  # Diagonal midpoint.
    check("eraser heals to 1 face", mesh_stats() == (4, 4, 1), str(mesh_stats()))
    driver.click(100, 0)  # Bottom edge midpoint.
    check("eraser deletes face", mesh_stats() == (4, 3, 0), str(mesh_stats()))
    driver.finish()


def scenario_eraser_drag(module):
    clear_scene()
    context = make_context()
    line = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    draw_rect(line)
    line.finish()
    eraser_cls = module.tools.eraser.SKETCHUP_OT_tool_eraser
    driver = ToolDriver(eraser_cls, context).start()
    driver.press(100, 0)
    driver.move(100, 200)
    driver.release(100, 200)
    check("eraser drag removes 2 edges", mesh_stats()[1] == 2, str(mesh_stats()))
    driver.finish()


def scenario_eraser_soft_hide(module):
    clear_scene()
    context = make_context()
    line = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    draw_rect(line)
    line.finish()
    eraser_cls = module.tools.eraser.SKETCHUP_OT_tool_eraser
    driver = ToolDriver(eraser_cls, context).start()
    driver.click(100, 0, ctrl=True)
    bm = bmesh.new()
    bm.from_mesh(sketchup_mesh())
    bm.edges.ensure_lookup_table()
    layer = bm.edges.layers.int.get("su_flags")
    flags = [edge[layer] for edge in bm.edges] if layer is not None else []
    smooth = [edge.smooth for edge in bm.edges]
    bm.free()
    check("eraser ctrl soft flag", 1 in flags, str(flags))
    check("eraser ctrl smooths", any(smooth), str(smooth))
    driver.click(100, 0, shift=True)
    bm = bmesh.new()
    bm.from_mesh(sketchup_mesh())
    bm.edges.ensure_lookup_table()
    layer = bm.edges.layers.int.get("su_flags")
    flags = [edge[layer] for edge in bm.edges] if layer is not None else []
    hidden = [edge.hide for edge in bm.edges]
    bm.free()
    check("eraser shift hide flag", 2 in flags or 3 in flags, str(flags))
    check("eraser shift hides", any(hidden), str(hidden))
    driver.click(100, 0, alt=True)
    bm = bmesh.new()
    bm.from_mesh(sketchup_mesh())
    bm.edges.ensure_lookup_table()
    layer = bm.edges.layers.int.get("su_flags")
    flags = [edge[layer] for edge in bm.edges] if layer is not None else []
    bm.free()
    check("eraser alt clears flags", all(f == 0 for f in flags), str(flags))
    driver.finish()


def scenario_vcb_display_places(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    driver.click(0, 0)
    driver.move(200, 0)
    session = module.core.state.get_session()
    check("vcb overlay text", driver.op.overlay.vcb_text != "", driver.op.overlay.vcb_text)
    import bpy

    wm_text = bpy.context.window_manager.sketchup_session.vcb_text
    check("vcb wm text", wm_text != "", wm_text)
    driver.finish()
    check("vcb cleared on finish", bpy.context.window_manager.sketchup_session.vcb_text == "")


def run(module):
    """Run all scenarios against the installed module; returns exit code."""
    FAILED.clear()
    patch_projections(module)
    scenario_line_rectangle(module)
    scenario_line_inference_kinds(module)
    scenario_line_axis_snap_and_lock(module)
    scenario_line_vcb_length(module)
    scenario_line_vcb_coordinate(module)
    scenario_line_vcb_invalid(module)
    scenario_line_escape_restart(module)
    scenario_line_alt_cycle(module)
    scenario_line_navigation_passthrough(module)
    scenario_line_diagonal_split(module)
    scenario_select_click_and_box(module)
    scenario_select_double_triple(module)
    scenario_select_modifiers(module)
    scenario_eraser_click_and_heal(module)
    scenario_eraser_drag(module)
    scenario_eraser_soft_hide(module)
    scenario_vcb_display_places(module)
    print("modal flows: %s" % ("ALL PASS" if not FAILED else "%d FAILURES: %s" % (len(FAILED), FAILED)))
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit("run via run_modal_standalone.py or run_t2.py")
