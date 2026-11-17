"""Line tool (research/01 §5.2.1): click to set points, preview
follows the inference engine, Enter commits a VCB length, Esc
restarts the current segment, Alt cycles the linear-inference
toggle. Continuous polylines: each click starts the next segment.
Typing a length right after a segment (before moving the mouse)
re-enters it and modifies the last segment.
"""

import bpy
from mathutils import Vector

from ..context import EditContext, undo_push
from ..core import geometry as geometry_mod
from ..core import inference as inference_mod
from ..core.units import format_length
from ..i18n.translations import translate as _T
from .base import SketchUpToolBase

LINE_MODE_LABELS = {
    inference_mod.LINE_MODE_ALL_ON: "All Inferences On",
    inference_mod.LINE_MODE_ALL_OFF: "All Inferences Off",
    inference_mod.LINE_MODE_PARALLEL_PERP: "Parallel and Perpendicular Only",
}


class SKETCHUP_OT_tool_line(SketchUpToolBase):
    bl_idname = "sketchup.tool_line"
    bl_label = "Line"
    bl_description = "SketchUp Line tool: draw edges, close loops to make faces."

    vcb_kind = "length"
    vcb_label = "Length"

    point_a: bpy.props.FloatVectorProperty(name="Point A", size=3)
    point_b: bpy.props.FloatVectorProperty(name="Point B", size=3)

    # -- setup / hooks ---------------------------------------------------

    def on_setup(self, context, event):
        self.state = "WAIT_FIRST"
        self.start = None
        self.current_point = None
        self.last_segment = None
        self.mouse_moved_since_commit = False
        self.segments = 0

    def _lock_anchor(self, context, event):
        if self.start is not None:
            return tuple(self.start)
        # Explicit base call (not super()): keeps the method callable
        # on test drivers that are not real operator instances.
        return SketchUpToolBase._lock_anchor(self, context, event)

    def resolve_vcb_kind(self, text):
        stripped = text.strip()
        if stripped.startswith("[") or stripped.startswith("<"):
            return "coordinate"
        return "length"

    def on_mouse_move(self, context, event):
        inference = self.compute_inference(
            context, event, start_point=tuple(self.start) if self.start else None
        )
        if inference is None:
            return
        self.current_point = Vector(inference.point)
        if self.state == "WAIT_SECOND":
            self.mouse_moved_since_commit = True
        self._update_overlay(context, event, inference)

    def _update_overlay(self, context, event, inference):
        self.overlay.set_marker(inference.point, inference.kind, inference.color)
        self.overlay.set_screentip(
            _T(inference.label) if inference.label else "",
            (event.mouse_region_x, event.mouse_region_y),
        )
        lines = []
        if self.state == "WAIT_SECOND" and self.start is not None:
            if inference.kind in ("axis", "from_point") or self.session.lock.locked:
                color = inference.color
            else:
                color = (1.0, 1.0, 1.0, 1.0)
            lines.append((self.start, Vector(inference.point), color, False))
        if inference.kind == "from_point" and self.session.from_point is not None:
            lines.append(
                (
                    Vector(self.session.from_point),
                    Vector(inference.point),
                    inference.color,
                    True,
                )
            )
        self.overlay.set_lines(lines)

    def vcb_display_value(self, context):
        if (
            self.state == "WAIT_SECOND"
            and self.start is not None
            and self.current_point is not None
        ):
            length = (self.current_point - self.start).length
            return format_length(length, self._default_unit(context), precision=2)
        return ""

    # -- confirm / commit --------------------------------------------------

    def on_left_press(self, context, event):
        if self.current_point is None:
            inference = self.compute_inference(
                context, event, start_point=tuple(self.start) if self.start else None
            )
            if inference is None:
                return None
            self.current_point = Vector(inference.point)
        if self.state == "WAIT_FIRST":
            self.start = Vector(self.current_point)
            self.state = "WAIT_SECOND"
            self.session.from_point = None
            return None
        self._commit_segment(context, Vector(self.current_point))
        return None

    def _commit_segment(self, context, end_world):
        start_world = Vector(self.start)
        local_a = self.edit_context.to_local(start_world)
        local_b = self.edit_context.to_local(end_world)
        bm = self.edit_context.begin()
        try:
            summary = geometry_mod.apply_line(bm, local_a, local_b)
        finally:
            self.edit_context.commit(bm)
        if summary["status"] in ("degenerate", "exists"):
            return
        undo_push("SketchUp Line")
        direction = end_world - start_world
        if direction.length > 1e-9:
            self.session.last_line_direction = tuple(direction.normalized())
        self.last_segment = (start_world, end_world)
        self.start = end_world
        self.mouse_moved_since_commit = False
        self.segments += 1

    def on_vcb_commit(self, context, value, kind):
        if kind == "coordinate":
            self._commit_coordinate(context, value)
        else:
            self._commit_length(context, value)
        return None

    def _commit_coordinate(self, context, value):
        is_relative, components = value
        axes = self.session.axes
        axis_dirs = (Vector(axes.x), Vector(axes.y), Vector(axes.z))
        origin = Vector(axes.origin)
        if is_relative:
            base = Vector(self.start) if self.start is not None else origin
            target = Vector(base)
            for i, component in enumerate(components):
                if component is not None:
                    target += axis_dirs[i] * component
        else:
            current = self.current_point if self.current_point is not None else origin
            target = Vector(origin)
            for i, component in enumerate(components):
                if component is not None:
                    target += axis_dirs[i] * component
                else:
                    target += axis_dirs[i] * (current - origin).dot(axis_dirs[i])
        if self.state == "WAIT_FIRST":
            self.start = target
            self.state = "WAIT_SECOND"
            self.current_point = target
        else:
            self._commit_segment(context, target)

    def _commit_length(self, context, length):
        if self.last_segment is not None and not self.mouse_moved_since_commit:
            self._modify_last_segment(context, length)
            return
        if self.state != "WAIT_SECOND" or self.start is None:
            return
        if self.current_point is not None:
            direction = self.current_point - self.start
        else:
            direction = Vector((0.0, 0.0, 0.0))
        if direction.length < 1e-9:
            if self.session.last_line_direction is not None:
                direction = Vector(self.session.last_line_direction)
            else:
                direction = Vector((1.0, 0.0, 0.0))
        direction.normalize()
        self._commit_segment(context, self.start + direction * length)

    def _modify_last_segment(self, context, length):
        start_world, end_world = self.last_segment
        direction = end_world - start_world
        if direction.length < 1e-9:
            return
        direction.normalize()
        new_end = start_world + direction * length
        bm = self.edit_context.begin()
        try:
            local_a = self.edit_context.to_local(start_world)
            local_b = self.edit_context.to_local(end_world)
            v1 = geometry_mod.find_vert_near(bm, local_a)
            v2 = geometry_mod.find_vert_near(bm, local_b)
            if v1 is not None and v2 is not None:
                edge = bm.edges.get((v1, v2))
                if edge is not None:
                    geometry_mod.delete_edge(bm, edge, heal=False)
            geometry_mod.apply_line(
                bm, self.edit_context.to_local(start_world),
                self.edit_context.to_local(new_end),
            )
        finally:
            self.edit_context.commit(bm)
        undo_push("SketchUp Line")
        self.last_segment = (start_world, new_end)
        self.start = new_end
        self.mouse_moved_since_commit = False

    # -- escape / alt ------------------------------------------------------

    def on_escape(self, context, event):
        if self.state == "WAIT_SECOND":
            self.start = None
            self.state = "WAIT_FIRST"
            self.overlay.clear()
            return {"RUNNING_MODAL"}
        return None

    def on_alt_press(self, context, event):
        self.session.lock.press_alt_line()
        self.report(
            {"INFO"}, _T(LINE_MODE_LABELS[self.session.lock.line_mode])
        )

    # -- scripted use ------------------------------------------------------

    def execute(self, context):
        if (Vector(self.point_b) - Vector(self.point_a)).length < 1e-9:
            return {"FINISHED"}
        edit_context = EditContext(context)
        bm = edit_context.begin()
        try:
            geometry_mod.apply_line(
                bm,
                edit_context.to_local(Vector(self.point_a)),
                edit_context.to_local(Vector(self.point_b)),
            )
        finally:
            edit_context.commit(bm)
        return {"FINISHED"}
