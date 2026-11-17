"""P6 modal flow scenarios: direct tool switching (no Esc),
Axes placement, Dimension placement, Tape Measure + resize VCB,
and the Text tool pending point. Runs inside Blender via run_t2.py.
"""

import sys

from modal_harness import ToolDriver, clear_scene, ev, make_context, patch_projections

FAILED = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print("[%s] p6flow %s %s" % (status, name, detail))
    if not condition:
        FAILED.append(name)


def approx(point, target, tol=1e-6):
    return all(abs(a - b) <= tol for a, b in zip(point, target))


def scenario_tool_switch_direct(module):
    clear_scene()
    context = make_context()
    switching = module.tools.switching
    driver = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    driver.click(0, 0)  # first point of a line
    result = driver.key("R")
    check("switch returns finished", result == {"FINISHED"}, str(result))
    check(
        "switch queued rectangle",
        switching.pending_switch() == "sketchup.tool_rectangle",
        str(switching.pending_switch()),
    )


def scenario_tool_switch_vcb_guard(module):
    clear_scene()
    context = make_context()
    switching = module.tools.switching
    driver = ToolDriver(module.tools.line.SKETCHUP_OT_tool_line, context).start()
    driver.click(0, 0)
    before = switching.pending_switch()
    driver.type_text("24")
    result = driver.key("S")
    check("vcb guard stays modal", result == {"RUNNING_MODAL"}, str(result))
    check("vcb guard no new switch", switching.pending_switch() == before)


def scenario_axes_tool(module):
    clear_scene()
    context = make_context()
    session = module.core.state.get_session()
    session.axes.reset()
    driver = ToolDriver(module.tools.measure.SKETCHUP_OT_tool_axes, context).start()
    driver.click(0, 0)
    driver.click(100, 0)
    result = driver.press(0, 100)
    check("axes finishes", result == {"FINISHED"}, str(result))
    check("axes origin", approx(session.axes.origin, (0, 0, 0)), str(session.axes.origin))
    check("axes x", approx(session.axes.x, (1, 0, 0)), str(session.axes.x))
    check("axes y", approx(session.axes.y, (0, 1, 0)), str(session.axes.y))
    check("axes z", approx(session.axes.z, (0, 0, 1)), str(session.axes.z))
    session.axes.reset()


def scenario_dimension_tool(module):
    clear_scene()
    context = make_context()
    scene = context.scene
    module.data.annotations.save_annotations(scene, [])
    driver = ToolDriver(module.tools.annotate.SKETCHUP_OT_tool_dimension, context).start()
    driver.click(0, 0)
    driver.click(200, 0)
    driver.click(100, 100)
    entries = module.data.annotations.get_annotations(scene)
    check("dimension added", len(entries) == 1, str(entries))
    if entries:
        check("dimension type", entries[0]["type"] == "dimension")
        check("dimension p2", approx(entries[0]["p2"], (2, 0, 0)), str(entries[0]["p2"]))
    module.data.annotations.save_annotations(scene, [])
    driver.finish()


def scenario_tape_measure_resize(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.measure.SKETCHUP_OT_tool_tape_measure, context).start()
    driver.click(0, 0)
    driver.click(200, 0)
    driver.type_text("4m")
    driver.enter()
    pending = module.tools.measure._pending_resize
    check("resize pending factor", pending["factor"] is not None and abs(pending["factor"] - 2.0) < 1e-9, str(pending))
    pending["factor"] = None
    driver.finish()


def scenario_text_tool_pending(module):
    clear_scene()
    context = make_context()
    driver = ToolDriver(module.tools.annotate.SKETCHUP_OT_tool_text, context).start()
    result = driver.press(50, 50)
    check("text finishes", result == {"FINISHED"}, str(result))
    pending = module.tools.annotate._pending_text
    check("text pending point", pending["point"] is not None and approx(pending["point"], (0.5, 0.5, 0)), str(pending))
    pending["point"] = None


def run(module):
    """Run all P6 flow scenarios; returns exit code."""
    FAILED.clear()
    patch_projections(module)
    scenario_tool_switch_direct(module)
    scenario_tool_switch_vcb_guard(module)
    scenario_axes_tool(module)
    scenario_dimension_tool(module)
    scenario_tape_measure_resize(module)
    scenario_text_tool_pending(module)
    print("p6 flows: %s" % ("ALL PASS" if not FAILED else "%d FAILURES: %s" % (len(FAILED), FAILED)))
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit("run via run_t2.py")
