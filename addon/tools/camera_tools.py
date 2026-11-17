"""Camera tools (proposal §3.11, P6): Orbit / Pan / Zoom / Zoom
Window / Position Camera / Look Around / Walk, standard views,
Zoom Extents, view history, and two-point perspective (leveled
horizon approximation — Blender has no off-axis projection).
"""

import math

import bpy
from mathutils import Euler, Quaternion, Vector

from ..core.state import get_session
from ..i18n.translations import translate as _T

ORBIT_SPEED = 0.005
ZOOM_SPEED = 0.003


# ---------------------------------------------------------------------------
# Pure view math (headless-testable).
# ---------------------------------------------------------------------------


def orbit_rotation(rotation, dx, dy):
    """Orbit the view by pixel deltas: yaw about the view Y axis,
    pitch about the view X axis (view-local composition)."""
    yaw = Quaternion(Vector((0, 1, 0)), -dx * ORBIT_SPEED)
    pitch = Quaternion(Vector((1, 0, 0)), -dy * ORBIT_SPEED)
    return Quaternion(rotation) @ yaw @ pitch


def pan_offset(rotation, dx, dy, view_distance, region_height):
    """World offset for a pan drag (right/up in view space)."""
    scale = view_distance / max(region_height, 1) * 0.8
    right = Quaternion(rotation) @ Vector((1, 0, 0))
    up = Quaternion(rotation) @ Vector((0, 1, 0))
    return right * (-dx * scale) + up * (dy * scale)


def fit_distance(radius, fov_ratio=0.7):
    """View distance fitting a bounding sphere of ``radius``."""
    return radius / max(fov_ratio, 1e-6)


def iso_rotation():
    return Euler((math.radians(54.7356), 0.0, math.radians(45.0)), "XYZ").to_quaternion()


def level_rotation(rotation):
    """Remove roll and pitch: look horizontally, up stays world Z
    (two-point-perspective approximation)."""
    forward = Quaternion(rotation) @ Vector((0, 0, -1))
    forward.z = 0.0
    if forward.length < 1e-6:
        forward = Vector((0, -1, 0))
    forward.normalize()
    right = forward.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(forward).normalized()
    from mathutils import Matrix

    matrix = Matrix((right, up, -forward)).transposed().to_3x3()
    return matrix.to_quaternion()


def view_state(rv3d):
    return (
        tuple(rv3d.view_location),
        tuple(rv3d.view_rotation),
        rv3d.view_distance,
        rv3d.view_perspective,
    )


def apply_view_state(rv3d, state):
    location, rotation, distance, perspective = state
    rv3d.view_location = Vector(location)
    rv3d.view_rotation = Quaternion(rotation)
    rv3d.view_distance = distance
    try:
        rv3d.view_perspective = perspective
    except Exception:
        pass


def push_view_history(context):
    rv3d = getattr(context.space_data, "region_3d", None)
    if rv3d is None:
        return
    session = get_session()
    state = view_state(rv3d)
    if session.view_history and session.view_history[-1] == state:
        return
    session.view_history = session.view_history[: session.view_history_index + 1]
    session.view_history.append(state)
    session.view_history = session.view_history[-20:]
    session.view_history_index = len(session.view_history) - 1


# ---------------------------------------------------------------------------
# Modal navigation tools (plain Operators: no edit context needed).
# ---------------------------------------------------------------------------


class _CameraToolBase(bpy.types.Operator):
    bl_options = {"REGISTER", "GRAB_CURSOR", "BLOCKING"}

    def _rv3d(self, context):
        return getattr(context.space_data, "region_3d", None)

    def invoke(self, context, event):
        if self._rv3d(context) is None:
            return {"CANCELLED"}
        self._start_x = event.mouse_x
        self._start_y = event.mouse_y
        self._last_x = event.mouse_x
        self._last_y = event.mouse_y
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type in {"RIGHTMOUSE", "ESC"} and event.value == "PRESS":
            push_view_history(context)
            return {"FINISHED"}
        if event.type == "MOUSEMOVE":
            self._on_drag(context, event)
            self._last_x = event.mouse_x
            self._last_y = event.mouse_y
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            push_view_history(context)
            return {"FINISHED"}
        return {"RUNNING_MODAL"}

    def _on_drag(self, context, event):
        pass


class SKETCHUP_OT_tool_orbit(_CameraToolBase):
    bl_idname = "sketchup.tool_orbit"
    bl_label = "Orbit"
    bl_description = "Drag to orbit around the view center."

    def _on_drag(self, context, event):
        rv3d = self._rv3d(context)
        rv3d.view_rotation = orbit_rotation(
            rv3d.view_rotation,
            event.mouse_x - self._last_x,
            event.mouse_y - self._last_y,
        )


class SKETCHUP_OT_tool_pan(_CameraToolBase):
    bl_idname = "sketchup.tool_pan"
    bl_label = "Pan"
    bl_description = "Drag to pan the view."

    def _on_drag(self, context, event):
        rv3d = self._rv3d(context)
        region = context.region
        rv3d.view_location = rv3d.view_location + pan_offset(
            rv3d.view_rotation,
            event.mouse_x - self._last_x,
            event.mouse_y - self._last_y,
            rv3d.view_distance,
            region.height if region else 800,
        )


class SKETCHUP_OT_tool_zoom(_CameraToolBase):
    bl_idname = "sketchup.tool_zoom"
    bl_label = "Zoom"
    bl_description = "Drag up/down or scroll to zoom."

    def modal(self, context, event):
        if event.type == "WHEELUPMOUSE" and event.value == "PRESS":
            self._rv3d(context).view_distance *= 0.9
            return {"RUNNING_MODAL"}
        if event.type == "WHEELDOWNMOUSE" and event.value == "PRESS":
            self._rv3d(context).view_distance *= 1.1
            return {"RUNNING_MODAL"}
        return super().modal(context, event)

    def _on_drag(self, context, event):
        rv3d = self._rv3d(context)
        dy = event.mouse_y - self._last_y
        rv3d.view_distance *= math.exp(-dy * ZOOM_SPEED)


class SKETCHUP_OT_tool_zoom_window(_CameraToolBase):
    bl_idname = "sketchup.tool_zoom_window"
    bl_label = "Zoom Window"
    bl_description = "Drag a rectangle to zoom to it."

    def invoke(self, context, event):
        result = super().invoke(context, event)
        self._anchor = (event.mouse_region_x, event.mouse_region_y)
        return result

    def modal(self, context, event):
        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            self._fit(context, event)
            push_view_history(context)
            return {"FINISHED"}
        return super().modal(context, event)

    def _fit(self, context, event):
        rv3d = self._rv3d(context)
        region = context.region
        if region is None:
            return
        x1, y1 = self._anchor
        x2, y2 = event.mouse_region_x, event.mouse_region_y
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        if width < 5 or height < 5:
            return
        center_x = (x1 + x2) / 2.0 - region.width / 2.0
        center_y = (y1 + y2) / 2.0 - region.height / 2.0
        rv3d.view_location = rv3d.view_location + pan_offset(
            rv3d.view_rotation,
            -center_x,
            -center_y,
            rv3d.view_distance,
            region.height,
        )
        ratio = max(region.width / width, region.height / height)
        if rv3d.view_perspective == "ORTHO":
            rv3d.view_distance = rv3d.view_distance  # ortho: keep
            try:
                rv3d.view_camera_zoom = rv3d.view_camera_zoom
            except Exception:
                pass
        else:
            rv3d.view_distance /= ratio


class SKETCHUP_OT_tool_look_around(_CameraToolBase):
    bl_idname = "sketchup.tool_look_around"
    bl_label = "Look Around"
    bl_description = "Drag to look around from a fixed eye point."

    def _on_drag(self, context, event):
        rv3d = self._rv3d(context)
        old_rotation = Quaternion(rv3d.view_rotation)
        eye = rv3d.view_location - (old_rotation @ Vector((0, 0, -1))) * rv3d.view_distance
        new_rotation = orbit_rotation(
            old_rotation,
            event.mouse_x - self._last_x,
            event.mouse_y - self._last_y,
        )
        rv3d.view_rotation = new_rotation
        rv3d.view_location = eye + (new_rotation @ Vector((0, 0, -1))) * rv3d.view_distance


class SKETCHUP_OT_tool_position_camera(_CameraToolBase):
    bl_idname = "sketchup.tool_position_camera"
    bl_label = "Position Camera"
    bl_description = "Click to place the eye, drag to aim."

    EYE_HEIGHT = 1.7

    def invoke(self, context, event):
        result = super().invoke(context, event)
        self._eye = None
        return result

    def _ground_point(self, context, event):
        from bpy_extras.view3d_utils import (
            region_2d_to_origin_3d,
            region_2d_to_vector_3d,
        )
        from mathutils.geometry import intersect_line_plane

        region = context.region
        rv3d = self._rv3d(context)
        coord = (event.mouse_region_x, event.mouse_region_y)
        origin = region_2d_to_origin_3d(region, rv3d, coord)
        direction = region_2d_to_vector_3d(region, rv3d, coord)
        hit = intersect_line_plane(
            origin, origin + direction, Vector((0, 0, 0)), Vector((0, 0, 1))
        )
        return hit

    def modal(self, context, event):
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            point = self._ground_point(context, event)
            if point is not None:
                self._eye = point + Vector((0, 0, self.EYE_HEIGHT))
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            if self._eye is not None:
                push_view_history(context)
                return {"FINISHED"}
            return {"RUNNING_MODAL"}
        if event.type == "MOUSEMOVE" and self._eye is not None:
            target = self._ground_point(context, event)
            if target is not None and (target - self._eye).length > 1e-6:
                direction = (target - self._eye).normalized()
                rv3d = self._rv3d(context)
                rv3d.view_rotation = direction.to_track_quat("-Z", "Y")
                rv3d.view_location = Vector(target)
                rv3d.view_distance = (target - self._eye).length
            return {"RUNNING_MODAL"}
        return super().modal(context, event)


class SKETCHUP_OT_tool_walk(_CameraToolBase):
    bl_idname = "sketchup.tool_walk"
    bl_label = "Walk"
    bl_description = "Walk with W/A/S/D, drag to look around."

    STEP = 0.5

    def modal(self, context, event):
        if event.type in {"W", "S", "A", "D"} and event.value == "PRESS":
            rv3d = self._rv3d(context)
            forward = rv3d.view_rotation @ Vector((0, 0, -1))
            forward.z = 0.0
            if forward.length < 1e-6:
                forward = Vector((0, -1, 0))
            forward.normalize()
            right = rv3d.view_rotation @ Vector((1, 0, 0))
            right.z = 0.0
            right.normalize()
            step = self.STEP * (3.0 if event.shift else 1.0)
            if event.type == "W":
                rv3d.view_location = rv3d.view_location + forward * step
            elif event.type == "S":
                rv3d.view_location = rv3d.view_location - forward * step
            elif event.type == "A":
                rv3d.view_location = rv3d.view_location - right * step
            elif event.type == "D":
                rv3d.view_location = rv3d.view_location + right * step
            return {"RUNNING_MODAL"}
        return super().modal(context, event)

    def _on_drag(self, context, event):
        # Walk drags look around from the eye (like Look Around).
        rv3d = self._rv3d(context)
        old_rotation = Quaternion(rv3d.view_rotation)
        eye = rv3d.view_location - (old_rotation @ Vector((0, 0, -1))) * rv3d.view_distance
        new_rotation = orbit_rotation(
            old_rotation,
            event.mouse_x - self._last_x,
            event.mouse_y - self._last_y,
        )
        rv3d.view_rotation = new_rotation
        rv3d.view_location = eye + (new_rotation @ Vector((0, 0, -1))) * rv3d.view_distance


# ---------------------------------------------------------------------------
# One-shot view commands.
# ---------------------------------------------------------------------------


def _zoom_to_bounds(context, objects):
    rv3d = getattr(context.space_data, "region_3d", None)
    if rv3d is None:
        return False
    low = Vector((1e9, 1e9, 1e9))
    high = Vector((-1e9, -1e9, -1e9))
    found = False
    for obj in objects:
        if obj.type != "MESH":
            continue
        try:
            corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        except Exception:
            continue
        found = True
        for corner in corners:
            low = Vector(map(min, low, corner))
            high = Vector(map(max, high, corner))
    if not found:
        return False
    center = (low + high) * 0.5
    radius = max((high - low).length * 0.5, 0.1)
    rv3d.view_location = center
    rv3d.view_distance = fit_distance(radius)
    push_view_history(context)
    return True


class SKETCHUP_OT_zoom_extents(bpy.types.Operator):
    bl_idname = "sketchup.zoom_extents"
    bl_label = "Zoom Extents"
    bl_description = "Fit the whole model in the view"
    bl_options = {"REGISTER"}

    def execute(self, context):
        if _zoom_to_bounds(context, context.scene.objects):
            return {"FINISHED"}
        return {"CANCELLED"}


class SKETCHUP_OT_zoom_selection(bpy.types.Operator):
    bl_idname = "sketchup.zoom_selection"
    bl_label = "Zoom Selection"
    bl_description = "Fit the selection in the view"
    bl_options = {"REGISTER"}

    def execute(self, context):
        objects = list(context.selected_objects) or list(context.scene.objects)
        if _zoom_to_bounds(context, objects):
            return {"FINISHED"}
        return {"CANCELLED"}


def _make_view_operator(op_id, label, view_type):
    class ViewOperator(bpy.types.Operator):
        bl_idname = op_id
        bl_label = label
        bl_description = "Switch to the %s view" % label
        bl_options = {"REGISTER"}

        def execute(self, context):
            rv3d = getattr(context.space_data, "region_3d", None)
            if rv3d is None:
                return {"CANCELLED"}
            if view_type == "ISO":
                rv3d.view_rotation = iso_rotation()
            else:
                try:
                    bpy.ops.view3d.view_axis(type=view_type, align_active=True)
                except Exception:
                    return {"CANCELLED"}
            push_view_history(context)
            return {"FINISHED"}

    ViewOperator.__name__ = "SKETCHUP_OT_view_" + view_type.lower()
    return ViewOperator


SKETCHUP_OT_view_top = _make_view_operator("sketchup.view_top", "Top", "TOP")
SKETCHUP_OT_view_bottom = _make_view_operator("sketchup.view_bottom", "Bottom", "BOTTOM")
SKETCHUP_OT_view_front = _make_view_operator("sketchup.view_front", "Front", "FRONT")
SKETCHUP_OT_view_back = _make_view_operator("sketchup.view_back", "Back", "BACK")
SKETCHUP_OT_view_left = _make_view_operator("sketchup.view_left", "Left", "LEFT")
SKETCHUP_OT_view_right = _make_view_operator("sketchup.view_right", "Right", "RIGHT")
SKETCHUP_OT_view_iso = _make_view_operator("sketchup.view_iso", "Iso", "ISO")


class SKETCHUP_OT_view_previous(bpy.types.Operator):
    bl_idname = "sketchup.view_previous"
    bl_label = "Previous View"
    bl_description = "Go to the previous camera view"
    bl_options = {"REGISTER"}

    def execute(self, context):
        rv3d = getattr(context.space_data, "region_3d", None)
        session = get_session()
        if rv3d is None or session.view_history_index <= 0:
            return {"CANCELLED"}
        session.view_history_index -= 1
        apply_view_state(rv3d, session.view_history[session.view_history_index])
        return {"FINISHED"}


class SKETCHUP_OT_view_next(bpy.types.Operator):
    bl_idname = "sketchup.view_next"
    bl_label = "Next View"
    bl_description = "Go to the next camera view"
    bl_options = {"REGISTER"}

    def execute(self, context):
        rv3d = getattr(context.space_data, "region_3d", None)
        session = get_session()
        if rv3d is None or session.view_history_index >= len(session.view_history) - 1:
            return {"CANCELLED"}
        session.view_history_index += 1
        apply_view_state(rv3d, session.view_history[session.view_history_index])
        return {"FINISHED"}


class SKETCHUP_OT_parallel_projection(bpy.types.Operator):
    bl_idname = "sketchup.parallel_projection"
    bl_label = "Parallel Projection"
    bl_description = "Toggle parallel projection / perspective"
    bl_options = {"REGISTER"}

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("TOGGLE", "Toggle", ""),
            ("ORTHO", "Parallel Projection", ""),
            ("PERSP", "Perspective", ""),
        ],
        default="TOGGLE",
    )

    def execute(self, context):
        rv3d = getattr(context.space_data, "region_3d", None)
        if rv3d is None:
            return {"CANCELLED"}
        if self.mode == "TOGGLE":
            rv3d.view_perspective = (
                "ORTHO" if rv3d.view_perspective != "ORTHO" else "PERSP"
            )
        else:
            rv3d.view_perspective = self.mode
        push_view_history(context)
        return {"FINISHED"}


class SKETCHUP_OT_field_of_view(bpy.types.Operator):
    bl_idname = "sketchup.field_of_view"
    bl_label = "Field of View"
    bl_description = "Set the perspective field of view in degrees"
    bl_options = {"REGISTER"}

    angle: bpy.props.FloatProperty(
        name="Field of View",
        description="Vertical field of view in degrees",
        default=35.0,
        min=1.0,
        max=120.0,
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        rv3d = getattr(context.space_data, "region_3d", None)
        if rv3d is None:
            return {"CANCELLED"}
        rv3d.view_perspective = "PERSP"
        try:
            rv3d.lens = 16.0 / math.tan(math.radians(self.angle) / 2.0)
        except Exception:
            return {"CANCELLED"}
        push_view_history(context)
        return {"FINISHED"}


class SKETCHUP_OT_two_point_perspective(bpy.types.Operator):
    bl_idname = "sketchup.two_point_perspective"
    bl_label = "Two-Point Perspective"
    bl_description = "Level the horizon (two-point perspective approximation)"
    bl_options = {"REGISTER"}

    def execute(self, context):
        rv3d = getattr(context.space_data, "region_3d", None)
        if rv3d is None:
            return {"CANCELLED"}
        rv3d.view_perspective = "PERSP"
        rv3d.view_rotation = level_rotation(rv3d.view_rotation)
        push_view_history(context)
        self.report(
            {"INFO"},
            _T("Two-point perspective is approximated by leveling the horizon"),
        )
        return {"FINISHED"}


CAMERA_OPERATORS = [
    SKETCHUP_OT_tool_orbit,
    SKETCHUP_OT_tool_pan,
    SKETCHUP_OT_tool_zoom,
    SKETCHUP_OT_tool_zoom_window,
    SKETCHUP_OT_tool_look_around,
    SKETCHUP_OT_tool_position_camera,
    SKETCHUP_OT_tool_walk,
    SKETCHUP_OT_zoom_extents,
    SKETCHUP_OT_zoom_selection,
    SKETCHUP_OT_view_top,
    SKETCHUP_OT_view_bottom,
    SKETCHUP_OT_view_front,
    SKETCHUP_OT_view_back,
    SKETCHUP_OT_view_left,
    SKETCHUP_OT_view_right,
    SKETCHUP_OT_view_iso,
    SKETCHUP_OT_view_previous,
    SKETCHUP_OT_view_next,
    SKETCHUP_OT_parallel_projection,
    SKETCHUP_OT_field_of_view,
    SKETCHUP_OT_two_point_perspective,
]
