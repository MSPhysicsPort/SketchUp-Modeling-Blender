"""Tape Measure, Protractor, and Axes tools (proposal §3.9, P6).

Guides and drawing axes live in world coordinates and are
persisted to the scene (scene_props). Tape Measure VCB input after
a measurement resizes the whole model, with a confirmation dialog
(like SketchUp's resize prompt).
"""

import math

import bpy
from mathutils import Matrix, Vector

from ..context import undo_push
from ..core import geometry as geometry_mod
from ..core.state import DrawingAxes, get_session
from ..core.units import format_length
from ..i18n.translations import translate as _T
from ..scene_props import save_axes, save_guides
from .base import SketchUpToolBase

GUIDE_COLOR = (1.0, 0.0, 1.0, 0.9)


def resize_model(scene, factor):
    """Scale every root object about the world origin, plus the
    guides and drawing axes. One Undo step (caller pushes)."""
    scale = Matrix.Scale(factor, 4)
    for obj in scene.objects:
        if obj.parent is None:
            obj.matrix_world = scale @ obj.matrix_world
    session = get_session()
    session.guides.points = [
        tuple(Vector(p) * factor) for p in session.guides.points
    ]
    session.guides.lines = [
        (tuple(Vector(p) * factor), d) for p, d in session.guides.lines
    ]
    session.axes.origin = tuple(Vector(session.axes.origin) * factor)
    save_guides(scene)
    save_axes(scene)


# ---------------------------------------------------------------------------
# Resize confirmation dialog.
# ---------------------------------------------------------------------------

_pending_resize = {"factor": None, "old": None, "new": None}


class SKETCHUP_OT_tape_resize_confirm(bpy.types.Operator):
    bl_idname = "sketchup.tape_resize_confirm"
    bl_label = "Resize Model"
    bl_description = "Confirm resizing the entire model"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.label(text=_T("Resize the entire model?"))
        layout.label(
            text=_T("Measured %s -> %s (factor %.4f)")
            % (
                _pending_resize["old"] or "",
                _pending_resize["new"] or "",
                _pending_resize["factor"] or 1.0,
            )
        )

    def execute(self, context):
        factor = _pending_resize["factor"]
        if factor is None or factor <= 0:
            return {"CANCELLED"}
        resize_model(context.scene, factor)
        _pending_resize["factor"] = None
        undo_push("SketchUp Resize Model")
        self.report({"INFO"}, _T("Model resized (factor %.4f)") % factor)
        return {"FINISHED"}


def request_resize(factor, old_text, new_text):
    _pending_resize["factor"] = factor
    _pending_resize["old"] = old_text
    _pending_resize["new"] = new_text

    def _invoke():
        try:
            bpy.ops.sketchup.tape_resize_confirm("INVOKE_DEFAULT")
        except Exception:
            pass
        return None

    try:
        bpy.app.timers.register(_invoke, first_interval=0.0)
    except Exception:
        pass


class SKETCHUP_OT_delete_guides(bpy.types.Operator):
    bl_idname = "sketchup.delete_guides"
    bl_label = "Delete Guides"
    bl_description = "Delete all guide lines and points"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        get_session().guides.clear()
        save_guides(context.scene)
        undo_push("SketchUp Delete Guides")
        return {"FINISHED"}


class SKETCHUP_OT_axes_reset(bpy.types.Operator):
    bl_idname = "sketchup.axes_reset"
    bl_label = "Reset Drawing Axes"
    bl_description = "Reset the drawing axes to the world axes"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        get_session().axes.reset()
        save_axes(context.scene)
        undo_push("SketchUp Reset Axes")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Tape Measure.
# ---------------------------------------------------------------------------


class SKETCHUP_OT_tool_tape_measure(SketchUpToolBase):
    bl_idname = "sketchup.tool_tape_measure"
    bl_label = "Tape Measure"
    bl_description = "Measure distances, place guides, resize the model."
    vcb_kind = "length"

    def on_setup(self, context, event):
        self.state = "WAIT_FIRST"
        self.start = None
        self.current_point = None
        self.guide_direction = None  # world edge direction, or None
        self.last_measurement = None  # (start, end, length)
        self.overlay.set_screentip(
            _T("Click a start point (an edge starts a guide line)"),
            (20, 60),
        )

    def on_mouse_move(self, context, event):
        inference = self.compute_inference(
            context, event,
            start_point=tuple(self.start) if self.start else None,
        )
        if inference is None:
            return
        self.current_point = Vector(inference.point)
        self.overlay.set_marker(
            inference.point, inference.kind, inference.color
        )
        lines = []
        if self.start is not None:
            lines.append(
                (self.start, self.current_point, GUIDE_COLOR, True)
            )
            if self.guide_direction is not None:
                direction = self.guide_direction
                lines.append(
                    (
                        self.current_point - direction * 10.0,
                        self.current_point + direction * 10.0,
                        GUIDE_COLOR,
                        True,
                    )
                )
        self.overlay.set_lines(lines)

    def vcb_display_value(self, context):
        if self.start is not None and self.current_point is not None:
            length = (self.current_point - self.start).length
            return format_length(length, self._default_unit(context), precision=2)
        return ""

    def on_left_press(self, context, event):
        if self.current_point is None:
            inference = self.compute_inference(context, event)
            if inference is None:
                return None
            self.current_point = Vector(inference.point)
        if self.state == "WAIT_FIRST":
            self.start = Vector(self.current_point)
            self.guide_direction = None
            picked = self.pick_at(context, event)
            if picked is not None and picked[0] == "edge":
                bm = self.edit_context.begin()
                try:
                    geometry_mod.refresh(bm)
                    v1 = bm.verts[picked[1][0]].co
                    v2 = bm.verts[picked[1][1]].co
                    direction = v2 - v1
                    if direction.length > 1e-9:
                        matrix = self.edit_context.object.matrix_world
                        self.guide_direction = (
                            matrix.to_3x3() @ direction
                        ).normalized()
                finally:
                    self.edit_context.abort(bm)
            self.state = "WAIT_SECOND"
            self.overlay.set_screentip(
                _T("Click the end point"), (20, 60)
            )
            return None
        end = Vector(self.current_point)
        length = (end - self.start).length
        self.last_measurement = (Vector(self.start), end, length)
        if self.guide_direction is not None:
            self.session.guides.add_line(end, self.guide_direction)
            save_guides(context.scene)
            self.report(
                {"INFO"},
                _T("Guide line placed (%s from start)")
                % format_length(length, self._default_unit(context), precision=2),
            )
        elif event.ctrl:
            self.session.guides.add_point(end)
            save_guides(context.scene)
            self.report({"INFO"}, _T("Guide point placed"))
        else:
            self.report(
                {"INFO"},
                _T("Distance: %s (type a value + Enter to resize the model)")
                % format_length(length, self._default_unit(context), precision=2),
            )
        self.state = "WAIT_FIRST"
        self.start = None
        self.guide_direction = None
        self.overlay.set_lines([])
        return None

    def on_vcb_commit(self, context, value, kind):
        if value is None or value <= 0:
            return None
        unit = self._default_unit(context)
        if self.state == "WAIT_SECOND" and self.guide_direction is not None:
            # Exact guide offset from the start edge.
            direction = self.guide_direction
            offset = self.current_point - self.start
            offset = offset - offset.dot(direction) * direction
            if offset.length < 1e-9:
                offset = Vector((0, 0, 1))
            offset.normalize()
            point = self.start + offset * value
            self.session.guides.add_line(point, direction)
            save_guides(context.scene)
            self.state = "WAIT_FIRST"
            self.start = None
            self.guide_direction = None
            self.overlay.set_lines([])
            return None
        if self.last_measurement is None:
            self.report({"WARNING"}, _T("Measure something first"))
            return None
        _start, _end, measured = self.last_measurement
        if measured <= 1e-9:
            return None
        request_resize(
            value / measured,
            format_length(measured, unit, precision=2),
            format_length(value, unit, precision=2),
        )
        return None


# ---------------------------------------------------------------------------
# Protractor.
# ---------------------------------------------------------------------------


class SKETCHUP_OT_tool_protractor(SketchUpToolBase):
    bl_idname = "sketchup.tool_protractor"
    bl_label = "Protractor"
    bl_description = "Measure angles and place angled guide lines."
    vcb_kind = "angle"

    def on_setup(self, context, event):
        self.state = "WAIT_CENTER"
        self.center = None
        self.reference = None
        self.plane_normal = Vector((0, 0, 1))
        self.current_point = None
        self.current_angle = None
        self.overlay.set_screentip(
            _T("Click the angle center"), (20, 60)
        )

    def _on_plane(self, point):
        delta = Vector(point) - self.center
        return self.center + delta - delta.dot(self.plane_normal) * self.plane_normal

    def on_mouse_move(self, context, event):
        inference = self.compute_inference(context, event)
        if inference is None:
            return
        point = Vector(inference.point)
        self.overlay.set_marker(
            inference.point, inference.kind, inference.color
        )
        if self.state == "WAIT_CENTER":
            self.current_point = point
            return
        point = self._on_plane(point)
        self.current_point = point
        lines = []
        if self.state == "WAIT_REF":
            lines.append((self.center, point, GUIDE_COLOR, True))
        elif self.state == "WAIT_ANGLE" and self.reference is not None:
            lines.append((self.center, self.reference, GUIDE_COLOR, True))
            lines.append((self.center, point, GUIDE_COLOR, True))
            base = self.reference - self.center
            arm = point - self.center
            if base.length > 1e-9 and arm.length > 1e-9:
                self.current_angle = math.degrees(base.angle(arm))
        self.overlay.set_lines(lines)

    def vcb_display_value(self, context):
        if self.current_angle is not None:
            return "%.2f°" % self.current_angle
        return ""

    def _place_guide(self, context, direction):
        self.session.guides.add_line(self.center, direction)
        save_guides(context.scene)

    def on_left_press(self, context, event):
        if self.current_point is None:
            inference = self.compute_inference(context, event)
            if inference is None:
                return None
            self.current_point = Vector(inference.point)
        if self.state == "WAIT_CENTER":
            self.center = Vector(self.current_point)
            picked = self.pick_at(context, event)
            if picked is not None and picked[0] == "face":
                bm = self.edit_context.begin()
                try:
                    geometry_mod.refresh(bm)
                    face = bm.faces[picked[1]]
                    matrix = self.edit_context.object.matrix_world
                    self.plane_normal = (
                        matrix.to_3x3() @ Vector(face.normal)
                    ).normalized()
                finally:
                    self.edit_context.abort(bm)
            else:
                self.plane_normal = Vector(self.session.axes.z)
            self.state = "WAIT_REF"
            self.overlay.set_screentip(
                _T("Click the 0 degree reference point"), (20, 60)
            )
            return None
        point = self._on_plane(self.current_point)
        if self.state == "WAIT_REF":
            if (point - self.center).length < 1e-9:
                return None
            self.reference = point
            self.state = "WAIT_ANGLE"
            self.overlay.set_screentip(
                _T("Click the angle point"), (20, 60)
            )
            return None
        arm = point - self.center
        if arm.length < 1e-9:
            return None
        self._place_guide(context, arm.normalized())
        self.report(
            {"INFO"},
            _T("Angle: %.2f degrees") % (self.current_angle or 0.0),
        )
        self.state = "WAIT_CENTER"
        self.center = None
        self.reference = None
        self.current_angle = None
        self.overlay.set_lines([])
        return None

    def on_vcb_commit(self, context, value, kind):
        if value is None or self.state != "WAIT_ANGLE":
            return None
        base = (self.reference - self.center).normalized()
        rotation = Matrix.Rotation(
            math.radians(value), 4, self.plane_normal
        )
        direction = (rotation @ base).normalized()
        self._place_guide(context, direction)
        self.state = "WAIT_CENTER"
        self.center = None
        self.reference = None
        self.current_angle = None
        self.overlay.set_lines([])
        return None


# ---------------------------------------------------------------------------
# Axes.
# ---------------------------------------------------------------------------


class SKETCHUP_OT_tool_axes(SketchUpToolBase):
    bl_idname = "sketchup.tool_axes"
    bl_label = "Axes"
    bl_description = "Place the drawing axes with three clicks."
    vcb_kind = None

    AXIS_COLORS = (
        (1.0, 0.2, 0.2, 1.0),
        (0.2, 0.8, 0.2, 1.0),
        (0.2, 0.4, 1.0, 1.0),
    )

    def on_setup(self, context, event):
        self.state = "WAIT_ORIGIN"
        self.origin = None
        self.x_dir = None
        self.current_point = None
        self.overlay.set_screentip(_T("Click the axes origin"), (20, 60))

    def on_mouse_move(self, context, event):
        inference = self.compute_inference(context, event)
        if inference is None:
            return
        self.current_point = Vector(inference.point)
        self.overlay.set_marker(
            inference.point, inference.kind, inference.color
        )
        lines = []
        if self.state == "WAIT_X" and self.origin is not None:
            direction = self.current_point - self.origin
            if direction.length > 1e-9:
                lines.append(
                    (self.origin, self.current_point, self.AXIS_COLORS[0], False)
                )
        elif self.state == "WAIT_Y" and self.origin is not None:
            lines.append(
                (self.origin, self.origin + self.x_dir, self.AXIS_COLORS[0], False)
            )
            lines.append(
                (self.origin, self.current_point, self.AXIS_COLORS[1], False)
            )
        self.overlay.set_lines(lines)

    def on_left_press(self, context, event):
        if self.current_point is None:
            inference = self.compute_inference(context, event)
            if inference is None:
                return None
            self.current_point = Vector(inference.point)
        if self.state == "WAIT_ORIGIN":
            self.origin = Vector(self.current_point)
            self.state = "WAIT_X"
            self.overlay.set_screentip(
                _T("Click the red axis direction"), (20, 60)
            )
            return None
        if self.state == "WAIT_X":
            direction = self.current_point - self.origin
            if direction.length < 1e-9:
                return None
            self.x_dir = direction.normalized()
            self.state = "WAIT_Y"
            self.overlay.set_screentip(
                _T("Click the green axis direction"), (20, 60)
            )
            return None
        y_raw = self.current_point - self.origin
        y_raw = y_raw - y_raw.dot(self.x_dir) * self.x_dir
        if y_raw.length < 1e-9:
            self.report(
                {"WARNING"}, _T("Pick a point off the red axis")
            )
            return None
        y_dir = y_raw.normalized()
        z_dir = self.x_dir.cross(y_dir).normalized()
        y_dir = z_dir.cross(self.x_dir).normalized()
        self.session.axes = DrawingAxes(
            origin=tuple(self.origin),
            x=tuple(self.x_dir),
            y=tuple(y_dir),
            z=tuple(z_dir),
        )
        save_axes(context.scene)
        undo_push("SketchUp Axes")
        self.report({"INFO"}, _T("Drawing axes placed"))
        return {"FINISHED"}


MEASURE_OPERATORS = [
    SKETCHUP_OT_tape_resize_confirm,
    SKETCHUP_OT_delete_guides,
    SKETCHUP_OT_axes_reset,
    SKETCHUP_OT_tool_tape_measure,
    SKETCHUP_OT_tool_protractor,
    SKETCHUP_OT_tool_axes,
]
