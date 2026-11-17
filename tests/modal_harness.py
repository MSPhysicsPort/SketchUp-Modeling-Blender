"""Modal test harness: drive SketchUp modal operators headless with
synthetic mouse/keyboard events and a fake orthographic top view.

Why this exists (Sen, 2026-11-17): the add-on must be self-tested in
Ember's own Blender installs; intermediate versions are no longer
hand-verified on Sen's machine. This harness runs the REAL operator
code (modal dispatch, inference, VCB, geometry commits) against a
fake context + fake projection, so interactive flows are verified
without a GUI.

Projection: screen (x, y) px -> world (x/100, y/100, 0), ray from
z=5 straight down. 100 px = 1 m.

Operator instances cannot be created directly (bpy_struct), so the
harness binds the operator class's plain Python methods onto a
SimpleNamespace driver. The operator code uses no RNA features in
its modal path (only plain attributes + self.report, stubbed), so
the driver executes the exact same code as the real tool.
"""

import types
from types import SimpleNamespace

import bpy
from mathutils import Quaternion, Vector

PX_PER_METER = 100.0


# ---------------------------------------------------------------------------
# Fake projection (orthographic top view).
# ---------------------------------------------------------------------------


def fake_origin_3d(region, rv3d, xy):
    return Vector((xy[0] / PX_PER_METER, xy[1] / PX_PER_METER, 5.0))


def fake_vector_3d(region, rv3d, xy):
    return Vector((0.0, 0.0, -1.0))


def fake_location_2d(region, rv3d, co):
    return Vector((co[0] * PX_PER_METER, co[1] * PX_PER_METER))


def patch_projections(module):
    """Replace the view3d_utils projections in the installed modules."""
    base = module.tools.base
    base.region_2d_to_origin_3d = fake_origin_3d
    base.region_2d_to_vector_3d = fake_vector_3d
    base.location_3d_to_region_2d = fake_location_2d
    module.tools.select.location_3d_to_region_2d = fake_location_2d
    module.tools.eraser.location_3d_to_region_2d = fake_location_2d
    module.tools.shapes.region_2d_to_origin_3d = fake_origin_3d
    module.tools.shapes.region_2d_to_vector_3d = fake_vector_3d


# ---------------------------------------------------------------------------
# Fake context / events.
# ---------------------------------------------------------------------------


class FakeContext:
    """Delegates everything to the real context except the view parts."""

    def __init__(self, real):
        object.__setattr__(self, "_real", real)
        self.region = SimpleNamespace(width=1000, height=1000)
        self.space_data = SimpleNamespace(
            region_3d=SimpleNamespace(
                view_distance=10.0,
                view_rotation=Quaternion(),
                view_location=Vector((0, 0, 0)),
                view_perspective="PERSP",
            )
        )
        self.area = None
        self.mode = "OBJECT"

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_real"), name)

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)


def make_context():
    return FakeContext(bpy.context)


def ev(type_, value="PRESS", x=0, y=0, ascii_="", shift=False, ctrl=False, alt=False):
    return SimpleNamespace(
        type=type_,
        value=value,
        mouse_region_x=x,
        mouse_region_y=y,
        mouse_prev_x=x,
        mouse_prev_y=y,
        ascii=ascii_,
        unicode=ascii_,
        shift=shift,
        ctrl=ctrl,
        alt=alt,
        oskey=False,
    )


# ---------------------------------------------------------------------------
# Driver: bind operator methods onto a plain namespace.
# ---------------------------------------------------------------------------


def make_driver(cls):
    driver = SimpleNamespace()
    driver.bl_idname = cls.bl_idname
    driver.bl_label = cls.bl_label
    driver.vcb_kind = getattr(cls, "vcb_kind", None)
    driver.vcb_label = getattr(cls, "vcb_label", "Measurements")
    driver.reports = []
    driver.report = lambda *args, **kwargs: driver.reports.append((args, kwargs))
    bound = {}
    plain_attrs = {}
    for klass in reversed(cls.__mro__):
        try:
            namespace = vars(klass)
        except TypeError:
            continue
        for name, attr in namespace.items():
            if name.startswith("__") and name.endswith("__"):
                continue
            if isinstance(attr, staticmethod):
                bound[name] = ("static", attr.__func__)
            elif isinstance(attr, classmethod):
                bound[name] = ("class", attr.__func__)
            elif isinstance(attr, types.FunctionType):
                bound[name] = ("method", attr)
            elif isinstance(attr, (bool, int, float, str, tuple, list, dict, set, frozenset, type(None))):
                # Plain class data (is_polygon, is_pie, bl_options, ...).
                plain_attrs[name] = attr
    for name, value in plain_attrs.items():
        setattr(driver, name, value)
    for name, (kind, func) in bound.items():
        if kind == "static":
            setattr(driver, name, func)
        elif kind == "class":
            setattr(driver, name, types.MethodType(func, cls))
        else:
            setattr(driver, name, types.MethodType(func, driver))
    return driver


class ToolDriver:
    """Drive one tool instance through synthetic events."""

    def __init__(self, cls, context):
        self.op = make_driver(cls)
        self.context = context

    def start(self, x=0, y=0):
        self.op._setup(self.context, ev("MOUSEMOVE", x=x, y=y))
        return self

    def send(self, event):
        return self.op.modal(self.context, event)

    def move(self, x, y):
        return self.send(ev("MOUSEMOVE", x=x, y=y))

    def click(self, x, y, shift=False, ctrl=False, alt=False):
        self.move(x, y)
        self.send(ev("LEFTMOUSE", "PRESS", x, y, shift=shift, ctrl=ctrl, alt=alt))
        return self.send(
            ev("LEFTMOUSE", "RELEASE", x, y, shift=shift, ctrl=ctrl, alt=alt)
        )

    def press(self, x, y, shift=False, ctrl=False, alt=False):
        self.move(x, y)
        return self.send(
            ev("LEFTMOUSE", "PRESS", x, y, shift=shift, ctrl=ctrl, alt=alt)
        )

    def release(self, x, y, shift=False, ctrl=False, alt=False):
        return self.send(
            ev("LEFTMOUSE", "RELEASE", x, y, shift=shift, ctrl=ctrl, alt=alt)
        )

    def key(self, type_, value="PRESS", x=0, y=0, **kwargs):
        return self.send(ev(type_, value, x, y, **kwargs))

    def type_text(self, text, x=0, y=0):
        for char in text:
            self.send(ev("TEXTINPUT", "PRESS", x, y, ascii_=char))

    def enter(self, x=0, y=0):
        return self.send(ev("RET", "PRESS", x, y))

    def escape(self, x=0, y=0):
        return self.send(ev("ESC", "PRESS", x, y))

    def right_click(self, x=0, y=0):
        return self.send(ev("RIGHTMOUSE", "PRESS", x, y))

    def finish(self):
        return self.right_click()


# ---------------------------------------------------------------------------
# Scene helpers.
# ---------------------------------------------------------------------------


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    bpy.context.view_layer.objects.active = None


def sketchup_mesh():
    obj = bpy.data.objects.get("SketchUp Model")
    return obj.data if obj is not None else None


def mesh_stats():
    mesh = sketchup_mesh()
    if mesh is None:
        return (0, 0, 0)
    return (len(mesh.vertices), len(mesh.edges), len(mesh.polygons))


def selected_counts():
    mesh = sketchup_mesh()
    if mesh is None:
        return (0, 0, 0)
    return (
        sum(1 for v in mesh.vertices if v.select),
        sum(1 for e in mesh.edges if e.select),
        sum(1 for p in mesh.polygons if p.select),
    )


def vertex_coords():
    mesh = sketchup_mesh()
    if mesh is None:
        return []
    return [tuple(v.co) for v in mesh.vertices]


def edge_coords():
    mesh = sketchup_mesh()
    if mesh is None:
        return []
    verts = [tuple(v.co) for v in mesh.vertices]
    return [(verts[e.vertices[0]], verts[e.vertices[1]]) for e in mesh.edges]
