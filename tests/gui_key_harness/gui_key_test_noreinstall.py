import bpy
OUT = "/tmp/gui_key_state.txt"
open(OUT, "w").write("")
def log(msg):
    with open(OUT, "a") as f:
        f.write(msg + "\n")
    print("KEYTEST:", msg)
def state():
    try:
        tool = bpy.context.window_manager.sketchup_session.active_tool
    except Exception:
        tool = "NO-SESSION"
    return "mode=%s tool=%r" % (bpy.context.mode, tool)
def setup():
    log("startup state " + state())
    log("READY")
    return None
_ticks = [0]
def tick():
    _ticks[0] += 1
    log("tick %02d %s" % (_ticks[0], state()))
    if _ticks[0] >= 25:
        bpy.ops.wm.quit_blender()
        return None
    return 0.5
bpy.app.timers.register(setup, first_interval=3.0)
bpy.app.timers.register(tick, first_interval=4.0)
