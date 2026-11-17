import bpy
OUT = "/tmp/gui_key_state.txt"
ZIP = "ZIP_PATH_PLACEHOLDER"
open(OUT, "w").write("")
def log(msg):
    with open(OUT, "a") as f:
        f.write(msg + "\n")
    print("KEYTEST:", msg)
def dump_state(tag):
    wm = bpy.context.window_manager
    mod = None
    try:
        import bl_ext.user_default.sketchup_modeling.keymaps as km
        counts = {n: km.our_key_count(n) for n in ("3D View", "Mesh", "Object Mode")}
    except Exception as e:
        counts = "ERR %r" % (e,)
    def item_active(km_name, typ):
        try:
            km = wm.keyconfigs.active.keymaps.get(km_name)
            for it in km.keymap_items:
                if it.type == typ and it.value == "PRESS" and not (it.ctrl or it.alt or it.shift):
                    return "%s:%s" % (it.idname, it.active)
        except Exception:
            pass
        return "?"
    ts = bpy.context.scene.tool_settings
    log("[%s] flag=%s counts=%s MeshL=%s ObjM=%s snap=%s pivot=%s mode=%s" % (
        tag, getattr(wm, "sketchup_mode", "?"), counts,
        item_active("Mesh", "L"), item_active("Object Mode", "M"),
        ts.use_snap, ts.transform_pivot_point, bpy.context.mode))
def state():
    try:
        tool = bpy.context.window_manager.sketchup_session.active_tool
    except Exception:
        tool = "?"
    return "mode=%s tool=%r" % (bpy.context.mode, tool)
def view_override():
    window = bpy.context.window
    area = next((a for a in window.screen.areas if a.type == "VIEW_3D"), None)
    region = next((r for r in area.regions if r.type == "WINDOW"), None)
    return {"window": window, "area": area, "region": region}
def phase1():
    bpy.ops.extensions.package_install_files(filepath=ZIP, repo="user_default", enable_on_install=True, overwrite=True)
    dump_state("after-enable")
    with bpy.context.temp_override(**view_override()):
        bpy.ops.sketchup.toggle_mode()
    dump_state("mode-ON")
    log("READY")
    return None
_ticks = [0]
def tick():
    _ticks[0] += 1
    log("tick %02d %s" % (_ticks[0], state()))
    return 0.5
def phase2():
    with bpy.context.temp_override(**view_override()):
        bpy.ops.sketchup.toggle_mode()
    dump_state("mode-OFF")
    log("DONE")
    bpy.ops.wm.quit_blender()
    return None
bpy.app.timers.register(phase1, first_interval=3.0)
bpy.app.timers.register(tick, first_interval=4.0)
bpy.app.timers.register(phase2, first_interval=50.0)
