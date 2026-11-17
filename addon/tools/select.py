"""Select tool (research/01 §5.1.1): click to select, drag for a
selection box (right = fully inside, left = crossing), Shift toggles,
Ctrl adds, Ctrl+Shift subtracts. Double-click a face selects the face
plus its boundary edges; double-click an edge selects it plus its
connected faces; triple-click selects everything connected.
"""

import time

import bpy
from bpy_extras.view3d_utils import (
    location_3d_to_region_2d,
    region_2d_to_origin_3d,
    region_2d_to_vector_3d,
)
from mathutils import Vector

from ..core import containers, geometry as geometry_mod
from ..core.inference import segments_intersect_2d
from ..i18n.translations import translate as _T
from .base import SketchUpToolBase

DOUBLE_CLICK_SECONDS = 0.4
DRAG_THRESHOLD_PX = 5.0


class SKETCHUP_OT_tool_select(SketchUpToolBase):
    bl_idname = "sketchup.tool_select"
    bl_label = "Select"
    bl_description = "SketchUp Select tool: click, box-select, double/triple-click."

    vcb_kind = None

    def on_setup(self, context, event):
        self.press_xy = None
        self.press_time = 0.0
        self.press_mods = (False, False)
        self.dragging = False
        self.last_click = None  # (time, xy, key, count)

    # -- mouse -----------------------------------------------------------

    def on_left_press(self, context, event):
        self.press_xy = (event.mouse_region_x, event.mouse_region_y)
        self.press_time = time.monotonic()
        self.press_mods = (event.shift, event.ctrl)
        self.dragging = False
        return None

    def on_mouse_move(self, context, event):
        if not self._button_held or self.press_xy is None:
            return
        x, y = event.mouse_region_x, event.mouse_region_y
        if not self.dragging:
            dist = ((x - self.press_xy[0]) ** 2 + (y - self.press_xy[1]) ** 2) ** 0.5
            if dist < DRAG_THRESHOLD_PX:
                return
            self.dragging = True
        x1, y1 = self.press_xy
        crossing = x < x1
        color = (0.2, 0.8, 0.4, 1.0) if crossing else (0.2, 0.5, 1.0, 1.0)
        self.overlay.set_box_rect(
            (min(x1, x), min(y1, y), max(x1, x), max(y1, y), color, crossing)
        )

    def on_left_release(self, context, event):
        if self.dragging:
            self.dragging = False
            self.overlay.set_box_rect(None)
            self._apply_box_select(context, event)
            return None
        if self.press_xy is None:
            return None
        return self._apply_click(context, event)

    # -- container picking (other objects in the scene) -------------------

    def _pick_container(self, context, event):
        """Raycast the whole scene for a container object under the
        cursor (groups/components live outside the edit context)."""
        region = context.region
        rv3d = getattr(context.space_data, "region_3d", None)
        if region is None or rv3d is None:
            return None
        try:
            origin = region_2d_to_origin_3d(
                region, rv3d, (event.mouse_region_x, event.mouse_region_y)
            )
            direction = region_2d_to_vector_3d(
                region, rv3d, (event.mouse_region_x, event.mouse_region_y)
            )
            depsgraph = context.evaluated_depsgraph_get()
            hit, _loc, _normal, _index, obj, _matrix = context.scene.ray_cast(
                depsgraph, origin, direction
            )
        except Exception:
            return None
        if hit and obj is not None and obj is not self.edit_context.object:
            if containers.is_container(obj):
                return obj
        return None

    # -- click selection ---------------------------------------------------

    def _apply_click(self, context, event):
        pick = self.pick_at(context, event)
        container = None
        if pick is not None:
            key = (pick[0], pick[1])
        else:
            container = self._pick_container(context, event)
            key = ("container", container.name) if container is not None else None
        shift, ctrl = self.press_mods
        now = time.monotonic()
        x, y = event.mouse_region_x, event.mouse_region_y
        count = 1
        if self.last_click is not None:
            last_time, last_xy, last_key, last_count = self.last_click
            dist = ((x - last_xy[0]) ** 2 + (y - last_xy[1]) ** 2) ** 0.5
            if (
                key is not None
                and key == last_key
                and not shift
                and not ctrl
                and now - last_time < DOUBLE_CLICK_SECONDS
                and dist < 5.0
            ):
                count = last_count + 1
        self.last_click = (now, (x, y), key, count)
        if pick is None:
            return self._apply_empty_click(
                context, event, shift, ctrl, count, container
            )
        bm = self.edit_context.begin()
        try:
            geometry_mod.refresh(bm)
            kind, index, _co = pick
            if count >= 3:
                self._select_connected(bm, kind, index)
            elif count == 2:
                self._select_double_click(bm, kind, index)
            else:
                targets = self._expand_surface(bm, kind, index)
                self._apply_mode(bm, targets, shift, ctrl)
        finally:
            self.edit_context.commit(bm)
        return None

    def _apply_empty_click(self, context, event, shift, ctrl, count, container):
        """No context geometry under the cursor: maybe a container,
        maybe empty space (which closes one context level)."""
        if container is not None and not shift and not ctrl:
            if count >= 2:
                if containers.is_locked(container):
                    self.report({"WARNING"}, _T("This group/component is locked"))
                    return None
                containers.request_enter_context(container.name)
                return {"FINISHED"}
            self.session.selected_container = container.name
            self.report(
                {"INFO"},
                _T("Selected %s (double-click to edit)") % container.name,
            )
            return None
        if container is None and not shift and not ctrl:
            if len(containers.context_stack()) > 1:
                # Clicking outside the edited container closes it.
                containers.request_close_context()
                return {"FINISHED"}
            bm = self.edit_context.begin()
            try:
                self._clear_all(bm)
            finally:
                self.edit_context.commit(bm)
        return None

    def _expand_surface(self, bm, kind, index):
        """A face click selects its whole Surface (soft-edge flood);
        other elements select as-is."""
        if kind != "face":
            return [(kind, index)]
        face = bm.faces[index]
        return [("face", i) for i in geometry_mod.flood_surface_faces(bm, face)]

    def _clear_all(self, bm):
        for vert in bm.verts:
            vert.select = False
        for edge in bm.edges:
            edge.select = False
        for face in bm.faces:
            face.select = False

    def _set_element(self, bm, kind, index, value):
        if kind == "vert":
            vert = bm.verts[index]
            vert.select = value
        elif kind == "edge":
            edge = bm.edges[index]
            edge.select = value
            for vert in edge.verts:
                vert.select = value
        elif kind == "face":
            face = bm.faces[index]
            face.select = value
            for edge in face.edges:
                edge.select = value
            for vert in face.verts:
                vert.select = value

    def _apply_mode(self, bm, targets, shift, ctrl):
        if shift and ctrl:
            for kind, index in targets:
                self._set_element(bm, kind, index, False)
        elif shift:
            for kind, index in targets:
                current = self._is_selected(bm, kind, index)
                self._set_element(bm, kind, index, not current)
        elif ctrl:
            for kind, index in targets:
                self._set_element(bm, kind, index, True)
        else:
            self._clear_all(bm)
            for kind, index in targets:
                self._set_element(bm, kind, index, True)

    def _is_selected(self, bm, kind, index):
        if kind == "vert":
            return bm.verts[index].select
        if kind == "edge":
            return bm.edges[index].select
        return bm.faces[index].select

    def _select_double_click(self, bm, kind, index):
        self._clear_all(bm)
        if kind == "face":
            self._set_element(bm, "face", index, True)
        elif kind == "edge":
            self._set_element(bm, "edge", index, True)
            for face in bm.edges[index].link_faces:
                self._set_element(bm, "face", face.index, True)
        elif kind == "vert":
            self._set_element(bm, "vert", index, True)
            for edge in bm.verts[index].link_edges:
                self._set_element(bm, "edge", edge.index, True)
            for face in bm.verts[index].link_faces:
                self._set_element(bm, "face", face.index, True)

    def _select_connected(self, bm, kind, index):
        self._clear_all(bm)
        if kind == "vert":
            seed_verts = {index}
        elif kind == "edge":
            seed_verts = {v.index for v in bm.edges[index].verts}
        else:
            seed_verts = {v.index for v in bm.faces[index].verts}
        seen = set(seed_verts)
        stack = list(seed_verts)
        while stack:
            vert_index = stack.pop()
            for edge in bm.verts[vert_index].link_edges:
                for vert in edge.verts:
                    if vert.index not in seen:
                        seen.add(vert.index)
                        stack.append(vert.index)
        for vert_index in seen:
            bm.verts[vert_index].select = True
        for edge in bm.edges:
            if edge.verts[0].index in seen or edge.verts[1].index in seen:
                edge.select = True
        for face in bm.faces:
            if any(v.index in seen for v in face.verts):
                face.select = True

    # -- box selection -----------------------------------------------------

    def _apply_box_select(self, context, event):
        region = context.region
        rv3d = getattr(context.space_data, "region_3d", None)
        if region is None or rv3d is None or self.press_xy is None:
            return
        x, y = event.mouse_region_x, event.mouse_region_y
        x1, y1 = self.press_xy
        rect = (min(x1, x), min(y1, y), max(x1, x), max(y1, y))
        crossing = x < x1
        shift, ctrl = self.press_mods
        bm = self.edit_context.begin()
        try:
            geometry_mod.refresh(bm)
            matrix = self.edit_context.object.matrix_world
            projected = {}
            for vert in bm.verts:
                xy = location_3d_to_region_2d(region, rv3d, matrix @ vert.co)
                if xy is not None:
                    projected[vert.index] = (xy.x, xy.y)
            targets = []
            for face in bm.faces:
                if self._element_in_box(face.verts, projected, rect, crossing):
                    targets.append(("face", face.index))
            for edge in bm.edges:
                if self._element_in_box(edge.verts, projected, rect, crossing):
                    targets.append(("edge", edge.index))
            for vert in bm.verts:
                if self._in_rect(projected.get(vert.index), rect):
                    targets.append(("vert", vert.index))
            # Vertices belonging to a selected edge/face are implied;
            # a vertex inside the box only counts when it is free
            # (no link edges) or its element was selected.
            selected_elements = {
                (kind, index) for kind, index in targets if kind != "vert"
            }
            implied_verts = set()
            for kind, index in selected_elements:
                if kind == "edge":
                    implied_verts.update(
                        v.index for v in bm.edges[index].verts
                    )
                else:
                    implied_verts.update(
                        v.index for v in bm.faces[index].verts
                    )
            targets = [
                (kind, index)
                for kind, index in targets
                if kind != "vert"
                or index in implied_verts
                or not bm.verts[index].link_edges
            ]
            self._apply_mode(bm, targets, shift, ctrl)
        finally:
            self.edit_context.commit(bm)

    @staticmethod
    def _in_rect(xy, rect):
        if xy is None:
            return False
        return rect[0] <= xy[0] <= rect[2] and rect[1] <= xy[1] <= rect[3]

    def _element_in_box(self, verts, projected, rect, crossing):
        points = [projected.get(v.index) for v in verts]
        if crossing:
            if any(self._in_rect(p, rect) for p in points):
                return True
            # Any boundary edge crossing the rectangle border.
            rect_edges = [
                ((rect[0], rect[1]), (rect[2], rect[1])),
                ((rect[2], rect[1]), (rect[2], rect[3])),
                ((rect[2], rect[3]), (rect[0], rect[3])),
                ((rect[0], rect[3]), (rect[0], rect[1])),
            ]
            for i in range(len(points)):
                a, b = points[i], points[(i + 1) % len(points)]
                if a is None or b is None:
                    continue
                for c, d in rect_edges:
                    if segments_intersect_2d(a, b, c, d) is not None:
                        return True
            return False
        return all(self._in_rect(p, rect) for p in points)
