"""T2 headless bpy integration test (proposal §5.9).

Runs inside Blender: install the built .zip, enable, exercise the
skeleton, disable cleanly, re-enable. Run via tests/run_matrix.sh
with an isolated HOME so the real user config is untouched.

Usage (Blender): blender --background --factory-startup
    --python-exit-code 1 --python tests/run_t2.py -- <zip_path>
"""

import importlib
import sys
import traceback
import zipfile
from pathlib import Path
from types import SimpleNamespace

import bpy

ADDON_ID = "sketchup_modeling"

CHECKS = []


def check(name, condition, detail=""):
    CHECKS.append((name, bool(condition), detail))
    print("[%s] %s %s" % ("PASS" if condition else "FAIL", name, detail))
    if not condition:
        raise AssertionError("T2 check failed: %s %s" % (name, detail))


def find_addon_entry():
    for entry in bpy.context.preferences.addons:
        if entry.module == ADDON_ID or entry.module.endswith("." + ADDON_ID):
            return entry
    return None


def install_from_zip(zip_path):
    """Install via the extensions operator, falling back to a manual
    unzip into the User Default repo + addon_enable."""
    try:
        bpy.ops.extensions.package_install_files(
            filepath=str(zip_path),
            repo="user_default",
            enable_on_install=True,
            overwrite=True,
        )
        return "operator"
    except Exception as exc:  # noqa: BLE001 - fallback path is intentional
        print("operator install failed (%r); falling back to manual install" % (exc,))
    repo_dir = None
    for repo in bpy.context.preferences.extensions.repos:
        if repo.name == "User Default":
            repo_dir = Path(repo.directory)
            break
    if repo_dir is None:
        raise RuntimeError("User Default extensions repo not found")
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(repo_dir / ADDON_ID)
    bpy.ops.extensions.repo_refresh_all()
    bpy.ops.preferences.addon_enable(module="bl_ext.user_default." + ADDON_ID)
    return "manual"


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :]
    zip_path = Path(argv[0])
    print("T2 on Blender %s, zip %s" % (".".join(map(str, bpy.app.version)), zip_path))
    check("zip exists", zip_path.is_file())

    method = install_from_zip(zip_path)
    print("install method: %s" % method)

    prefs_container = find_addon_entry()
    check("addon enabled", prefs_container is not None)
    module_key = prefs_container.module
    print("addon module key: %s" % module_key)
    module = sys.modules.get(module_key)
    check("addon module loaded", module is not None)

    prefs = prefs_container.preferences
    check("pref keymap_level default 1", prefs.keymap_level == "1", prefs.keymap_level)
    check("pref default_unit default mm", prefs.default_unit == "mm", prefs.default_unit)
    check("pref inference default on", prefs.inference_enabled is True)

    for cls_name in (
        "SKETCHUP_MT_MAIN",
        "SKETCHUP_MT_TOOLS",
        "SKETCHUP_MT_DRAW",
        "SKETCHUP_MT_CAMERA",
        "SKETCHUP_MT_LINES",
        "SKETCHUP_MT_ARCS",
        "SKETCHUP_MT_SHAPES",
        "SKETCHUP_MT_STANDARD_VIEWS",
        "SKETCHUP_MT_SOLID_TOOLS",
        "SKETCHUP_PT_tools",
        "SKETCHUP_PT_vcb",
    ):
        check("class registered: %s" % cls_name, hasattr(bpy.types, cls_name))

    check("stub operator exists", hasattr(bpy.ops.sketchup, "stub"))
    result = bpy.ops.sketchup.stub(tool_id="line")
    check("stub operator executes", result == {"FINISHED"}, str(result))

    compat = importlib.import_module(module_key + ".core.compat")
    flags = compat.feature_flags()
    print("feature flags: %s" % (flags,))
    check("compat translations feature", flags["translations"] is True)
    check("compat background detected", flags["background"] is True)

    vcb = importlib.import_module(module_key + ".core.vcb")
    parsed = vcb.parse_length("6' 8 7/8\"")
    check("packaged VCB parses feet/inches", abs(parsed - 2.054225) < 1e-9, str(parsed))
    check("keymap level state", module.keymaps.CURRENT_LEVEL == 1)
    conflicts = module.keymaps.scan_conflicts()
    check("conflict scan returns list", isinstance(conflicts, list))
    print("keymap conflicts at level 1: %s" % (conflicts,))

    # Translation mechanism end to end (unique msgids with no built-in
    # collision: "Push/Pull" collides with Blender's own "推 / 拉").
    bpy.context.preferences.view.language = "zh_HANS"
    check("locale is zh_HANS", bpy.app.translations.locale == "zh_HANS")
    translated = bpy.app.translations.pgettext_iface("SketchUp Select (P0 stub)")
    check("zh translation stub label", translated == "SketchUp 选择（P0 占位）", translated)
    translated = bpy.app.translations.pgettext_iface("Follow Me")
    check("zh translation Follow Me", translated == "路径跟随", translated)

    # Explicit-lookup checks: draw code resolves every string with
    # translate() because Blender shows operator text verbatim.
    translations_mod = importlib.import_module(module_key + ".i18n.translations")
    translate = translations_mod.translate
    check("T() Previous zh", translate("Previous") == "上一视图", translate("Previous"))
    check(
        "T() Parallel Projection zh",
        translate("Parallel Projection") == "平行投影",
        translate("Parallel Projection"),
    )
    check(
        "T() stub template zh",
        translate("SketchUp tool '%s' is not implemented yet (P0 skeleton).")
        == "SketchUp 工具“%s”尚未实现（P0 骨架）。",
    )
    check("T() unknown falls back to msgid", translate("NoSuchString123") == "NoSuchString123")

    # Fake-layout draw capture: run every menu/panel draw function
    # against a recording layout and compare with the expected
    # translated text, under both languages.
    menu_data = importlib.import_module(module_key + ".data.menu_data")
    menus_mod = importlib.import_module(module_key + ".menus")
    panels_mod = importlib.import_module(module_key + ".panels")

    class _FakeOp:
        pass

    class _FakeLayout:
        def __init__(self, recorder):
            self._rec = recorder
            self.enabled = True

        def separator(self):
            self._rec.append(("separator", ""))

        def menu(self, idname, text=None, **kwargs):
            self._rec.append(("menu", text))
            return self

        def operator(self, idname, text=None, **kwargs):
            self._rec.append(("operator", idname, text))
            return _FakeOp()

        def label(self, text=None, **kwargs):
            self._rec.append(("label", text))

        def row(self, **kwargs):
            return _FakeLayout(self._rec)

        def column(self, **kwargs):
            return _FakeLayout(self._rec)

        def box(self, **kwargs):
            return _FakeLayout(self._rec)

        def prop(self, *args, **kwargs):
            self._rec.append(("prop", ""))

    def capture(cls, context):
        recorder = []
        fake_self = SimpleNamespace(layout=_FakeLayout(recorder))
        cls.__dict__["draw"](fake_self, context)
        return recorder

    def expected_menu(items):
        out = []
        for item in items:
            if item.get("separator"):
                out.append(("separator", ""))
            elif "note" in item:
                out.append(("label", translate(item["note"])))
            elif item.get("scope", "in") == "out" or item.get("label") is None:
                continue
            elif "submenu" in item:
                out.append(("menu", translate(item["label"])))
            else:
                out.append(
                    (
                        "operator",
                        item.get("operator", "sketchup.stub"),
                        translate(item["label"]),
                    )
                )
        return out

    def expected_panel(items, depth=0):
        out = []
        for item in items:
            if item.get("separator"):
                out.append(("separator", ""))
            elif "note" in item or item.get("scope", "in") == "out":
                continue
            elif item.get("label") is None:
                continue
            elif "submenu" in item:
                out.append(("label", "  " * depth + translate(item["label"])))
                out.extend(expected_panel(item["submenu"], depth + 1))
            else:
                out.append(
                    (
                        "operator",
                        item.get("operator", "sketchup.stub"),
                        "  " * depth + translate(item["label"]),
                    )
                )
        return out

    def find_items(item_id):
        for menu in menu_data.MENUS:
            if menu["id"] == item_id:
                return menu["items"]
        stack = [item for menu in menu_data.MENUS for item in menu["items"]]
        while stack:
            item = stack.pop()
            if "submenu" in item:
                if item["id"] == item_id:
                    return item["submenu"]
                stack.extend(item["submenu"])
        return None

    def verify_draws(tag):
        for cls in menus_mod.MENU_CLASSES:
            if cls.bl_idname == menus_mod.MAIN_MENU_ID:
                expected = [("menu", translate(m["label"])) for m in menu_data.MENUS]
            else:
                item_id = cls.bl_idname[len("SKETCHUP_MT_"):].lower()
                expected = expected_menu(find_items(item_id))
            captured = capture(cls, None)
            check("draw %s %s" % (tag, cls.bl_idname), captured == expected)
        tools_expected = [
            ("prop", ""),
            ("label", translate("Blender shortcuts active")),
            ("separator", ""),
        ]
        for menu in menu_data.MENUS:
            tools_expected.append(("label", translate(menu["label"])))
            tools_expected.extend(expected_panel(menu["items"]))
            tools_expected.append(("separator", ""))
        tools_context = SimpleNamespace(
            window_manager=SimpleNamespace(sketchup_mode=False)
        )
        check(
            "draw %s SKETCHUP_PT_tools" % tag,
            capture(panels_mod.SKETCHUP_PT_tools, tools_context) == tools_expected,
        )
        fake_context = SimpleNamespace(
            preferences=SimpleNamespace(addons={}),
            window_manager=SimpleNamespace(
                sketchup_session=SimpleNamespace(vcb_text="")
            ),
        )
        vcb_expected = [
            ("label", translate("Default unit:")),
            ("label", "mm"),
            ("label", translate("VCB:")),
            ("label", ""),
        ]
        check(
            "draw %s SKETCHUP_PT_vcb" % tag,
            capture(panels_mod.SKETCHUP_PT_vcb, fake_context) == vcb_expected,
        )

    verify_draws("zh")
    bpy.context.preferences.view.language = "en_US"
    check("T() Previous en", translate("Previous") == "Previous")
    check("T() Follow Me en", translate("Follow Me") == "Follow Me")
    verify_draws("en")
    bpy.context.preferences.view.language = "zh_HANS"

    # P1: tool operators, toolbar, session props, keymaps.
    check("op tool_line registered", hasattr(bpy.ops.sketchup, "tool_line"))
    check("op tool_select registered", hasattr(bpy.ops.sketchup, "tool_select"))
    check("op tool_eraser registered", hasattr(bpy.ops.sketchup, "tool_eraser"))
    toolbar_mod = importlib.import_module(module_key + ".toolbar")
    expected_tools = sum(
        2 if spec[4] is not None else 1 for spec in toolbar_mod._TOOL_SPECS
    )
    check(
        "toolbar classes match specs",
        len(toolbar_mod.TOOL_CLASSES) == expected_tools,
        str(len(toolbar_mod.TOOL_CLASSES)),
    )
    check(
        "toolbar has no stubs",
        all(spec[4] is not None for spec in toolbar_mod._TOOL_SPECS),
    )
    check(
        "wm session props registered",
        hasattr(bpy.types.WindowManager, "sketchup_session"),
    )
    keymaps_mod = importlib.import_module(module_key + ".keymaps")

    def our_key_count(keymap_name="3D View"):
        keyconfig = compat.addon_keyconfig()
        if keyconfig is None:
            return -1
        keymap = keyconfig.keymaps.get(keymap_name)
        if keymap is None:
            return 0
        return sum(
            1
            for item in keymap.keymap_items
            if item.idname.startswith("sketchup.tool_")
        )

    # SU Mode defaults to OFF: no keymaps until the switch is flipped.
    check("mode default off", bpy.context.window_manager.sketchup_mode is False)
    check(
        "keymaps empty at enable",
        all(our_key_count(name) == 0 for name in ("3D View", "Mesh", "Object Mode")),
        str([our_key_count(name) for name in ("3D View", "Mesh", "Object Mode")]),
    )
    check("op toggle_mode registered", hasattr(bpy.ops.sketchup, "toggle_mode"))
    check("op array_repeat registered", hasattr(bpy.ops.sketchup, "array_repeat"))
    check(
        "disable_conflicts headless safe",
        keymaps_mod.disable_conflicts() == [],
    )
    check("restore_conflicts headless safe", keymaps_mod.restore_conflicts() == 0)
    tool_settings = bpy.context.scene.tool_settings
    check("snap default off", tool_settings.use_snap is False)
    result = bpy.ops.sketchup.toggle_mode()
    check("toggle mode on", result == {"FINISHED"}, str(result))
    check("mode flag on", bpy.context.window_manager.sketchup_mode is True)
    expected_tools = sum(
        1 for entry in keymaps_mod.KEYMAP_TABLE if entry[0].startswith("sketchup.tool_")
    )
    check(
        "keymaps on in 3 keymaps",
        all(our_key_count(name) == expected_tools for name in ("3D View", "Mesh", "Object Mode")),
        str([our_key_count(name) for name in ("3D View", "Mesh", "Object Mode")]),
    )
    check("snap on in SU mode", tool_settings.use_snap is True)
    check("pivot cursor in SU mode", tool_settings.transform_pivot_point == "CURSOR")
    result = bpy.ops.sketchup.toggle_mode()
    check("toggle mode off", result == {"FINISHED"}, str(result))
    check("mode flag off", bpy.context.window_manager.sketchup_mode is False)
    check(
        "keymaps off after toggle",
        all(our_key_count(name) == 0 for name in ("3D View", "Mesh", "Object Mode")),
        str([our_key_count(name) for name in ("3D View", "Mesh", "Object Mode")]),
    )
    check("snap restored", tool_settings.use_snap is False)
    check(
        "pivot restored",
        tool_settings.transform_pivot_point == "MEDIAN_POINT",
        tool_settings.transform_pivot_point,
    )

    check("op tool_move registered", hasattr(bpy.ops.sketchup, "tool_move"))
    check("op tool_rotate registered", hasattr(bpy.ops.sketchup, "tool_rotate"))
    check("op tool_scale registered", hasattr(bpy.ops.sketchup, "tool_scale"))
    check("op tool_push_pull registered", hasattr(bpy.ops.sketchup, "tool_push_pull"))
    check("op tool_offset registered", hasattr(bpy.ops.sketchup, "tool_offset"))
    check("op tool_follow_me registered", hasattr(bpy.ops.sketchup, "tool_follow_me"))
    check("op tool_flip registered", hasattr(bpy.ops.sketchup, "tool_flip"))
    keymaps_mod.apply_level(0)
    check("keymap level0 0 items", our_key_count() == 0, str(our_key_count()))
    keymaps_mod.apply_level(2)
    check("keymap level2 items", our_key_count() == expected_tools, str(our_key_count()))
    keymaps_mod.apply_level(1)
    check("keymap back level1 items", our_key_count() == expected_tools, str(our_key_count()))

    # P1: geometry suite against the INSTALLED module.
    geometry_mod = importlib.import_module(module_key + ".core.geometry")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import geometry_suite

    check("geometry suite", geometry_suite.run(geometry_mod) == 0)

    # P1: Line execute() end to end (headless object-mode path).
    bpy.context.view_layer.objects.active = None
    rect_points = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 0)]
    for a, b in zip(rect_points, rect_points[1:]):
        result = bpy.ops.sketchup.tool_line(point_a=a, point_b=b)
        check("line execute finished", result == {"FINISHED"}, str(result))
    sketchup_obj = bpy.data.objects.get("SketchUp Model")
    check("line execute object created", sketchup_obj is not None)
    if sketchup_obj is not None:
        check(
            "line execute rect 1 face",
            len(sketchup_obj.data.polygons) == 1,
            str(len(sketchup_obj.data.polygons)),
        )
        check(
            "line execute rect 4 edges",
            len(sketchup_obj.data.edges) == 4,
            str(len(sketchup_obj.data.edges)),
        )

    # Diagnostics (non-fatal): msgids where Blender's built-in
    # translation wins over the add-on dictionary.
    collisions = []
    translations = importlib.import_module(module_key + ".i18n.translations")
    for (context, msgid), ours in translations.TRANSLATIONS["zh_HANS"].items():
        shown = bpy.app.translations.pgettext_iface(msgid)
        if shown != ours:
            collisions.append((msgid, ours, shown))
    print("translation collisions (built-in wins): %d" % len(collisions))
    for msgid, ours, shown in collisions:
        print("  COLLISION msgid=%r ours=%r shown=%r" % (msgid, ours, shown))

    # P1: modal flows against the INSTALLED module (fake events).
    import modal_flows

    check("modal flows", modal_flows.run(module) == 0)

    # P2: shape flows against the INSTALLED module (fake events).
    import shape_flows

    check("shape flows", shape_flows.run(module) == 0)

    # P3: transform/sweep math against the INSTALLED modules.
    import transform_math_suite

    check(
        "transform math suite",
        transform_math_suite.run(module) == 0,
    )

    # P3: transform flows against the INSTALLED module (fake events).
    import transform_flows

    check("transform flows", transform_flows.run(module) == 0)

    # P4-P6: drivers, data modules, coverage.
    import p4_p6_suite

    check("p4p6 suite", p4_p6_suite.run(module) == 0)

    # P6: modal flows (direct switching, axes, dimension, tape, text).
    import p6_flows

    check("p6 flows", p6_flows.run(module) == 0)

    # Disable: everything must go away cleanly.
    bpy.ops.preferences.addon_disable(module=module_key)
    check(
        "addon entry removed after disable",
        find_addon_entry() is None,
    )
    for cls_name in ("SKETCHUP_MT_MAIN", "SKETCHUP_MT_TOOLS", "SKETCHUP_PT_tools"):
        check("class unregistered: %s" % cls_name, not hasattr(bpy.types, cls_name))
    check(
        "translations unregistered",
        bpy.app.translations.pgettext_iface("SketchUp Select (P0 stub)")
        == "SketchUp Select (P0 stub)",
    )
    check("keymaps removed after disable", our_key_count() == 0, str(our_key_count()))
    check(
        "wm session props removed after disable",
        not hasattr(bpy.types.WindowManager, "sketchup_session"),
    )

    # Re-enable: clean re-registration, no "already registered" errors.
    bpy.ops.preferences.addon_enable(module=module_key)
    check(
        "re-enable registers classes",
        hasattr(bpy.types, "SKETCHUP_MT_MAIN")
        and hasattr(bpy.types, "SKETCHUP_PT_tools"),
    )
    check(
        "re-enable restores translations",
        bpy.app.translations.pgettext_iface("SketchUp Select (P0 stub)")
        == "SketchUp 选择（P0 占位）",
    )

    print("T2 PASS (%d checks)" % len(CHECKS))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        print("T2 FAIL")
        sys.exit(1)
