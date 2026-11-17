"""Direct tool switching: press another tool's shortcut while a modal
tool is running and SketchUp switches straight to that tool — no Esc
in between (Sen 2026-11-17: "工具之前的切换，不能通过直接按快捷键
切换，必须中间加一个 esc").

How it works: every SketchUp modal tool routes key events through
``SketchUpToolBase._modal_inner``, which consults
:func:`switch_target` before feeding the VCB buffer. When the chord
matches another tool and the VCB buffer is empty (a letter typed
after digits is a VCB suffix, e.g. ``24s`` for segments, and must
keep going to the buffer), the current tool finishes cleanly and
:func:`request_switch` defers the new tool's invoke to a zero-delay
timer: a modal operator cannot invoke another modal operator from
inside its own ``modal()``. The timer callback runs on the next main
loop iteration, after the old modal handler has left the stack.

Native-delegated tools (Move/Rotate/Scale via ``transform.*``) own
Blender's transform modal loop, which the add-on cannot intercept:
there, a click or Enter confirms the transform and the next shortcut
works immediately, exactly like finishing a Move in SketchUp. Only
the add-on's own modal tools get true mid-operation switching.
"""

import bpy

# (event type, shift, ctrl, alt) -> operator idname. Single letters
# mirror the level-1 keymap table (keymaps.KEYMAP_TABLE); view
# commands and toggles are included so they work mid-tool too.
SWITCH_CHORDS = {
    ("SPACE", False, False, False): "sketchup.tool_select",
    ("SPACE", True, False, False): "sketchup.tool_lasso",
    ("L", False, False, False): "sketchup.tool_line",
    ("E", False, False, False): "sketchup.tool_eraser",
    ("R", False, False, False): "sketchup.tool_rectangle",
    ("C", False, False, False): "sketchup.tool_circle",
    ("A", False, False, False): "sketchup.tool_arc_2_point",
    ("M", False, False, False): "sketchup.tool_move",
    ("P", False, False, False): "sketchup.tool_push_pull",
    ("Q", False, False, False): "sketchup.tool_rotate",
    ("S", False, False, False): "sketchup.tool_scale",
    ("F", False, False, False): "sketchup.tool_offset",
    ("G", False, False, False): "sketchup.make_group",
    ("T", False, False, False): "sketchup.tool_tape_measure",
    ("B", False, False, False): "sketchup.tool_paint_bucket",
    ("K", False, False, False): "sketchup.toggle_back_edges",
    ("O", False, False, False): "sketchup.tool_orbit",
    ("H", False, False, False): "sketchup.tool_pan",
    ("Z", False, False, False): "sketchup.tool_zoom",
    ("Z", True, False, False): "sketchup.zoom_extents",
    ("N", False, False, False): "sketchup.parallel_projection",
    ("F2", False, False, False): "sketchup.view_top",
    ("F3", False, False, False): "sketchup.view_front",
    ("F4", False, False, False): "sketchup.view_left",
    ("F5", False, False, False): "sketchup.view_right",
    ("S", True, False, False): "sketchup.search",
    ("W", True, True, False): "sketchup.tool_zoom_window",
    ("E", True, True, False): "sketchup.zoom_extents",
}

_pending = None


def switch_target(event, current_idname, vcb_empty):
    """Return the operator idname to switch to, or None.

    ``vcb_empty`` must be True: with text in the Measurements buffer
    a letter is VCB input, not a tool switch. The tool's own chord
    is a no-op (pressing L while drawing a Line keeps the Line).
    """
    if event.value != "PRESS":
        return None
    if getattr(event, "oskey", False):
        return None
    if not vcb_empty:
        return None
    target = SWITCH_CHORDS.get(
        (event.type, bool(event.shift), bool(event.ctrl), bool(event.alt))
    )
    if target is None or target == current_idname:
        return None
    return target


def request_switch(operator_id):
    """Queue a deferred invoke of ``operator_id`` (timer path)."""
    global _pending
    _pending = operator_id
    try:
        bpy.app.timers.register(_run_pending, first_interval=0.0)
    except Exception:
        pass


def pending_switch():
    """The queued operator idname, or None (tests introspect this)."""
    return _pending


def run_pending_switch():
    """Invoke the queued operator now. Called by the timer; tests
    call it directly because headless runs have no event loop."""
    global _pending
    operator_id = _pending
    _pending = None
    if operator_id is None:
        return None
    try:
        parts = operator_id.split(".")
        fn = bpy.ops
        for part in parts:
            fn = getattr(fn, part)
        from ..context import view_3d_override

        override = view_3d_override()
        if override:
            with bpy.context.temp_override(**override):
                return fn("INVOKE_DEFAULT")
        return fn("INVOKE_DEFAULT")
    except Exception as exc:
        print("SketchUp tool switch to %s failed: %r" % (operator_id, exc))
        return {"CANCELLED"}


def _run_pending():
    run_pending_switch()
    return None
