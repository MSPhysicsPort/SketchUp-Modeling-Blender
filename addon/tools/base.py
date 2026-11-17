"""Shared modal-operator base for SketchUp tools (proposal §5.3).

Conventions enforced here, so every tool behaves the same way:
- Left-click confirms / advances, Right-click or Esc cancels the
  current step (D5: in-progress right-click = cancel, not a menu).
- Middle-mouse / wheel navigation passes through to Blender.
- Typing goes to the VCB buffer; Enter commits, Backspace edits.
- Arrow keys / Shift drive the inference lock state machine.
- Preview drawing is draw-only; geometry changes only on commit,
  each commit pushing one Undo step.
- Overlay handlers and session state are always cleaned up on exit.

Subclasses implement hooks: on_setup, on_mouse_move, on_left_press,
on_left_release, on_escape, on_vcb_commit, vcb_display_value,
_lock_anchor, resolve_vcb_kind. Hooks return None to continue or a
result set ({'FINISHED'} / {'CANCELLED'}) to end the modal loop.
"""

import time

import bpy
from bpy_extras.view3d_utils import (
    location_3d_to_region_2d,
    region_2d_to_origin_3d,
    region_2d_to_vector_3d,
)
from mathutils import Vector

from ..context import EditContext, undo_push
from ..core import inference as inference_mod
from ..core.inference import LockState, evaluate, find_intersections
from ..core.state import get_session
from ..draw.overlay import Overlay
from ..i18n.translations import translate as _T
from ..session_props import set_active_tool, set_vcb_text
from . import switching

NAVIGATION_TYPES = {
    "MIDDLEMOUSE",
    "WHEELUPMOUSE",
    "WHEELDOWNMOUSE",
    "WHEELINMOUSE",
    "WHEELOUTMOUSE",
}

PIXEL_TOLERANCE = 12.0
HOVER_DWELL_SECONDS = 0.35


class _EventShim:
    """Stand-in event when an operator is invoked without one.

    Timer-deferred invokes (tool switching, deferred commits) call
    the operator through ``bpy.ops`` with no event; tools only need
    a mouse position to start, so the region center stands in.
    """

    def __init__(self, context):
        region = getattr(context, "region", None)
        if region is not None:
            self.mouse_region_x = region.width // 2
            self.mouse_region_y = region.height // 2
        else:
            self.mouse_region_x = 0
            self.mouse_region_y = 0
        self.type = "NONE"
        self.value = "NOTHING"
        self.ascii = ""
        self.shift = False
        self.ctrl = False
        self.alt = False
        self.oskey = False
        self.mouse_x = self.mouse_region_x
        self.mouse_y = self.mouse_region_y


def _hook_result(result):
    """Coerce a hook return into a modal result set or None.

    Hooks must return None (continue with the default) or a result
    set. A stray bool (the pre-0.5.0 on_escape convention) is
    coerced: True = stay in the tool, False = default action. This
    keeps one wrong hook from crashing the modal loop with
    "incompatible return value".
    """
    if isinstance(result, set):
        return result
    if result is True:
        return {"RUNNING_MODAL"}
    return None


class SketchUpToolBase(bpy.types.Operator):
    bl_options = {"REGISTER"}

    # Subclasses set these.
    vcb_kind = None  # e.g. "length"; None = no VCB input for this tool.
    vcb_label = "Measurements"

    # -- poll / invoke ---------------------------------------------------

    @classmethod
    def poll(cls, context):
        # Headless/scripted contexts have no area; allow them so
        # execute() stays testable (T2). GUI use requires a 3D View.
        return context.area is None or context.area.type == "VIEW_3D"

    def invoke(self, context, event):
        if event is None:
            event = _EventShim(context)
        self._setup(context, event)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _setup(self, context, event):
        self.edit_context = EditContext(context)
        self.session = get_session()
        self.session.active_tool_id = self.bl_idname
        self.session.vcb.clear()
        self.session.lock.clear()
        self.session.lock.line_mode = inference_mod.LINE_MODE_ALL_ON
        self.session.from_point = None
        self.overlay = Overlay()
        self.overlay.attach(context)
        self._mouse = (event.mouse_region_x, event.mouse_region_y)
        self._last_move_time = time.monotonic()
        self._current_inference = None
        self._shift_held = False
        self._button_held = False
        self._finished = False
        set_active_tool(context, self.bl_idname)
        self._set_cursor(context)
        self.on_setup(context, event)
        self._update_vcb_display(context)
        self._redraw(context)

    # -- modal dispatch --------------------------------------------------

    def modal(self, context, event):
        try:
            return self._modal_inner(context, event)
        except Exception as exc:
            # A tool error must never leak the overlay handler or
            # leave the session dirty: clean up and end the tool.
            print("SketchUp tool error in %s: %r" % (self.bl_idname, exc))
            import traceback

            traceback.print_exc()
            return self._finish(context)

    def _modal_inner(self, context, event):
        if event.type in NAVIGATION_TYPES:
            return {"PASS_THROUGH"}
        if event.type in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
            self._on_mouse_move(context, event)
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE":
            if event.value == "PRESS":
                self._button_held = True
                result = _hook_result(self.on_left_press(context, event))
                self._after_action(context)
                return result or {"RUNNING_MODAL"}
            if event.value == "RELEASE":
                self._button_held = False
                result = _hook_result(self.on_left_release(context, event))
                self._after_action(context)
                return result or {"RUNNING_MODAL"}
            return {"RUNNING_MODAL"}
        if event.type == "RIGHTMOUSE" and event.value == "PRESS":
            return self._finish(context)
        if event.type == "ESC" and event.value == "PRESS":
            result = _hook_result(self.on_escape(context, event))
            if result is not None:
                return result
            return self._finish(context)
        if event.type in {"RET", "NUMPAD_ENTER"} and event.value == "PRESS":
            return self._on_vcb_commit(context, event)
        if event.type == "BACK_SPACE" and event.value == "PRESS":
            self.session.vcb.backspace()
            self._update_vcb_display(context)
            self._redraw(context)
            return {"RUNNING_MODAL"}
        if event.type in {"LEFT_SHIFT", "RIGHT_SHIFT"}:
            if event.value == "PRESS":
                self._on_shift_press(context, event)
            elif event.value == "RELEASE":
                self._on_shift_release(context, event)
            return {"RUNNING_MODAL"}
        if event.type in {"LEFT_ALT", "RIGHT_ALT"} and event.value == "PRESS":
            self.on_alt_press(context, event)
            self._update_vcb_display(context)
            self._redraw(context)
            return {"RUNNING_MODAL"}
        if event.type in {"UP_ARROW", "DOWN_ARROW", "LEFT_ARROW", "RIGHT_ARROW"}:
            if event.value == "PRESS":
                self._on_arrow(context, event)
            return {"RUNNING_MODAL"}
        # Direct tool switching (no Esc needed): another tool's
        # shortcut ends this tool and starts that one. Only with an
        # empty VCB buffer — a letter after digits is VCB input.
        target = switching.switch_target(
            event, self.bl_idname, self.session.vcb.is_empty
        )
        if target is not None:
            switching.request_switch(target)
            return self._finish(context)
        if event.value == "PRESS" and self.vcb_kind is not None:
            char = event.ascii
            if char and char.isprintable() and not event.ctrl and not event.oskey:
                self.session.vcb.feed(char)
                self._update_vcb_display(context)
                self._redraw(context)
            return {"RUNNING_MODAL"}
        return {"RUNNING_MODAL"}

    def _after_action(self, context):
        self._update_vcb_display(context)
        self._redraw(context)

    # -- mouse / hover ---------------------------------------------------

    def _on_mouse_move(self, context, event):
        now = time.monotonic()
        x, y = event.mouse_region_x, event.mouse_region_y
        moved = ((x - self._mouse[0]) ** 2 + (y - self._mouse[1]) ** 2) ** 0.5
        if moved > 2.0:
            self._last_move_time = now
            self._mouse = (x, y)
        elif (
            now - self._last_move_time > HOVER_DWELL_SECONDS
            and self._current_inference is not None
        ):
            # Hover encouragement: dwell on a point to prefer it.
            self.session.from_point = tuple(self._current_inference.point)
        self.on_mouse_move(context, event)
        self._update_vcb_display(context)
        self._redraw(context)

    # -- inference -------------------------------------------------------

    def compute_inference(self, context, event, start_point=None):
        """Run the inference engine for the current mouse position."""
        region = context.region
        rv3d = getattr(context.space_data, "region_3d", None)
        if region is None or rv3d is None:
            return None
        x, y = event.mouse_region_x, event.mouse_region_y
        try:
            ray_origin = region_2d_to_origin_3d(region, rv3d, (x, y))
            ray_dir = region_2d_to_vector_3d(region, rv3d, (x, y))
        except Exception:
            return None
        bm = self.edit_context.begin()
        try:
            points, edges = self._build_candidates(region, rv3d, bm)
            face_hit = self.edit_context.ray_cast_face(bm, ray_origin, ray_dir)
        finally:
            self.edit_context.abort(bm)
        for point in find_intersections(edges, (x, y), PIXEL_TOLERANCE):
            xy = self._project(region, rv3d, point)
            if xy is not None:
                points.append(("intersection", tuple(point), xy))
        guide_lines = self._build_guide_lines(region, rv3d)
        lock_tolerance = max(0.001, rv3d.view_distance * 0.002)
        result = evaluate(
            tuple(ray_origin),
            tuple(ray_dir),
            (x, y),
            points=points,
            edges=edges,
            face_hit=(
                (tuple(face_hit[0]), tuple(face_hit[1]), face_hit[2])
                if face_hit is not None
                else None
            ),
            guide_lines=guide_lines,
            start_point=start_point,
            from_point=self.session.from_point,
            lock=self.session.lock,
            axes=self.session.axes.as_axes(),
            pixel_tolerance=PIXEL_TOLERANCE,
            lock_tolerance=lock_tolerance,
        )
        self._current_inference = result
        return result

    def _project(self, region, rv3d, world_co):
        try:
            xy = location_3d_to_region_2d(region, rv3d, Vector(world_co))
        except Exception:
            return None
        if xy is None:
            return None
        return (xy.x, xy.y)

    def _build_candidates(self, region, rv3d, bm):
        matrix = self.edit_context.object.matrix_world
        points = []
        edges = []
        for vert in bm.verts:
            world = matrix @ vert.co
            xy = self._project(region, rv3d, world)
            if xy is not None:
                points.append(("endpoint", tuple(world), xy))
        for edge in bm.edges:
            w1 = matrix @ edge.verts[0].co
            w2 = matrix @ edge.verts[1].co
            xy1 = self._project(region, rv3d, w1)
            xy2 = self._project(region, rv3d, w2)
            if xy1 is not None and xy2 is not None:
                edges.append((tuple(w1), tuple(w2), xy1, xy2))
            mid = (w1 + w2) * 0.5
            xy_mid = self._project(region, rv3d, mid)
            if xy_mid is not None:
                points.append(("midpoint", tuple(mid), xy_mid))
        origin = tuple(self.session.axes.origin)
        xy = self._project(region, rv3d, origin)
        if xy is not None:
            points.append(("origin", origin, xy))
        for kind, point in self.session.guides.point_candidates():
            xy = self._project(region, rv3d, point)
            if xy is not None:
                points.append((kind, tuple(point), xy))
        # Curve centers (Circle/Polygon/Arc/Pie): Center inference.
        try:
            from ..core import curves as curve_mod

            for record in curve_mod.get_curves(self.edit_context.mesh).values():
                if record.get("type") in ("circle", "polygon", "arc", "pie"):
                    center = tuple(record["center"])
                    xy = self._project(region, rv3d, center)
                    if xy is not None:
                        points.append(("center", center, xy))
        except Exception:
            pass
        return points, edges

    def _build_guide_lines(self, region, rv3d):
        guide_lines = []
        for point, direction in self.session.guides.line_candidates():
            far_a = Vector(point) - Vector(direction) * 1000.0
            far_b = Vector(point) + Vector(direction) * 1000.0
            xy1 = self._project(region, rv3d, far_a)
            xy2 = self._project(region, rv3d, far_b)
            if xy1 is not None and xy2 is not None:
                guide_lines.append((tuple(point), tuple(direction), xy1, xy2))
        return guide_lines

    # -- picking ---------------------------------------------------------

    def pick_at(self, context, event, tolerance_px=8.0):
        """Pick the entity under the cursor.

        Returns ("vert", index, world_co), ("edge", (i, j), world_mid),
        ("face", index, world_co), or None. Priority: vertex > edge >
        face. Indices are edit-mesh indices at pick time; callers
        re-fetch by coordinates after edits.
        """
        region = context.region
        rv3d = getattr(context.space_data, "region_3d", None)
        if region is None or rv3d is None:
            return None
        x, y = event.mouse_region_x, event.mouse_region_y
        try:
            ray_origin = region_2d_to_origin_3d(region, rv3d, (x, y))
            ray_dir = region_2d_to_vector_3d(region, rv3d, (x, y))
        except Exception:
            return None
        bm = self.edit_context.begin()
        try:
            from ..core import geometry as geometry_mod

            geometry_mod.refresh(bm)
            matrix = self.edit_context.object.matrix_world
            best_vert = None
            for vert in bm.verts:
                world = matrix @ vert.co
                xy = self._project(region, rv3d, world)
                if xy is None:
                    continue
                dist = ((xy[0] - x) ** 2 + (xy[1] - y) ** 2) ** 0.5
                if dist <= tolerance_px and (
                    best_vert is None or dist < best_vert[0]
                ):
                    best_vert = (dist, vert.index, tuple(world))
            if best_vert is not None:
                return ("vert", best_vert[1], best_vert[2])
            best_edge = None
            for edge in bm.edges:
                w1 = matrix @ edge.verts[0].co
                w2 = matrix @ edge.verts[1].co
                xy1 = self._project(region, rv3d, w1)
                xy2 = self._project(region, rv3d, w2)
                if xy1 is None or xy2 is None:
                    continue
                dist = inference_mod.dist_point_to_segment_2d(
                    x, y, xy1[0], xy1[1], xy2[0], xy2[1]
                )
                if dist <= tolerance_px and (
                    best_edge is None or dist < best_edge[0]
                ):
                    mid = tuple((w1 + w2) * 0.5)
                    best_edge = (
                        dist,
                        (edge.verts[0].index, edge.verts[1].index),
                        mid,
                    )
            if best_edge is not None:
                return ("edge", best_edge[1], best_edge[2])
            face_hit = self.edit_context.ray_cast_face(bm, ray_origin, ray_dir)
            if face_hit is not None:
                return ("face", face_hit[2], tuple(face_hit[0]))
            return None
        finally:
            self.edit_context.abort(bm)

    # -- lock keys -------------------------------------------------------

    def _lock_anchor(self, context, event):
        """Anchor point for arrow/Shift locks; subclasses override."""
        if self._current_inference is not None:
            return tuple(self._current_inference.point)
        return None

    def _on_arrow(self, context, event):
        axis_map = {"RIGHT_ARROW": 0, "LEFT_ARROW": 1, "UP_ARROW": 2}
        if event.type in axis_map:
            anchor = self._lock_anchor(context, event)
            if anchor is not None:
                self.session.lock.press_arrow(axis_map[event.type], anchor)
        elif event.type == "DOWN_ARROW":
            # Magenta lock (parallel/perpendicular): P1 has no
            # parallel/perpendicular candidates, so DOWN toggles a
            # direction lock on the current inference direction.
            if self.session.lock.mode == "direction":
                self.session.lock.clear()
            else:
                self._on_shift_press(context, event)
        self._update_vcb_display(context)
        self._redraw(context)

    def _on_shift_press(self, context, event):
        anchor = self._lock_anchor(context, event)
        if anchor is None or self._current_inference is None:
            return
        current = tuple(self._current_inference.point)
        direction = (
            current[0] - anchor[0],
            current[1] - anchor[1],
            current[2] - anchor[2],
        )
        self.session.lock.press_shift(direction, anchor)
        self._shift_held = True

    def _on_shift_release(self, context, event):
        if self._shift_held:
            self.session.lock.release_shift()
            self._shift_held = False

    # -- VCB -------------------------------------------------------------

    def resolve_vcb_kind(self, text):
        return self.vcb_kind

    def _default_unit(self, context):
        try:
            addon_key = __package__.rsplit(".", 1)[0]
            addon = context.preferences.addons.get(addon_key)
            if addon is not None:
                return addon.preferences.default_unit
        except (AttributeError, ReferenceError):
            pass
        return "mm"

    def _on_vcb_commit(self, context, event):
        text = self.session.vcb.text
        if not text or self.vcb_kind is None:
            return {"RUNNING_MODAL"}
        kind = self.resolve_vcb_kind(text)
        if kind is None:
            # Raw-text VCB: the tool parses the buffer itself
            # (e.g. Rotated Rectangle "width,angle", Arc "20c").
            value = text
            self.session.vcb.clear()
            result = _hook_result(self.on_vcb_commit(context, value, None))
            self._update_vcb_display(context)
            self._redraw(context)
            return result or {"RUNNING_MODAL"}
        try:
            value = self.session.vcb.commit(kind, default_unit=self._default_unit(context))
        except ValueError as exc:
            self.report({"WARNING"}, _T("Invalid Measurements input: ") + str(exc))
            self._update_vcb_display(context)
            self._redraw(context)
            return {"RUNNING_MODAL"}
        result = _hook_result(self.on_vcb_commit(context, value, kind))
        self._update_vcb_display(context)
        self._redraw(context)
        return result or {"RUNNING_MODAL"}

    def vcb_display_value(self, context):
        """Formatted live value shown when the buffer is empty."""
        return ""

    def _update_vcb_display(self, context):
        if getattr(self, "overlay", None) is None:
            return
        buffer_text = self.session.vcb.text
        if buffer_text:
            display = buffer_text
        else:
            display = self.vcb_display_value(context)
        label = _T(self.vcb_label) if self.vcb_kind is not None else ""
        self.overlay.set_vcb(label, display)
        self.overlay.set_guides(
            self.session.guides.line_candidates(),
            [point for _kind, point in self.session.guides.point_candidates()],
        )
        set_vcb_text(context, display)

    # -- finish / cleanup ------------------------------------------------

    def _set_cursor(self, context):
        try:
            context.window.cursor_modal_set("CROSSHAIR")
        except Exception:
            pass

    def _restore_cursor(self, context):
        try:
            context.window.cursor_modal_restore()
        except Exception:
            pass

    def _redraw(self, context):
        try:
            if context.area is not None:
                context.area.tag_redraw()
        except (AttributeError, ReferenceError):
            pass

    def _finish(self, context):
        if self._finished:
            return {"FINISHED"}
        self._finished = True
        self.on_finish(context)
        if getattr(self, "overlay", None) is not None:
            self.overlay.detach()
        self.session.vcb.clear()
        self.session.lock.clear()
        self.session.from_point = None
        self.session.active_tool_id = None
        set_active_tool(context, "")
        set_vcb_text(context, "")
        self._restore_cursor(context)
        self._redraw(context)
        return {"FINISHED"}

    def __del__(self):
        overlay = getattr(self, "overlay", None)
        if overlay is not None and overlay.active:
            try:
                overlay.detach()
            except Exception:
                pass

    # -- hooks (subclasses override) --------------------------------------

    def on_setup(self, context, event):
        pass

    def on_mouse_move(self, context, event):
        pass

    def on_left_press(self, context, event):
        return None

    def on_left_release(self, context, event):
        return None

    def on_escape(self, context, event):
        return None

    def on_alt_press(self, context, event):
        pass

    def on_vcb_commit(self, context, value, kind):
        return None

    def on_finish(self, context):
        pass

    def execute(self, context):
        return {"FINISHED"}
