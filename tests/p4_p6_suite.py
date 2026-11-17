"""P4-P6 integration suite: runs inside Blender against the
installed module (see run_t2.py). Covers the boolean/intersect
drivers, tags/materials/sections/solids/annotations data modules,
group/component round-trips, hide/unhide, and the menu/keymap/
translation coverage checks.
"""

import ast
import os
import re

import bmesh
import bpy
from mathutils import Quaternion, Vector

FAILED = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print("[%s] p4p6 %s %s" % (status, name, detail))
    if not condition:
        FAILED.append(name)


def approx(a, b, tol=1e-6):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    bpy.context.view_layer.objects.active = None


def make_cube(name, size=2.0, location=(0, 0, 0)):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    bm.to_mesh(mesh)
    bm.free()
    obj.location = location
    bpy.context.view_layer.update()
    return obj


def mesh_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    volume = bm.calc_volume()
    bm.free()
    return volume


# ---------------------------------------------------------------------------
# Pure math.
# ---------------------------------------------------------------------------


def suite_math(module):
    ix = module.core.intersect
    # Crossing triangles: one segment.
    segs = ix.tri_tri_segments(
        [(0, 0, 0), (2, 0, 0), (0, 2, 0)],
        [(1, -1, -1), (1, 1, -1), (1, 0, 1)],
    )
    check("tri-tri crossing 1 segment", len(segs) == 1, str(segs))
    # Disjoint: none.
    segs = ix.tri_tri_segments(
        [(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        [(5, 0, 0), (6, 0, 0), (5, 1, 0)],
    )
    check("tri-tri disjoint empty", segs == [])
    # Touching at a point: none.
    segs = ix.tri_tri_segments(
        [(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        [(1, 0, 0), (2, 0, 0), (1, 1, 0)],
    )
    check("tri-tri point touch empty", segs == [])
    # Coplanar overlap: boundary segments.
    segs = ix.tri_tri_segments(
        [(0, 0, 0), (2, 0, 0), (0, 2, 0)],
        [(1, 0, 0), (3, 0, 0), (1, 2, 0)],
    )
    check("tri-tri coplanar segments", len(segs) >= 2, str(len(segs)))

    # Sweep segment.
    sw = module.core.sweep
    prof = [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((1, 1, 0)), Vector((0, 1, 0))]
    ring1, quads = sw.sweep_segment(
        prof, Vector((0, 0, 1)), Vector((0.5, 0.5, 0)), Vector((1, 0, 0)), 2.0
    )
    check("sweep segment ring plane", all(abs(p.x - 2.5) < 1e-6 for p in ring1))
    check("sweep segment 4 quads", len(quads) == 4)

    # Dimension geometry.
    ann = module.data.annotations
    layout = ann.dimension_geometry((0, 0, 0), (2, 0, 0), (1, 1, 0))
    check("dimension length", abs(layout["length"] - 2.0) < 1e-9)
    check("dimension dim_a", approx(layout["dim_a"], (0, 1, 0)))
    check("dimension degenerate", ann.dimension_geometry((0, 0, 0), (0, 0, 0), (1, 1, 0)) is None)

    # Lasso 2D math.
    lasso = module.tools.lasso
    check("lasso cw area negative", lasso.polygon_signed_area([(0, 0), (0, 1), (1, 1), (1, 0)]) < 0)
    check("lasso point inside", lasso.point_in_polygon((0.5, 0.5), [(0, 0), (0, 1), (1, 1), (1, 0)]))
    check("lasso point outside", not lasso.point_in_polygon((2, 2), [(0, 0), (0, 1), (1, 1), (1, 0)]))
    check("lasso segments cross", lasso.segments_intersect_2d((0, 0), (2, 2), (0, 2), (2, 0)))
    check("lasso segments parallel", not lasso.segments_intersect_2d((0, 0), (1, 0), (0, 1), (1, 1)))

    # Camera math.
    cam = module.tools.camera_tools
    check("orbit angle", abs(cam.orbit_rotation(Quaternion(), 100, 0).angle - 0.5) < 0.01)
    check("fit distance", abs(cam.fit_distance(1.0) - 1.0 / 0.7) < 1e-9)
    leveled = cam.level_rotation(Quaternion((0.7, 0.7, 0, 0)))
    check("level rotation horizontal", abs((leveled @ Vector((0, 0, -1))).z) < 1e-6)
    check("iso rotation", cam.iso_rotation().angle > 0.1)

    # Switching table.
    switching = module.tools.switching
    from types import SimpleNamespace

    def fake_event(type_, shift=False, ctrl=False, alt=False):
        return SimpleNamespace(type=type_, shift=shift, ctrl=ctrl, alt=alt, value="PRESS")

    check(
        "switch L->R",
        switching.switch_target(fake_event("R"), "sketchup.tool_line", True) == "sketchup.tool_rectangle",
    )
    check(
        "switch blocked by VCB",
        switching.switch_target(fake_event("S"), "sketchup.tool_line", False) is None,
    )
    check(
        "switch same tool none",
        switching.switch_target(fake_event("L"), "sketchup.tool_line", True) is None,
    )


# ---------------------------------------------------------------------------
# Drivers: intersect / punch / boolean / solid.
# ---------------------------------------------------------------------------


def suite_drivers(module):
    ix = module.core.intersect

    def quad_bm(quads):
        bm = bmesh.new()
        for quad in quads:
            bm.faces.new([bm.verts.new(Vector(c)) for c in quad])
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        return bm

    bm = quad_bm([[(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)],
                  [(0, -1, -1), (0, 1, -1), (0, 1, 1), (0, -1, 1)]])
    added = ix.intersect_in_bmesh(bm, [0], "CONTEXT", None)
    check("intersect crossing", added == 2 and len(bm.faces) == 4, "%d/%d" % (added, len(bm.faces)))
    bm.free()
    bm = quad_bm([[(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)],
                  [(0, -1, 0), (2, -1, 0), (2, 1, 0), (0, 1, 0)]])
    added = ix.intersect_in_bmesh(bm, [0], "CONTEXT", None)
    check("intersect coplanar", added == 2 and len(bm.faces) == 3, "%d/%d" % (added, len(bm.faces)))
    bm.free()

    punch = module.core.punch
    clear_scene()
    obj = make_cube("Box")
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    top = max(bm.faces, key=lambda f: f.calc_center_median().z)
    limit = punch.find_push_limit(bm, top.calc_center_median(), -Vector(top.normal), skip_face_index=top.index)
    bm.free()
    check("push limit", limit is not None and abs(limit - 2.0) < 0.01, str(limit))
    loop = [Vector((x, y, 1.0)) for x, y in [(-0.25, -0.25), (0.25, -0.25), (0.25, 0.25), (-0.25, 0.25)]]
    check("punch applies", punch.punch_through_mesh(obj.data, loop, Vector((0, 0, -1)), 2.01))
    check("punch volume", abs(mesh_volume(obj) - 7.5) < 0.01, str(mesh_volume(obj)))

    solid = module.core.solid
    clear_scene()
    a = make_cube("A")
    b = make_cube("B", location=(1, 0, 0))
    check("is_solid cube", solid.is_solid(a))
    check("solid subtract", solid.solid_operate(a, b, "DIFFERENCE") and abs(mesh_volume(a) - 4.0) < 0.01)
    clear_scene()
    c = make_cube("C")
    d = make_cube("D", location=(1, 0, 0))
    check("solid union_all", solid.union_all([c, d]) and "D" not in bpy.data.objects)
    check("union volume", abs(mesh_volume(c) - 12.0) < 0.01)
    clear_scene()
    e = make_cube("E")
    f = make_cube("F", location=(1, 0, 0))
    check("solid intersect", solid.solid_operate(e, f, "INTERSECT") and abs(mesh_volume(e) - 4.0) < 0.01)
    clear_scene()
    g = make_cube("G")
    h = make_cube("H", location=(1, 0, 0))
    new = solid.solid_split(g, h)
    check("solid split", new is not None and abs(mesh_volume(g) - 4.0) < 0.01 and abs(mesh_volume(new) - 4.0) < 0.01)


# ---------------------------------------------------------------------------
# Data modules.
# ---------------------------------------------------------------------------


def suite_data(module):
    scene = bpy.context.scene
    tags = module.data.tags
    clear_scene()
    tags.ensure_defaults(scene)
    check("untagged exists", "Untagged" in scene.su_tags)
    tags.add_tag(scene, "Walls")
    obj = make_cube("Box1")
    tags.set_object_tag(obj, "Walls")
    tags.find_tag(scene, "Walls").visible = False
    tags.apply_visibility(scene)
    check("tag hide", obj.hide_viewport is True)
    tags.find_tag(scene, "Walls").visible = True
    tags.apply_visibility(scene)
    check("tag show", obj.hide_viewport is False)
    check("tag rename", tags.rename_tag(scene, "Walls", "Walls2") and tags.object_tag(obj) == "Walls2")
    check("tag delete", tags.delete_tag(scene, "Walls2") and tags.object_tag(obj) == "Untagged")
    check("tag delete untagged blocked", not tags.delete_tag(scene, "Untagged"))

    mats = module.data.materials
    default = mats.ensure_default_material()
    check("default material nodes", default.use_nodes and any(n.type == "NEW_GEOMETRY" for n in default.node_tree.nodes))
    check("default material flagged", mats.is_default_material(default))
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    mats.assign_material(bm, [0], default, obj.data)
    mats.apply_true_size_uv(bm, [0], 2.0)
    bm.to_mesh(obj.data)
    bm.free()
    check("material slot", obj.data.materials[0] == default)
    check("uv layer", obj.data.uv_layers.get("SU_UV") is not None)

    secs = module.data.sections
    plane = secs.create_section_plane(scene, (0, 0, 0), (0, 0, 1))
    _origin, normal = secs.plane_frame(plane)
    check("section frame", abs(normal.z - 1.0) < 1e-6)
    secs.set_active_section(scene, plane)
    check("section modifier", obj.modifiers.get("SU_SectionCut") is not None)
    sliced = secs.slice_section(scene, plane)
    check("section slice 4 edges", len(sliced.data.edges) == 4, str(len(sliced.data.edges)))
    secs.set_active_section(scene, None)
    check("section cleared", obj.modifiers.get("SU_SectionCut") is None)

    ann = module.data.annotations
    ann.save_annotations(scene, [])
    ann.add_dimension(scene, (0, 0, 0), (2, 0, 0), (1, 1, 0))
    ann.add_text(scene, (0, 0, 0), "hello")
    check("annotations stored", len(ann.get_annotations(scene)) == 2)
    check("annotation remove", ann.remove_annotation(scene, 0) and len(ann.get_annotations(scene)) == 1)
    ann.save_annotations(scene, [])
    result = bpy.ops.sketchup.text_3d(text="Hi", height=0.5, depth=0.1)
    text_obj = bpy.data.objects.get("3D Text")
    check("3D text object", result == {"FINISHED"} and text_obj is not None and len(text_obj.data.polygons) > 0)

    scenes = module.data.scenes
    scenes.save_scenes(scene, [])
    scenes.add_scene(bpy.context, "Test")
    check("scene captured", len(scenes.get_scenes(scene)) == 1)
    check("scene delete", scenes.delete_scene(scene, 0))

    # Guides / axes persistence round-trip.
    session = module.core.state.get_session()
    session.guides.clear()
    session.guides.add_point((1, 2, 3))
    session.guides.add_line((0, 0, 0), (1, 0, 0))
    module.scene_props.save_guides(scene)
    session.guides.clear()
    module.scene_props.load_guides(scene)
    check("guides persisted", len(session.guides.points) == 1 and len(session.guides.lines) == 1)
    session.axes = module.core.state.DrawingAxes(origin=(1, 0, 0), x=(0, 1, 0), y=(-1, 0, 0), z=(0, 0, 1))
    module.scene_props.save_axes(scene)
    session.axes.reset()
    module.scene_props.load_axes(scene)
    check("axes persisted", approx(session.axes.origin, (1, 0, 0)) and approx(session.axes.x, (0, 1, 0)))
    session.axes.reset()
    session.guides.clear()
    module.scene_props.save_guides(scene)
    module.scene_props.save_axes(scene)


# ---------------------------------------------------------------------------
# Groups / components round-trip.
# ---------------------------------------------------------------------------


def suite_containers(module):
    clear_scene()
    containers = module.core.containers
    mesh = bpy.data.meshes.new("M")
    obj = bpy.data.objects.new("Model", mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    for ox in (0.0, 3.0):
        verts = [bm.verts.new((ox + x, y, 0)) for x, y in [(0, 0), (1, 0), (1, 1), (0, 1)]]
        bm.faces.new(verts)
    bm.to_mesh(mesh)
    bm.free()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.faces[0].select = True
    for vert in bm.faces[0].verts:
        vert.select = True
    new_obj = containers.extract_selection_to_object(bm, obj, "Group", containers.KIND_GROUP)
    bm.to_mesh(mesh)
    bm.free()
    check("extract group", new_obj is not None and len(mesh.polygons) == 1 and len(new_obj.data.polygons) == 1)
    check("group kind", containers.kind_of(new_obj) == containers.KIND_GROUP)
    # Component: duplicate shares the mesh, explode merges back.
    bpy.context.view_layer.objects.active = new_obj
    new_obj.select_set(True)
    mesh2 = bpy.data.meshes.new("M2")
    comp = bpy.data.objects.new("CompObj", mesh2)
    bpy.context.collection.objects.link(comp)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(mesh2)
    bm.free()
    comp[containers.PROP_KIND] = containers.KIND_COMPONENT
    comp.data[containers.PROP_DEF] = "def1"
    inst = bpy.data.objects.new("CompInst", mesh2)
    bpy.context.collection.objects.link(inst)
    inst[containers.PROP_KIND] = containers.KIND_COMPONENT
    check("component shared mesh", comp.data is inst.data)
    containers.set_locked(comp, True)
    check("lock flag", containers.is_locked(comp))
    containers.set_locked(comp, False)
    check("unlock flag", not containers.is_locked(comp))
    # Context stack.
    containers.reset_context_stack(obj.name)
    session = module.core.state.get_session()
    check("context stack root", session.context_stack == [obj.name])
    containers.enter_context(bpy.context, new_obj)
    check("context stack enter", session.context_stack == [obj.name, new_obj.name])
    containers.close_context(bpy.context)
    check("context stack close", session.context_stack == [obj.name])
    containers.reset_context_stack("")


# ---------------------------------------------------------------------------
# Hide / unhide + soften operators.
# ---------------------------------------------------------------------------


def suite_edit_ops(module):
    clear_scene()
    obj = make_cube("Box")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.sketchup.hide()
    check("hide object", obj.hide_viewport is True)
    bpy.ops.sketchup.unhide_last()
    check("unhide last object", obj.hide_viewport is False)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.sketchup.hide()
    bpy.ops.object.mode_set(mode="OBJECT")
    check("hide faces", sum(1 for p in obj.data.polygons if p.hide) == 6)
    bpy.ops.sketchup.unhide_all()
    check("unhide all faces", sum(1 for p in obj.data.polygons if p.hide) == 0)
    # Soften: two coplanar quads sharing an edge.
    clear_scene()
    mesh = bpy.data.meshes.new("M")
    obj = bpy.data.objects.new("Quads", mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    v = [bm.verts.new(c) for c in [(0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 1, 0), (1, 1, 0), (2, 1, 0)]]
    bm.faces.new((v[0], v[1], v[4], v[3]))
    bm.faces.new((v[1], v[2], v[5], v[4]))
    bm.to_mesh(mesh)
    bm.free()
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    import math

    bpy.ops.sketchup.soften_edges(angle=math.radians(20), smooth_normals=True, soften_coplanar=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    bm = bmesh.new()
    bm.from_mesh(mesh)
    layer = bm.edges.layers.int.get(module.core.geometry.EDGE_FLAGS_LAYER)
    soft = sum(1 for e in bm.edges if layer is not None and (e[layer] & module.core.geometry.FLAG_SOFT))
    bm.free()
    check("soften coplanar edge", soft >= 1, str(soft))


# ---------------------------------------------------------------------------
# Coverage: menus, keymaps, translations.
# ---------------------------------------------------------------------------


def suite_coverage(module):
    md = module.data.menu_data
    missing = []

    def walk(items):
        for item in items:
            if "submenu" in item:
                walk(item["submenu"])
                continue
            if item.get("scope") == "out" or "note" in item or item.get("separator"):
                continue
            op = item.get("operator", "sketchup.stub")
            group, name = op.split(".")
            if not hasattr(getattr(bpy.ops, group, None), name):
                missing.append(op)

    for menu in md.MENUS:
        walk(menu["items"])
    check("menu operators exist", not missing, str(sorted(set(missing))))

    keymap_ids = {entry[0] for entry in module.keymaps.KEYMAP_TABLE}
    unregistered = [op for op in keymap_ids if not hasattr(getattr(bpy.ops, op.split(".")[0], None), op.split(".")[1])]
    check("keymap operators exist", not unregistered, str(unregistered))
    switch_ids = set(module.tools.switching.SWITCH_CHORDS.values())
    unregistered = [op for op in switch_ids if not hasattr(getattr(bpy.ops, op.split(".")[0], None), op.split(".")[1])]
    check("switch targets exist", not unregistered, str(unregistered))

    # Translation coverage: every _T literal + menu label has a zh entry.
    root = os.path.dirname(module.__file__)
    translations = module.i18n.translations
    have = set(translations._ZH_MAP)
    used = set()
    for dirpath, _dirnames, filenames in os.walk(root):
        if "__pycache__" in dirpath:
            continue
        for filename in filenames:
            if not filename.endswith(".py") or filename == "translations.py":
                continue
            text = open(os.path.join(dirpath, filename), encoding="utf-8").read()
            for match in re.finditer(r'_T\(\s*"((?:[^"\\]|\\.)*)"\s*[,)]', text):
                used.add(match.group(1))
            for match in re.finditer(r"_T\(\s*'((?:[^'\\]|\\.)*)'\s*[,)]", text):
                used.add(match.group(1))
    for match in re.finditer(r'"label":\s*"((?:[^"\\]|\\.)*)"', open(os.path.join(root, "data", "menu_data.py"), encoding="utf-8").read()):
        used.add(match.group(1))
    missing = sorted(used - have)
    check("translation coverage", not missing, str(missing[:5]))


def run(module):
    """Run all P4-P6 suites; returns exit code."""
    FAILED.clear()
    suite_math(module)
    suite_drivers(module)
    suite_data(module)
    suite_containers(module)
    suite_edit_ops(module)
    suite_coverage(module)
    clear_scene()
    print("p4p6 suite: %s" % ("ALL PASS" if not FAILED else "%d FAILURES: %s" % (len(FAILED), FAILED)))
    return 0 if not FAILED else 1
