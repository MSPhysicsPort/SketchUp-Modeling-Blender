"""Shape tools: Rectangle, Rotated Rectangle, Circle, Polygon, Arc,
2-Point Arc, 3-Point Arc, Pie, Freehand (proposal §3.2 / research A
§5.2.2–§5.2.9).

All shapes commit through geometry.apply_line (edges auto-split,
faces heal) and register curve metadata (core/curves.py) so Center
inference and Entity Info radius/segment edits work.

Drawing plane: the plane of the face under the cursor when the
first point lands on a face, otherwise the ground plane through
the drawing axes origin. Arrow keys lock the plane normal to an
axis (Up = blue/Z, Left = green/Y, Right = red/X); pressing the
same arrow again releases the lock.
"""

import math

from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d

from ..context import undo_push
from ..core import curves as curve_mod
from ..core import geometry as geometry_mod
from ..core import state as state_mod
from ..i18n.translations import translate as _T
from .base import SketchUpToolBase

MIN_RADIUS = 1e-4


def _plane_from_inference(session, inference, face_normal, override_normal):
    """Pick (origin, normal) for a shape's drawing plane."""
    if override_normal is not None:
        origin = inference.point if inference is not None else session.axes.origin
        return tuple(origin), tuple(override_normal)
    if inference is not None and inference.kind == "on_face" and face_normal is not None:
        return tuple(inference.point), tuple(face_normal)
    return tuple(session.axes.origin), tuple(session.axes.z)


class ShapeToolBase(SketchUpToolBase):
    """Shared plane handling + shape preview for shape tools."""

    plane_normal_override = None
    plane_origin = None
    plane_normal = None
    shape_label = ""

    def on_setup(self, context, event):
        self.plane_normal_override = None
        self.plane_origin = None
        self.plane_normal = None
        self.shape_label = ""
        self.current_point = None

    def on_mouse_move(self, context, event):
        inference = self.compute_inference(context, event)
        if inference is None:
            return
        self.current_point = tuple(inference.point)
        self.overlay.set_marker(inference.point, inference.kind, inference.color)
        self.overlay.set_screentip(
            _T(inference.label) if inference.label else "",
            (event.mouse_region_x, event.mouse_region_y),
        )
        self.on_shape_move(context, event)

    def on_shape_move(self, context, event):
        pass

    def _on_arrow(self, context, event):
        # Shape tools: arrows lock the drawing PLANE, not a direction.
        axis = {"RIGHT_ARROW": 0, "LEFT_ARROW": 1, "UP_ARROW": 2}.get(event.type)
        if axis is None:
            return
        axes = self.session.axes
        direction = (axes.x, axes.y, axes.z)[axis]
        if (
            self.plane_normal_override is not None
            and abs(sum(a * b for a, b in zip(self.plane_normal_override, direction))) > 0.99
        ):
            self.plane_normal_override = None
        else:
            self.plane_normal_override = tuple(direction)
        self._update_vcb_display(context)
        self._redraw(context)

    def _fix_plane(self, context, event):
        """Fix the drawing plane from the current inference."""
        inference = self._current_inference
        face_normal = None
        if inference is not None and inference.kind == "on_face":
            face_normal = self._face_normal_at(context, event)
        origin, normal = _plane_from_inference(
            self.session, inference, face_normal, self.plane_normal_override
        )
        self.plane_origin = origin
        self.plane_normal = normal
        return origin, normal

    def _face_normal_at(self, context, event):
        bm = self.edit_context.begin()
        try:
            xy = (event.mouse_region_x, event.mouse_region_y)
            origin = region_2d_to_origin_3d(context.region, context.space_data.region_3d, xy)
            direction = region_2d_to_vector_3d(context.region, context.space_data.region_3d, xy)
            hit = self.edit_context.ray_cast_face(bm, origin, direction)
            if hit is None:
                return None
            face_index = hit[1]
            geometry_mod.refresh(bm)
            face = bm.faces[face_index]
            return tuple(self.edit_context.to_world(face.normal, is_direction=True))
        finally:
            self.edit_context.abort(bm)

    def _plane_point(self, point):
        """Project a world point onto the fixed drawing plane."""
        if self.plane_origin is None or self.plane_normal is None:
            return tuple(point)
        return curve_mod.project_on_plane(point, self.plane_origin, self.plane_normal)

    def _set_preview(self, points, closed):
        lines = []
        for a, b in zip(points, points[1:]):
            lines.append((a, b, (1.0, 1.0, 1.0, 1.0), False))
        if closed and len(points) > 2:
            lines.append((points[-1], points[0], (1.0, 1.0, 1.0, 1.0), False))
        self.overlay.set_lines(lines)
        if self.shape_label:
            self.overlay.set_screentip(self.shape_label, self._mouse)

    def _commit_polyline(self, context, points, closed, record):
        """Commit a polyline through apply_line; tag + register curve."""
        bm = self.edit_context.begin()
        try:
            segments = list(zip(points, points[1:]))
            if closed and len(points) > 2:
                segments.append((points[-1], points[0]))
            committed = []
            for a, b in segments:
                local_a = self.edit_context.to_local(a)
                local_b = self.edit_context.to_local(b)
                geometry_mod.apply_line(bm, local_a, local_b)
                committed.append((local_a, local_b))
            # Tag the edges that make up the curve: re-find them by
            # endpoints (apply_line may have split existing edges).
            mesh = self.edit_context.mesh
            curve_id = 0
            if record is not None and mesh is not None:
                curve_id = curve_mod.register_curve(mesh, record)
                geometry_mod.refresh(bm)
                layer = curve_mod.ensure_curve_layer(bm)
                for edge in bm.edges:
                    for local_a, local_b in committed:
                        if _edge_matches(edge, local_a, local_b):
                            edge[layer] = curve_id
                            break
            self.edit_context.commit(bm)
        except Exception:
            self.edit_context.abort(bm)
            raise
        return curve_id

    def _delete_curve_edges(self, context, curve_id):
        """Delete a curve's edges (and dependent faces) for re-draw."""
        bm = self.edit_context.begin()
        try:
            edges = curve_mod.edges_of_curve(bm, curve_id)
            if not edges:
                self.edit_context.abort(bm)
                return False
            geometry_mod.refresh(bm)
            for edge in list(edges):
                if edge.is_valid:
                    geometry_mod.delete_edge(bm, edge, heal=False)
            mesh = self.edit_context.mesh
            if mesh is not None:
                curve_mod.remove_curve(mesh, curve_id)
            self.edit_context.commit(bm)
        except Exception:
            self.edit_context.abort(bm)
            raise
        return True


def _edge_matches(edge, a, b, tol=1e-6):
    v1, v2 = edge.verts
    return (
        (v1.co - a).length <= tol and (v2.co - b).length <= tol
    ) or (
        (v1.co - b).length <= tol and (v2.co - a).length <= tol
    )


def _snap_shape_ratio(width, height, tolerance=0.02):
    """Shape inference: Square / Golden Section snapping.

    Returns (snapped_width, snapped_height, label)."""
    if width <= 0.0 or height <= 0.0:
        return width, height, ""
    if abs(width - height) / max(width, height) <= tolerance:
        side = max(width, height)
        return side, side, "Square"
    ratio = max(width, height) / min(width, height)
    if abs(ratio - curve_mod.GOLDEN_RATIO) / curve_mod.GOLDEN_RATIO <= tolerance:
        if width >= height:
            return height * curve_mod.GOLDEN_RATIO, height, "Golden Section"
        return width, width * curve_mod.GOLDEN_RATIO, "Golden Section"
    return width, height, ""


# ---------------------------------------------------------------------------
# Rectangle (R).
# ---------------------------------------------------------------------------


class SKETCHUP_OT_tool_rectangle(ShapeToolBase):
    bl_idname = "sketchup.tool_rectangle"
    bl_label = "Rectangle"
    bl_description = "SketchUp Rectangle tool."
    vcb_kind = "length_list"
    vcb_label = "Dimensions"

    def on_setup(self, context, event):
        super_setup(self, context, event)
        self.state = "WAIT_FIRST"
        self.corner1 = None
        self.corner2 = None
        self.last_rect = None  # (corner1, corner2, plane_origin, plane_normal, curve_id)
        self._mouse_moved = False

    def on_left_press(self, context, event):
        if self.state == "WAIT_FIRST":
            self._fix_plane(context, event)
            self.corner1 = self._plane_point(self.current_point)
            self.state = "WAIT_SECOND"
            self.session.vcb.clear()
        else:
            self.corner2 = self._plane_point(self.current_point)
            self._commit_rectangle(context)
            self.state = "WAIT_FIRST"
            self.corner1 = None
            self.corner2 = None

    def on_shape_move(self, context, event):
        self._mouse_moved = True
        if self.state == "WAIT_SECOND" and self.corner1 is not None:
            corner2 = self._plane_point(self.current_point)
            u1, v1 = curve_mod.to_plane(self.corner1, self.plane_origin, self.plane_normal)
            u2, v2 = curve_mod.to_plane(corner2, self.plane_origin, self.plane_normal)
            width = abs(u2 - u1)
            height = abs(v2 - v1)
            snapped_w, snapped_h, label = _snap_shape_ratio(width, height)
            if label:
                u2 = u1 + math.copysign(snapped_w, u2 - u1 or 1.0)
                v2 = v1 + math.copysign(snapped_h, v2 - v1 or 1.0)
                corner2 = curve_mod.from_plane((u2, v2), self.plane_origin, self.plane_normal)
                self.shape_label = label
            else:
                self.shape_label = ""
            self.corner2 = corner2
            points = self._rect_points(self.corner1, corner2)
            self._set_preview(points, closed=True)

    def _rect_points(self, corner1, corner2):
        u1, v1 = curve_mod.to_plane(corner1, self.plane_origin, self.plane_normal)
        u2, v2 = curve_mod.to_plane(corner2, self.plane_origin, self.plane_normal)
        return [
            curve_mod.from_plane((u1, v1), self.plane_origin, self.plane_normal),
            curve_mod.from_plane((u2, v1), self.plane_origin, self.plane_normal),
            curve_mod.from_plane((u2, v2), self.plane_origin, self.plane_normal),
            curve_mod.from_plane((u1, v2), self.plane_origin, self.plane_normal),
        ]

    def _commit_rectangle(self, context):
        points = self._rect_points(self.corner1, self.corner2)
        record = {
            "type": "rectangle",
            "center": [sum(p[i] for p in points) / 4.0 for i in range(3)],
            "radius": 0.0,
            "segments": 4,
            "normal": list(self.plane_normal),
            "start_angle": 0.0,
            "end_angle": 0.0,
            "closed": True,
        }
        curve_id = self._commit_polyline(context, points, True, record)
        self.last_rect = (self.corner1, self.corner2, self.plane_origin, self.plane_normal, curve_id)
        self._mouse_moved = False
        undo_push("SketchUp Shape")

    def on_vcb_commit(self, context, value, kind):
        if self.state == "WAIT_SECOND" and self.corner1 is not None and isinstance(value, list):
            u1, v1 = curve_mod.to_plane(self.corner1, self.plane_origin, self.plane_normal)
            current = self._plane_point(self.current_point)
            u2, v2 = curve_mod.to_plane(current, self.plane_origin, self.plane_normal)
            new_u = u1 + value[0] if len(value) > 0 and value[0] is not None else u2
            new_v = v1 + value[1] if len(value) > 1 and value[1] is not None else v2
            self.corner2 = curve_mod.from_plane((new_u, new_v), self.plane_origin, self.plane_normal)
            self._commit_rectangle(context)
            self.state = "WAIT_FIRST"
            self.corner1 = None
            self.corner2 = None
        elif self.last_rect is not None and not self._mouse_moved and isinstance(value, list):
            # Re-type without moving the mouse: resize the last rectangle.
            corner1, _old, origin, normal, curve_id = self.last_rect
            self._delete_curve_edges(context, curve_id)
            u1, v1 = curve_mod.to_plane(corner1, origin, normal)
            self.plane_origin, self.plane_normal = origin, normal
            self.corner1 = corner1
            new_u = u1 + value[0] if len(value) > 0 and value[0] is not None else u1 + 1.0
            new_v = v1 + value[1] if len(value) > 1 and value[1] is not None else v1 + 1.0
            self.corner2 = curve_mod.from_plane((new_u, new_v), origin, normal)
            self._commit_rectangle(context)
            self.state = "WAIT_FIRST"
            self.corner1 = None

    def vcb_display_value(self, context):
        if self.state == "WAIT_SECOND" and self.corner1 is not None and self.corner2 is not None:
            u1, v1 = curve_mod.to_plane(self.corner1, self.plane_origin, self.plane_normal)
            u2, v2 = curve_mod.to_plane(self.corner2, self.plane_origin, self.plane_normal)
            from ..core.units import format_length

            return "%s, %s" % (
                format_length(abs(u2 - u1), self._default_unit(context), precision=2),
                format_length(abs(v2 - v1), self._default_unit(context), precision=2),
            )
        return ""

    def on_escape(self, context, event):
        if self.state == "WAIT_SECOND":
            self.state = "WAIT_FIRST"
            self.corner1 = None
            self.corner2 = None
            self.overlay.set_lines([])
            return {"RUNNING_MODAL"}
        return None


def super_setup(tool, context, event):
    ShapeToolBase.on_setup(tool, context, event)


# ---------------------------------------------------------------------------
# Circle (C) / Polygon.
# ---------------------------------------------------------------------------


class _RoundShapeBase(ShapeToolBase):
    is_polygon = False

    def on_setup(self, context, event):
        super_setup(self, context, event)
        self.state = "WAIT_CENTER"
        self.center = None
        self.radius = 0.0
        self.segments = (
            curve_mod.DEFAULT_POLYGON_SEGMENTS
            if self.is_polygon
            else curve_mod.DEFAULT_CIRCLE_SEGMENTS
        )
        self.last_shape = None
        self._mouse_moved = False

    def resolve_vcb_kind(self, text):
        stripped = text.strip().lower()
        if stripped.endswith("s"):
            return "count"
        if self.state == "WAIT_CENTER":
            # Bare number right after a commit = radius retype;
            # otherwise (fresh tool / mouse moved) = side count.
            if self.last_shape is not None and not self._mouse_moved:
                return "length"
            return "count"
        return "length"

    def on_left_press(self, context, event):
        if self.state == "WAIT_CENTER":
            self._fix_plane(context, event)
            self.center = self._plane_point(self.current_point)
            self.state = "WAIT_RADIUS"
            self.session.vcb.clear()
        else:
            radius_point = self._plane_point(self.current_point)
            self.radius = max(MIN_RADIUS, _distance(self.center, radius_point))
            self._commit_shape(context)
            self.state = "WAIT_CENTER"
            self.center = None

    def on_shape_move(self, context, event):
        self._mouse_moved = True
        if self.state == "WAIT_RADIUS" and self.center is not None:
            radius_point = self._plane_point(self.current_point)
            self.radius = max(MIN_RADIUS, _distance(self.center, radius_point))
            points = curve_mod.circle_points(
                self.center, self.plane_normal, self.radius, self.segments
            )
            self._set_preview(points, closed=True)

    def _commit_shape(self, context):
        points = curve_mod.circle_points(
            self.center, self.plane_normal, self.radius, self.segments
        )
        record = {
            "type": "polygon" if self.is_polygon else "circle",
            "center": list(self.center),
            "radius": self.radius,
            "segments": self.segments,
            "normal": list(self.plane_normal),
            "start_angle": 0.0,
            "end_angle": 360.0,
            "closed": True,
        }
        curve_id = self._commit_polyline(context, points, True, record)
        self._set_smooth_flags(context, curve_id, smooth=not self.is_polygon)
        self.last_shape = (self.center, self.radius, self.segments, self.plane_origin, self.plane_normal, curve_id)
        self._mouse_moved = False
        undo_push("SketchUp Shape")

    def _set_smooth_flags(self, context, curve_id, smooth):
        bm = self.edit_context.begin()
        try:
            for edge in curve_mod.edges_of_curve(bm, curve_id):
                geometry_mod.set_edge_flags(bm, edge, soft=smooth)
            self.edit_context.commit(bm)
        except Exception:
            self.edit_context.abort(bm)
            raise

    def on_vcb_commit(self, context, value, kind):
        if kind == "count" and isinstance(value, int):
            if value >= 3:
                if (
                    self.state == "WAIT_CENTER"
                    and self.last_shape is not None
                    and not self._mouse_moved
                ):
                    center, radius, _s, origin, normal, curve_id = self.last_shape
                    self._delete_curve_edges(context, curve_id)
                    self.plane_origin, self.plane_normal = origin, normal
                    self.center, self.radius, self.segments = center, radius, value
                    self._commit_shape(context)
                    self.state = "WAIT_CENTER"
                    self.center = None
                else:
                    self.segments = value
            return
        if kind == "length" and isinstance(value, float):
            if self.state == "WAIT_RADIUS" and self.center is not None:
                self.radius = max(MIN_RADIUS, value)
                self._commit_shape(context)
                self.state = "WAIT_CENTER"
                self.center = None
            elif self.last_shape is not None:
                # Re-type: redraw with the new radius.
                center, _r, segments, origin, normal, curve_id = self.last_shape
                self._delete_curve_edges(context, curve_id)
                self.plane_origin, self.plane_normal = origin, normal
                self.center, self.radius, self.segments = center, max(MIN_RADIUS, value), segments
                self._commit_shape(context)
                self.state = "WAIT_CENTER"
                self.center = None

    def vcb_display_value(self, context):
        if self.state == "WAIT_RADIUS":
            from ..core.units import format_length

            return format_length(self.radius, self._default_unit(context), precision=2)
        return "Sides: %d" % self.segments

    def on_escape(self, context, event):
        if self.state == "WAIT_RADIUS":
            self.state = "WAIT_CENTER"
            self.center = None
            self.overlay.set_lines([])
            return {"RUNNING_MODAL"}
        return None


class SKETCHUP_OT_tool_circle(_RoundShapeBase):
    bl_idname = "sketchup.tool_circle"
    bl_label = "Circle"
    bl_description = "SketchUp Circle tool."
    vcb_kind = "length"
    vcb_label = "Radius"
    is_polygon = False


class SKETCHUP_OT_tool_polygon(_RoundShapeBase):
    bl_idname = "sketchup.tool_polygon"
    bl_label = "Polygon"
    bl_description = "SketchUp Polygon tool."
    vcb_kind = "length"
    vcb_label = "Radius"
    is_polygon = True


def _distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


# ---------------------------------------------------------------------------
# Arc (protractor) / Pie.
# ---------------------------------------------------------------------------


class _ArcBase(ShapeToolBase):
    is_pie = False

    def on_setup(self, context, event):
        super_setup(self, context, event)
        self.state = "WAIT_CENTER"
        self.center = None
        self.start_angle = 0.0
        self.end_angle = 0.0
        self.radius = 0.0
        self.segments = curve_mod.DEFAULT_ARC_SEGMENTS
        self.last_arc = None

    def resolve_vcb_kind(self, text):
        stripped = text.strip().lower()
        if stripped.endswith("s"):
            return "count"
        if stripped.endswith("c"):
            return None  # Raw: "20c" circle-segment count.
        if self.state in ("WAIT_CENTER", "WAIT_START"):
            return "length"
        return "angle"

    def on_left_press(self, context, event):
        if self.state == "WAIT_CENTER":
            self._fix_plane(context, event)
            self.center = self._plane_point(self.current_point)
            self.state = "WAIT_START"
            self.session.vcb.clear()
        elif self.state == "WAIT_START":
            point = self._plane_point(self.current_point)
            self.radius = max(MIN_RADIUS, _distance(self.center, point))
            self.start_angle = curve_mod.angle_in_plane(point, self.center, self.plane_normal)
            self.state = "WAIT_END"
        else:
            point = self._plane_point(self.current_point)
            self.end_angle = curve_mod.angle_in_plane(point, self.center, self.plane_normal)
            self._commit_arc(context)
            self.state = "WAIT_CENTER"
            self.center = None

    def on_shape_move(self, context, event):
        if self.state == "WAIT_START" and self.center is not None:
            point = self._plane_point(self.current_point)
            self.radius = max(MIN_RADIUS, _distance(self.center, point))
            self.overlay.set_lines([(self.center, point, (1.0, 1.0, 1.0, 1.0), False)])
        elif self.state == "WAIT_END" and self.center is not None:
            point = self._plane_point(self.current_point)
            end_angle = curve_mod.angle_in_plane(point, self.center, self.plane_normal)
            # Snap to half/quarter/three-quarter circle.
            sweep = (end_angle - self.start_angle) % 360.0
            label = ""
            for target, name in ((90.0, "Quarter Circle"), (180.0, "Half Circle"), (270.0, "Three-Quarter Circle")):
                if abs(sweep - target) <= 2.0:
                    end_angle = (self.start_angle + target) % 360.0
                    label = name
                    break
            self.shape_label = label
            points = curve_mod.arc_points(
                self.center, self.plane_normal, self.radius,
                self.start_angle, end_angle, self.segments,
            )
            self._set_preview(points, closed=False)
            if self.is_pie:
                self.overlay.set_lines([
                    (self.center, points[0], (1.0, 1.0, 1.0, 1.0), False),
                    (self.center, points[-1], (1.0, 1.0, 1.0, 1.0), False),
                ])

    def _commit_arc(self, context):
        points = curve_mod.arc_points(
            self.center, self.plane_normal, self.radius,
            self.start_angle, self.end_angle, self.segments,
        )
        if self.is_pie:
            points = points + [self.center]
        record = {
            "type": "pie" if self.is_pie else "arc",
            "center": list(self.center),
            "radius": self.radius,
            "segments": self.segments,
            "normal": list(self.plane_normal),
            "start_angle": self.start_angle,
            "end_angle": self.end_angle,
            "closed": self.is_pie,
        }
        curve_id = self._commit_polyline(context, points, self.is_pie, record)
        self.last_arc = (self.center, self.radius, self.start_angle, self.end_angle, self.segments, self.plane_origin, self.plane_normal, curve_id)
        undo_push("SketchUp Shape")

    def on_vcb_commit(self, context, value, kind):
        if kind is None and isinstance(value, str):
            # "20c": segments as if the full circle had 20 segments.
            stripped = value.strip().lower()
            if stripped.endswith("c"):
                try:
                    total = int(stripped[:-1])
                except ValueError:
                    return
                if self.state == "WAIT_END":
                    sweep = (self.end_angle - self.start_angle) % 360.0 or 360.0
                    self.segments = curve_mod.segments_for_circle_segments(total, sweep)
                elif self.last_arc is not None:
                    sweep = (self.last_arc[3] - self.last_arc[2]) % 360.0 or 360.0
                    self._redraw_arc(
                        context,
                        segments=curve_mod.segments_for_circle_segments(total, sweep),
                    )
                else:
                    self.segments = max(1, total)
            return
        if kind == "count" and isinstance(value, int):
            if self.state == "WAIT_CENTER" and self.last_arc is not None:
                self._redraw_arc(context, segments=value)
            else:
                self.segments = max(1, value)
            return
        if kind == "angle" and isinstance(value, float):
            if self.state == "WAIT_END":
                self.end_angle = (self.start_angle + value) % 360.0
                self._commit_arc(context)
                self.state = "WAIT_CENTER"
                self.center = None
            elif self.state == "WAIT_CENTER" and self.last_arc is not None:
                self._redraw_arc(context, end_angle=(self.last_arc[2] + value) % 360.0)
            return
        if kind == "length" and isinstance(value, float):
            if self.state == "WAIT_CENTER" and self.last_arc is not None:
                self._redraw_arc(context, radius=max(MIN_RADIUS, value))

    def _redraw_arc(self, context, radius=None, end_angle=None, segments=None):
        center, old_radius, start_angle, old_end, old_segments, origin, normal, curve_id = self.last_arc
        self._delete_curve_edges(context, curve_id)
        self.plane_origin, self.plane_normal = origin, normal
        self.center = center
        self.radius = old_radius if radius is None else radius
        self.start_angle = start_angle
        self.end_angle = old_end if end_angle is None else end_angle
        self.segments = old_segments if segments is None else max(1, segments)
        self._commit_arc(context)
        self.state = "WAIT_CENTER"
        self.center = None

    def vcb_display_value(self, context):
        if self.state == "WAIT_END":
            return "%.1f" % ((self.end_angle - self.start_angle) % 360.0)
        return ""

    def on_escape(self, context, event):
        if self.state in ("WAIT_START", "WAIT_END"):
            self.state = "WAIT_CENTER"
            self.center = None
            self.overlay.set_lines([])
            return {"RUNNING_MODAL"}
        return None


class SKETCHUP_OT_tool_arc(_ArcBase):
    bl_idname = "sketchup.tool_arc"
    bl_label = "Arc"
    bl_description = "SketchUp Arc tool."
    vcb_kind = "angle"
    vcb_label = "Angle"
    is_pie = False


class SKETCHUP_OT_tool_pie(_ArcBase):
    bl_idname = "sketchup.tool_pie"
    bl_label = "Pie"
    bl_description = "SketchUp Pie tool."
    vcb_kind = "angle"
    vcb_label = "Angle"
    is_pie = True


# ---------------------------------------------------------------------------
# 2-Point Arc (A).
# ---------------------------------------------------------------------------


class SKETCHUP_OT_tool_arc_2_point(ShapeToolBase):
    bl_idname = "sketchup.tool_arc_2_point"
    bl_label = "2-Point Arc"
    bl_description = "SketchUp 2-Point Arc tool."
    vcb_kind = "length"
    vcb_label = "Bulge"

    def on_setup(self, context, event):
        super_setup(self, context, event)
        self.state = "WAIT_START"
        self.chord_start = None
        self.chord_end = None
        self.bulge = 0.0
        self.segments = curve_mod.DEFAULT_ARC_SEGMENTS
        self.last_arc = None

    def resolve_vcb_kind(self, text):
        stripped = text.strip().lower()
        if stripped.endswith("s"):
            return "count"
        if stripped.endswith("r"):
            return None  # Raw: radius input, e.g. "500R".
        return "length"

    def on_left_press(self, context, event):
        if self.state == "WAIT_START":
            self._fix_plane(context, event)
            self.chord_start = self._plane_point(self.current_point)
            self.state = "WAIT_END"
            self.session.vcb.clear()
        elif self.state == "WAIT_END":
            self.chord_end = self._plane_point(self.current_point)
            self.state = "WAIT_BULGE"
        else:
            self._commit_2point(context)
            self.state = "WAIT_START"
            self.chord_start = None
            self.chord_end = None

    def on_shape_move(self, context, event):
        if self.state == "WAIT_END" and self.chord_start is not None:
            point = self._plane_point(self.current_point)
            self.overlay.set_lines([(self.chord_start, point, (1.0, 1.0, 1.0, 1.0), False)])
        elif self.state == "WAIT_BULGE":
            point = self._plane_point(self.current_point)
            self.bulge = self._bulge_from_point(point)
            points = self._arc_points()
            if points:
                self._set_preview(points, closed=False)

    def _bulge_from_point(self, point):
        # Signed distance from the chord line to the cursor point,
        # measured along perp = normal x chord (screen-up side for a
        # ground-plane chord drawn left to right).
        chord = tuple(b - a for a, b in zip(self.chord_start, self.chord_end))
        chord_len = math.sqrt(sum(c * c for c in chord))
        if chord_len < 1e-9:
            return 0.0
        to_point = tuple(p - a for p, a in zip(point, self.chord_start))
        normal = self.plane_normal
        perp = (
            normal[1] * chord[2] - normal[2] * chord[1],
            normal[2] * chord[0] - normal[0] * chord[2],
            normal[0] * chord[1] - normal[1] * chord[0],
        )
        perp_len = math.sqrt(sum(c * c for c in perp))
        if perp_len < 1e-9:
            return 0.0
        return sum(t * p for t, p in zip(to_point, perp)) / perp_len

    def _arc_points(self):
        chord_len = _distance(self.chord_start, self.chord_end)
        radius = curve_mod.arc_bulge_to_radius(chord_len, abs(self.bulge))
        if radius is None:
            return [self.chord_start, self.chord_end]
        mid = tuple((a + b) / 2.0 for a, b in zip(self.chord_start, self.chord_end))
        normal = self.plane_normal
        chord = tuple(b - a for a, b in zip(self.chord_start, self.chord_end))
        perp = (
            normal[1] * chord[2] - normal[2] * chord[1],
            normal[2] * chord[0] - normal[0] * chord[2],
            normal[0] * chord[1] - normal[1] * chord[0],
        )
        perp_len = math.sqrt(sum(c * c for c in perp))
        perp = tuple(p / perp_len for p in perp)
        # Center is on the opposite side of the bulge.
        sign = 1.0 if self.bulge >= 0 else -1.0
        dist = radius - abs(self.bulge)
        center = tuple(m - sign * dist * p for m, p in zip(mid, perp))
        start_angle = curve_mod.angle_in_plane(self.chord_start, center, normal)
        end_angle = curve_mod.angle_in_plane(self.chord_end, center, normal)
        points = curve_mod.arc_points(center, normal, radius, start_angle, end_angle, self.segments)
        # arc_points always runs counter-clockwise; reverse when the
        # CCW arc's midpoint lands on the wrong side of the chord.
        mid_point = points[len(points) // 2]
        to_mid = tuple(m - c for m, c in zip(mid_point, mid))
        apex_dir = tuple(self.bulge * p for p in perp)
        if sum(t * a for t, a in zip(to_mid, apex_dir)) < 0:
            points = curve_mod.arc_points(
                center, normal, radius, end_angle, start_angle, self.segments
            )[::-1]
        return points

    def _commit_2point(self, context):
        points = self._arc_points()
        chord_len = _distance(self.chord_start, self.chord_end)
        radius = curve_mod.arc_bulge_to_radius(chord_len, abs(self.bulge)) or 0.0
        record = {
            "type": "arc",
            "center": [0.0, 0.0, 0.0],
            "radius": radius,
            "segments": self.segments,
            "normal": list(self.plane_normal),
            "start_angle": 0.0,
            "end_angle": 0.0,
            "closed": False,
        }
        curve_id = self._commit_polyline(context, points, False, record)
        self.last_arc = (self.chord_start, self.chord_end, self.bulge, self.segments, self.plane_origin, self.plane_normal, curve_id)
        undo_push("SketchUp Shape")

    def on_vcb_commit(self, context, value, kind):
        if kind is None and isinstance(value, str):
            # Radius input: convert to bulge, then commit/redraw.
            stripped = value.strip().lower()
            if not stripped.endswith("r"):
                return
            try:
                from ..core.vcb import parse_length

                radius = parse_length(stripped[:-1], self._default_unit(context))
            except ValueError:
                return
            chord = self.chord_start, self.chord_end
            if self.state != "WAIT_BULGE" and self.last_arc is not None:
                chord = self.last_arc[0], self.last_arc[1]
            if chord[0] is None or chord[1] is None:
                return
            bulge = curve_mod.arc_radius_to_bulge(_distance(chord[0], chord[1]), radius)
            if bulge is None:
                return
            value, kind = bulge, "length"
        if kind == "count" and isinstance(value, int):
            self.segments = max(1, value)
            return
        if kind == "length" and isinstance(value, float):
            if self.state == "WAIT_BULGE":
                self.bulge = value
                self._commit_2point(context)
                self.state = "WAIT_START"
                self.chord_start = None
                self.chord_end = None
            elif self.last_arc is not None:
                start, end, _b, segments, origin, normal, curve_id = self.last_arc
                self._delete_curve_edges(context, curve_id)
                self.plane_origin, self.plane_normal = origin, normal
                self.chord_start, self.chord_end, self.bulge, self.segments = start, end, value, segments
                self._commit_2point(context)
                self.state = "WAIT_START"
                self.chord_start = None
                self.chord_end = None

    def vcb_display_value(self, context):
        if self.state == "WAIT_BULGE":
            from ..core.units import format_length

            return format_length(abs(self.bulge), self._default_unit(context), precision=2)
        return ""

    def on_escape(self, context, event):
        if self.state in ("WAIT_END", "WAIT_BULGE"):
            self.state = "WAIT_START"
            self.chord_start = None
            self.chord_end = None
            self.overlay.set_lines([])
            return {"RUNNING_MODAL"}
        return None


# ---------------------------------------------------------------------------
# 3-Point Arc.
# ---------------------------------------------------------------------------


class SKETCHUP_OT_tool_arc_3_point(ShapeToolBase):
    bl_idname = "sketchup.tool_arc_3_point"
    bl_label = "3-Point Arc"
    bl_description = "SketchUp 3-Point Arc tool."
    vcb_kind = None
    vcb_label = "Measurements"

    def on_setup(self, context, event):
        super_setup(self, context, event)
        self.state = "WAIT_P1"
        self.p1 = None
        self.p2 = None
        self.segments = curve_mod.DEFAULT_ARC_SEGMENTS

    def on_left_press(self, context, event):
        if self.state == "WAIT_P1":
            self._fix_plane(context, event)
            self.p1 = self._plane_point(self.current_point)
            self.state = "WAIT_P2"
        elif self.state == "WAIT_P2":
            self.p2 = self._plane_point(self.current_point)
            self.state = "WAIT_P3"
        else:
            p3 = self._plane_point(self.current_point)
            self._commit_3point(context, p3)
            self.state = "WAIT_P1"
            self.p1 = None
            self.p2 = None

    def on_shape_move(self, context, event):
        if self.state == "WAIT_P2" and self.p1 is not None:
            point = self._plane_point(self.current_point)
            self.overlay.set_lines([(self.p1, point, (1.0, 1.0, 1.0, 1.0), False)])
        elif self.state == "WAIT_P3" and self.p1 is not None and self.p2 is not None:
            point = self._plane_point(self.current_point)
            points = self._arc_through(point)
            if points:
                self._set_preview(points, closed=False)

    def _arc_through(self, p3):
        solved = curve_mod.arc_from_three_points(self.p1, self.p2, p3, self.plane_normal)
        if solved is None:
            return [self.p1, self.p2, p3]
        center, radius = solved
        start = curve_mod.angle_in_plane(self.p1, center, self.plane_normal)
        mid = curve_mod.angle_in_plane(self.p2, center, self.plane_normal)
        end = curve_mod.angle_in_plane(p3, center, self.plane_normal)
        # Choose the sweep direction that passes through p2.
        sweep_ccw = (end - start) % 360.0
        mid_ccw = (mid - start) % 360.0
        if mid_ccw <= sweep_ccw:
            return curve_mod.arc_points(center, self.plane_normal, radius, start, end, self.segments)
        return curve_mod.arc_points(center, self.plane_normal, radius, end, start, self.segments)[::-1]

    def _commit_3point(self, context, p3):
        solved = curve_mod.arc_from_three_points(self.p1, self.p2, p3, self.plane_normal)
        points = self._arc_through(p3)
        if solved is not None:
            center, radius = solved
        else:
            center, radius = (0.0, 0.0, 0.0), 0.0
        record = {
            "type": "arc",
            "center": list(center),
            "radius": radius,
            "segments": self.segments,
            "normal": list(self.plane_normal),
            "start_angle": 0.0,
            "end_angle": 0.0,
            "closed": False,
        }
        self._commit_polyline(context, points, False, record)
        undo_push("SketchUp Shape")

    def on_escape(self, context, event):
        if self.state in ("WAIT_P2", "WAIT_P3"):
            self.state = "WAIT_P1"
            self.p1 = None
            self.p2 = None
            self.overlay.set_lines([])
            return {"RUNNING_MODAL"}
        return None


# ---------------------------------------------------------------------------
# Rotated Rectangle.
# ---------------------------------------------------------------------------


class SKETCHUP_OT_tool_rotated_rectangle(ShapeToolBase):
    bl_idname = "sketchup.tool_rotated_rectangle"
    bl_label = "Rotated Rectangle"
    bl_description = "SketchUp Rotated Rectangle tool."
    vcb_kind = "length_list"
    vcb_label = "Dimensions"

    def on_setup(self, context, event):
        super_setup(self, context, event)
        self.state = "WAIT_P1"
        self.p1 = None
        self.p2 = None
        self.p3 = None

    def resolve_vcb_kind(self, text):
        # After two corners, VCB takes "width,angle" (QRC format):
        # raw text, parsed by on_vcb_commit itself.
        if self.state == "WAIT_P3":
            return None
        return self.vcb_kind

    def on_left_press(self, context, event):
        if self.state == "WAIT_P1":
            self._fix_plane(context, event)
            self.p1 = self._plane_point(self.current_point)
            self.state = "WAIT_P2"
            self.session.vcb.clear()
        elif self.state == "WAIT_P2":
            self.p2 = self._plane_point(self.current_point)
            self.state = "WAIT_P3"
        else:
            self.p3 = self._plane_point(self.current_point)
            self._commit_rotated(context)
            self.state = "WAIT_P1"
            self.p1 = None
            self.p2 = None
            self.p3 = None

    def on_shape_move(self, context, event):
        if self.state == "WAIT_P2" and self.p1 is not None:
            point = self._plane_point(self.current_point)
            self.overlay.set_lines([(self.p1, point, (1.0, 1.0, 1.0, 1.0), False)])
        elif self.state == "WAIT_P3":
            point = self._plane_point(self.current_point)
            points = self._rotated_points(point)
            if points:
                self._set_preview(points, closed=True)

    def _rotated_points(self, p3):
        # p1->p2 is the first edge; p3 sets the perpendicular extent.
        edge = tuple(b - a for a, b in zip(self.p1, self.p2))
        edge_len = math.sqrt(sum(c * c for c in edge))
        if edge_len < 1e-9:
            return []
        edge_dir = tuple(c / edge_len for c in edge)
        to_p3 = tuple(p - a for p, a in zip(p3, self.p1))
        along = sum(t * d for t, d in zip(to_p3, edge_dir))
        # Perpendicular component in the plane.
        perp_vec = tuple(t - along * d for t, d in zip(to_p3, edge_dir))
        p4 = tuple(a + p for a, p in zip(self.p1, perp_vec))
        p3_corner = tuple(b + p for b, p in zip(self.p2, perp_vec))
        return [self.p1, self.p2, p3_corner, p4]

    def _commit_rotated(self, context):
        points = self._rotated_points(self.p3)
        if not points:
            return
        record = {
            "type": "rectangle",
            "center": [sum(p[i] for p in points) / 4.0 for i in range(3)],
            "radius": 0.0,
            "segments": 4,
            "normal": list(self.plane_normal),
            "start_angle": 0.0,
            "end_angle": 0.0,
            "closed": True,
        }
        self._commit_polyline(context, points, True, record)
        undo_push("SketchUp Shape")

    def on_vcb_commit(self, context, value, kind):
        if kind is None and isinstance(value, str) and self.state == "WAIT_P3":
            # Raw "width,angle" text.
            from ..core.vcb import parse_length

            parts = [part.strip() for part in value.replace(";", ",").split(",")]
            if len(parts) >= 2:
                try:
                    width = parse_length(parts[0], self._default_unit(context))
                    angle = float(parts[1])
                except (ValueError, TypeError):
                    return
                edge = tuple(b - a for a, b in zip(self.p1, self.p2))
                edge_len = math.sqrt(sum(c * c for c in edge))
                if edge_len < 1e-9:
                    return
                edge_dir = tuple(c / edge_len for c in edge)
                # Rotate the edge direction by `angle` in the plane,
                # then step `width` along it from p2.
                normal = self.plane_normal
                cos_a = math.cos(math.radians(angle))
                sin_a = math.sin(math.radians(angle))
                rot = (
                    edge_dir[0] * cos_a + (normal[1] * edge_dir[2] - normal[2] * edge_dir[1]) * sin_a,
                    edge_dir[1] * cos_a + (normal[2] * edge_dir[0] - normal[0] * edge_dir[2]) * sin_a,
                    edge_dir[2] * cos_a + (normal[0] * edge_dir[1] - normal[1] * edge_dir[0]) * sin_a,
                )
                self.p3 = tuple(b + width * r for b, r in zip(self.p2, rot))
                self._commit_rotated(context)
                self.state = "WAIT_P1"
                self.p1 = None
                self.p2 = None
                self.p3 = None
        elif isinstance(value, list) and self.state == "WAIT_P2":
            # Length input for the first edge (QRC: width after 2 clicks
            # is handled above; a bare length here sets edge length).
            pass

    def on_escape(self, context, event):
        if self.state in ("WAIT_P2", "WAIT_P3"):
            self.state = "WAIT_P1"
            self.p1 = None
            self.p2 = None
            self.p3 = None
            self.overlay.set_lines([])
            return {"RUNNING_MODAL"}
        return None


# ---------------------------------------------------------------------------
# Freehand.
# ---------------------------------------------------------------------------


class SKETCHUP_OT_tool_freehand(ShapeToolBase):
    bl_idname = "sketchup.tool_freehand"
    bl_label = "Freehand"
    bl_description = "SketchUp Freehand tool."
    vcb_kind = None
    vcb_label = "Measurements"

    def on_setup(self, context, event):
        super_setup(self, context, event)
        self.drawing = False
        self.points = []
        self.min_spacing = 0.002  # 2 mm between kept points.

    def on_left_press(self, context, event):
        self._fix_plane(context, event)
        self.drawing = True
        self.points = [self._plane_point(self.current_point)]

    def on_shape_move(self, context, event):
        if self.drawing:
            point = self._plane_point(self.current_point)
            if _distance(self.points[-1], point) >= self.min_spacing:
                self.points.append(point)
            self._set_preview(self.points, closed=False)

    def on_left_release(self, context, event):
        if self.drawing:
            self.drawing = False
            point = self._plane_point(self.current_point)
            if _distance(self.points[-1], point) >= 1e-6:
                self.points.append(point)
            if len(self.points) >= 2:
                record = {
                    "type": "freehand",
                    "center": [0.0, 0.0, 0.0],
                    "radius": 0.0,
                    "segments": len(self.points) - 1,
                    "normal": list(self.plane_normal),
                    "start_angle": 0.0,
                    "end_angle": 0.0,
                    "closed": False,
                }
                self._commit_polyline(context, self.points, False, record)
                undo_push("SketchUp Shape")
            self.overlay.set_lines([])
            self.points = []

    def on_escape(self, context, event):
        if self.drawing:
            self.drawing = False
            self.points = []
            self.overlay.set_lines([])
            return {"RUNNING_MODAL"}
        return None


SHAPE_OPERATORS = [
    SKETCHUP_OT_tool_rectangle,
    SKETCHUP_OT_tool_rotated_rectangle,
    SKETCHUP_OT_tool_circle,
    SKETCHUP_OT_tool_polygon,
    SKETCHUP_OT_tool_arc,
    SKETCHUP_OT_tool_arc_2_point,
    SKETCHUP_OT_tool_arc_3_point,
    SKETCHUP_OT_tool_pie,
    SKETCHUP_OT_tool_freehand,
]
