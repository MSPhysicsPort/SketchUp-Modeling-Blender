"""Push/Pull, Offset, Follow Me, and Flip tools (proposal §3.3-§3.5,
§6 P3/P4). Push/Pull: pull-out + push-in + punch-through openings
(boolean subtraction, P4) + double-click reuse + Ctrl keep-start-face.
Follow Me: automatic mode + manual path building (P4).
"""

import time

from mathutils import Vector

from ..context import undo_push
from ..core import curves as curve_mod
from ..core import punch as punch_mod
from ..core import sweep as sweep_mod
from ..core import transform as transform_mod
from ..core import geometry as geometry_mod
from ..core.geometry import refresh
from ..i18n.translations import translate as _T
from . import base as base_mod
from .base import SketchUpToolBase

PREVIEW_COLOR = (1.0, 0.55, 0.0, 0.9)
DOUBLE_CLICK_SECONDS = 0.4


def extrude_face_prism(bm, face, distance, keep_start):
    """Extrude a face along its normal by `distance`.

    Positive distance: the original face stays as the bottom,
    sides + top face are added (keep_start=True builds a separate
    prism with its own bottom face, leaving the original face
    untouched). Negative distance: the original face is removed
    (opening) and sides + cap are added. Returns the list of newly
    created vertex coordinates (for VCB retype undo).
    """
    refresh(bm)
    normal = Vector(face.normal)
    loop = [v.co.copy() for v in face.verts]
    loop_verts = list(face.verts)
    created_coords = []
    if keep_start:
        bottom = [bm.verts.new(co) for co in loop]
        top = [bm.verts.new(co + normal * distance) for co in loop]
        refresh(bm)
        bm.faces.new(tuple(reversed(bottom)))  # outward = opposite normal
        bm.faces.new(tuple(top))
        for i in range(len(loop)):
            j = (i + 1) % len(loop)
            bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
        created_coords = [v.co.copy() for v in bottom + top]
    else:
        top = [bm.verts.new(co + normal * distance) for co in loop]
        refresh(bm)
        if distance < 0:
            bm.faces.remove(face)
        bm.faces.new(tuple(top))
        for i in range(len(loop)):
            j = (i + 1) % len(loop)
            bm.faces.new((loop_verts[i], loop_verts[j], top[j], top[i]))
        created_coords = [v.co.copy() for v in top]
    refresh(bm)
    return created_coords


def delete_verts_at_coords(bm, coords, tolerance=1e-6):
    """Delete verts matching the given coords (with their connected
    faces/edges). Used to undo a recorded extrusion/offset."""
    import bmesh

    refresh(bm)
    targets = []
    for vert in bm.verts:
        for co in coords:
            if (vert.co - Vector(co)).length <= tolerance:
                targets.append(vert)
                break
    if targets:
        bmesh.ops.delete(bm, geom=targets, context="VERTS")
    refresh(bm)
    return len(targets)


# ---------------------------------------------------------------------------
# Push/Pull.
# ---------------------------------------------------------------------------


class SKETCHUP_OT_tool_push_pull(SketchUpToolBase):
    bl_idname = "sketchup.tool_push_pull"
    bl_label = "Push/Pull"
    bl_description = "Extrude a face along its normal."
    vcb_kind = "length"
    vcb_label = "Distance"

    def on_setup(self, context, event):
        self._state = "WAIT_FACE"
        self._face_index = None
        self._face_normal = None  # local
        self._face_center = None  # local
        self._face_loop = None  # local coords
        self._distance = 0.0
        self._last_click_time = 0.0
        self._last_click_face = None
        self._last_op = None  # (loop, normal, distance, keep_start, created_coords)
        self._keep_start = False
        self._limit_cache = None  # (face_index, mesh version, limit or None)

    def on_mouse_move(self, context, event):
        if self._state != "PULLING":
            return
        region = context.region
        rv3d = getattr(context.space_data, "region_3d", None)
        if region is None or rv3d is None:
            return
        x, y = event.mouse_region_x, event.mouse_region_y
        ray_origin = base_mod.region_2d_to_origin_3d(region, rv3d, (x, y))
        ray_dir = base_mod.region_2d_to_vector_3d(region, rv3d, (x, y))
        matrix = self.edit_context.object.matrix_world
        origin_local = self.edit_context.to_local(ray_origin)
        direction_local = (
            matrix.inverted().to_3x3() @ Vector(ray_dir)
        ).normalized()
        found = transform_mod.ray_line_distance(
            origin_local, direction_local, self._face_center, self._face_normal
        )
        if found is not None:
            self._distance = found
            if self._distance < 0:
                limit = self._preview_limit()
                if limit is not None and -self._distance >= limit:
                    self._distance = -limit
                    self.overlay.set_screentip(_T("Offset is limited"), (x, y))
                else:
                    self.overlay.set_screentip("", (0, 0))
            else:
                self.overlay.set_screentip("", (0, 0))
        self._preview_prism()

    def _preview_limit(self):
        """Push-through limit for the picked face (cached per mesh
        version: the BVH rebuild is the expensive part)."""
        version = self.edit_context.version
        cache = self._limit_cache
        if cache is not None and cache[0] == self._face_index and cache[1] == version:
            return cache[2]
        bm = self.edit_context.begin()
        try:
            refresh(bm)
            limit = punch_mod.find_push_limit(
                bm,
                self._face_center,
                -self._face_normal,
                skip_face_index=self._face_index,
            )
        finally:
            self.edit_context.abort(bm)
        self._limit_cache = (self._face_index, version, limit)
        return limit

    def on_left_press(self, context, event):
        now = time.monotonic()
        if self._state == "WAIT_FACE":
            picked = self.pick_at(context, event)
            if picked is None or picked[0] != "face":
                return None
            face_index = picked[1]
            self._last_click_time = now
            self._last_click_face = face_index
            bm = self.edit_context.begin()
            try:
                refresh(bm)
                face = bm.faces[face_index]
                self._face_index = face_index
                self._face_normal = Vector(face.normal)
                self._face_center = face.calc_center_median()
                self._face_loop = [v.co.copy() for v in face.verts]
            finally:
                self.edit_context.abort(bm)
            self._state = "PULLING"
            self._distance = 0.0
            self._keep_start = bool(event.ctrl)
            return None
        # PULLING: a quick second press on the same face is a
        # double-click -> reuse the last distance; otherwise commit.
        picked = self.pick_at(context, event)
        if (
            self._last_op is not None
            and picked is not None
            and picked[0] == "face"
            and picked[1] == self._last_click_face
            and now - self._last_click_time < DOUBLE_CLICK_SECONDS
        ):
            self._last_click_time = 0.0
            _loop, _normal, distance, keep_start, _c = self._last_op
            self._apply_extrude(picked[1], distance, event.ctrl or keep_start)
            self._state = "WAIT_FACE"
            self.overlay.set_lines([])
            return None
        self._apply_extrude(self._face_index, self._distance, event.ctrl or self._keep_start)
        self._state = "WAIT_FACE"
        self.overlay.set_lines([])
        return None

    def on_escape(self, context, event):
        if self._state == "PULLING":
            self._state = "WAIT_FACE"
            self.overlay.set_lines([])
            return {"RUNNING_MODAL"}
        return None

    def on_vcb_commit(self, context, value, kind):
        if self._state == "PULLING":
            self._apply_extrude(self._face_index, value, self._keep_start)
            self._state = "WAIT_FACE"
            self.overlay.set_lines([])
            return None
        if self._last_op is not None:
            loop, normal, _d, keep_start, created = self._last_op
            bm = self.edit_context.begin()
            try:
                delete_verts_at_coords(bm, created)
                # Re-find the original face by its loop coords.
                face = self._find_face_by_loop(bm, loop)
                if face is None and not keep_start:
                    # Negative-distance op removed it; rebuild it.
                    verts = [
                        geometry_mod.get_or_create_vert(bm, co) for co in loop
                    ]
                    refresh(bm)
                    face = bm.faces.new(tuple(verts))
                if face is not None:
                    created = extrude_face_prism(bm, face, value, keep_start)
                self.edit_context.commit(bm)
            except Exception:
                self.edit_context.abort(bm)
                raise
            undo_push("SketchUp Push/Pull")
            self._last_op = (loop, normal, value, keep_start, created)
            return None
        self.report({"WARNING"}, _T("Pick a face first"))
        return None

    def vcb_display_value(self, context):
        if self._state == "PULLING":
            return "%.3f" % self._distance
        return ""

    # -- internals ---------------------------------------------------------

    def _preview_prism(self):
        matrix = self.edit_context.object.matrix_world
        top = [co + self._face_normal * self._distance for co in self._face_loop]
        lines = []
        count = len(self._face_loop)
        for i in range(count):
            j = (i + 1) % count
            lines.append(
                (matrix @ self._face_loop[i], matrix @ self._face_loop[j], PREVIEW_COLOR, True)
            )
            lines.append((matrix @ top[i], matrix @ top[j], PREVIEW_COLOR, False))
            lines.append((matrix @ self._face_loop[i], matrix @ top[i], PREVIEW_COLOR, False))
        self.overlay.set_lines(lines)

    def _apply_extrude(self, face_index, distance, keep_start):
        bm = self.edit_context.begin()
        try:
            refresh(bm)
            face = bm.faces[face_index]
            loop = [v.co.copy() for v in face.verts]
            normal = Vector(face.normal)
            if distance < 0 and not keep_start:
                limit = punch_mod.find_push_limit(
                    bm, face.calc_center_median(), -normal,
                    skip_face_index=face_index,
                )
                if limit is not None and -distance >= limit - 1e-6:
                    # Punch-through: deferred commit (mode dance).
                    self.edit_context.abort(bm)
                    travel = limit + max(1e-3, limit * 0.001)
                    punch_mod.request_punch(
                        self.edit_context.object.name, loop, -normal, travel
                    )
                    self._last_op = None
                    return
            created = extrude_face_prism(bm, face, distance, keep_start)
            self.edit_context.commit(bm)
        except Exception:
            self.edit_context.abort(bm)
            raise
        undo_push("SketchUp Push/Pull")
        self._last_op = (loop, normal, distance, keep_start, created)

    @staticmethod
    def _find_face_by_loop(bm, loop):
        refresh(bm)
        wanted = sorted((round(c.x, 6), round(c.y, 6), round(c.z, 6)) for c in loop)
        for face in bm.faces:
            got = sorted(
                (round(v.co.x, 6), round(v.co.y, 6), round(v.co.z, 6))
                for v in face.verts
            )
            if got == wanted:
                return face
        return None


# ---------------------------------------------------------------------------
# Offset.
# ---------------------------------------------------------------------------


class SKETCHUP_OT_tool_offset(SketchUpToolBase):
    bl_idname = "sketchup.tool_offset"
    bl_label = "Offset"
    bl_description = "Offset a face loop or a selected edge chain."
    vcb_kind = "length"
    vcb_label = "Distance"

    def on_setup(self, context, event):
        self._state = "WAIT_TARGET"
        self._loop = None  # local coords, ordered
        self._closed = True
        self._normal = None  # local plane normal
        self._distance = 0.0
        self._plane_basis = None  # (u, v) unit vectors
        self._last_click_time = 0.0
        self._last_click_face = None
        self._last_op = None  # (loop, closed, normal, distance, created_coords)
        # Preselected edge chain?
        bm = self.edit_context.begin()
        try:
            refresh(bm)
            selected = [e for e in bm.edges if e.select]
            if len(selected) >= 2:
                ordered = self._order_chain(selected)
                if ordered is not None:
                    self._loop, self._closed = ordered
                    self._normal = self._chain_normal(self._loop)
                    self._plane_basis = None
                    self._state = "DRAGGING"
        finally:
            self.edit_context.abort(bm)

    def on_mouse_move(self, context, event):
        if self._loop is None:
            return
        inference = self.compute_inference(context, event)
        if inference is None:
            return
        point = self.edit_context.to_local(inference.point)
        self._distance = self._signed_distance(point)
        self._preview_offset()

    def on_left_press(self, context, event):
        now = time.monotonic()
        if self._loop is None:
            picked = self.pick_at(context, event)
            if picked is None or picked[0] != "face":
                return None
            face_index = picked[1]
            self._last_click_time = now
            self._last_click_face = face_index
            bm = self.edit_context.begin()
            try:
                refresh(bm)
                face = bm.faces[face_index]
                self._loop = [v.co.copy() for v in face.verts]
                self._closed = True
                self._normal = Vector(face.normal)
                self._plane_basis = None
                self._face_index = face_index
            finally:
                self.edit_context.abort(bm)
            self._state = "DRAGGING"
            self._distance = 0.0
            return None
        if self._state == "DRAGGING":
            # Double-click reuse: quick second press on the same face.
            picked = self.pick_at(context, event)
            if (
                self._last_op is not None
                and picked is not None
                and picked[0] == "face"
                and picked[1] == self._last_click_face
                and now - self._last_click_time < DOUBLE_CLICK_SECONDS
            ):
                self._last_click_time = 0.0
                _loop, _c, _n, distance, _cr = self._last_op
                self._apply_offset(picked[1], distance)
                self._loop = None
                self._state = "WAIT_TARGET"
                self.overlay.set_lines([])
                return None
            self._apply_offset(getattr(self, "_face_index", None), self._distance)
            self._loop = None
            self._state = "WAIT_TARGET"
            self.overlay.set_lines([])
            return None
        return None

    def on_escape(self, context, event):
        if self._loop is not None:
            self._loop = None
            self._state = "WAIT_TARGET"
            self.overlay.set_lines([])
            return {"RUNNING_MODAL"}
        return None

    def on_vcb_commit(self, context, value, kind):
        if self._loop is not None:
            self._apply_offset(getattr(self, "_face_index", None), value)
            self._loop = None
            self._state = "WAIT_TARGET"
            self.overlay.set_lines([])
            return None
        if self._last_op is not None:
            loop, closed, normal, _d, created = self._last_op
            bm = self.edit_context.begin()
            try:
                # Remove the old offset loop: any edge with an
                # endpoint lying on the old offset polyline.
                refresh(bm)
                old = self._offset_points_for(loop, closed, normal, _d)
                doomed = []
                for edge in bm.edges:
                    if self._edge_on_polyline(edge, old, closed):
                        doomed.append(edge)
                for edge in doomed:
                    if edge.is_valid:
                        geometry_mod.delete_edge(bm, edge, heal=True)
                self.edit_context.commit(bm)
            except Exception:
                self.edit_context.abort(bm)
                raise
            self._loop, self._closed, self._normal = loop, closed, normal
            self._plane_basis = None
            self._apply_offset(None, value)
            self._loop = None
            return None
        self.report({"WARNING"}, _T("Pick a face or select edges first"))
        return None

    def vcb_display_value(self, context):
        if self._loop is not None:
            return "%.3f" % abs(self._distance)
        return ""

    # -- internals ---------------------------------------------------------

    def _offset_points_for(self, loop, closed, normal, distance):
        saved = (self._loop, self._closed, self._normal, self._plane_basis)
        self._loop, self._closed, self._normal = loop, closed, normal
        self._plane_basis = None
        try:
            return self._offset_loop(distance) or []
        finally:
            self._loop, self._closed, self._normal, self._plane_basis = saved

    @staticmethod
    def _edge_on_polyline(edge, polyline, closed):
        if len(polyline) < 2:
            return False
        segments = list(zip(polyline, polyline[1:]))
        if closed:
            segments.append((polyline[-1], polyline[0]))
        for vert in edge.verts:
            point = vert.co
            for a, b in segments:
                ab = b - a
                denom = ab.length_squared
                if denom < 1e-12:
                    continue
                t = (point - a).dot(ab) / denom
                if 0.0 <= t <= 1.0 and (point - (a + ab * t)).length <= 1e-6:
                    return True
        return False

    @staticmethod
    def _order_chain(edges):
        """Order selected edges into a point list; None if not a chain."""
        pairs = [(e.verts[0].co, e.verts[1].co) for e in edges]
        ordered = sweep_mod.order_path(pairs)
        if ordered is None:
            return None
        points, closed = ordered
        return [Vector(p) for p in points], closed

    @staticmethod
    def _chain_normal(loop):
        # Newell normal of the loop (chains must be coplanar).
        normal = Vector()
        for a, b in zip(loop, loop[1:] + loop[:1]):
            normal.x += (a.y - b.y) * (a.z + b.z)
            normal.y += (a.z - b.z) * (a.x + b.x)
            normal.z += (a.x - b.x) * (a.y + b.y)
        if normal.length < 1e-9:
            return Vector((0, 0, 1))
        return normal.normalized()

    def _to_plane(self, point):
        u, v = self._plane_basis
        origin = self._loop[0]
        rel = Vector(point) - origin
        return (rel.dot(u), rel.dot(v))

    def _from_plane(self, uv):
        u, v = self._plane_basis
        return self._loop[0] + u * uv[0] + v * uv[1]

    def _ensure_basis(self):
        if self._plane_basis is not None:
            return
        n = self._normal
        if abs(n.z) < 0.9:
            u = n.cross(Vector((0, 0, 1))).normalized()
        else:
            u = n.cross(Vector((0, 1, 0))).normalized()
        self._plane_basis = (u, n.cross(u).normalized())

    def _signed_distance(self, point):
        self._ensure_basis()
        # Perpendicular distance to the nearest loop edge; sign by
        # which side of the edge the point lies (left = positive).
        best = None
        count = len(self._loop)
        seg_count = count if self._closed else count - 1
        for i in range(seg_count):
            a = self._loop[i]
            b = self._loop[(i + 1) % count]
            ab = b - a
            denom = ab.length_squared
            if denom < 1e-12:
                continue
            t = max(0.0, min(1.0, (Vector(point) - a).dot(ab) / denom))
            closest = a + ab * t
            dist = (Vector(point) - closest).length
            # Side: sign of the cross product with the plane normal.
            side = (ab.cross(Vector(point) - a)).dot(self._normal)
            signed = dist if side >= 0 else -dist
            if best is None or dist < abs(best):
                best = signed
        return best if best is not None else 0.0

    def _offset_loop(self, distance):
        self._ensure_basis()
        plane_points = [self._to_plane(p) for p in self._loop]
        # Keep the loop counter-clockwise in plane coords so a
        # positive distance offsets toward the loop interior
        # (offset_polygon_2d offsets left of each directed segment,
        # which is the interior side for CCW loops).
        area = transform_mod.polygon_signed_area_2d(plane_points)
        if self._closed and area < 0:
            plane_points = list(reversed(plane_points))
            flip = True
        else:
            flip = False
        offset = transform_mod.offset_polygon_2d(
            plane_points, distance, closed=self._closed
        )
        if offset is None:
            return None
        if flip:
            offset = list(reversed(offset))
        return [self._from_plane(uv) for uv in offset]

    def _preview_offset(self):
        offset = self._offset_loop(self._distance)
        if offset is None:
            return
        matrix = self.edit_context.object.matrix_world
        lines = []
        count = len(offset)
        seg_count = count if self._closed else count - 1
        for i in range(seg_count):
            lines.append(
                (
                    matrix @ offset[i],
                    matrix @ offset[(i + 1) % count],
                    PREVIEW_COLOR,
                    False,
                )
            )
        self.overlay.set_lines(lines)

    def _apply_offset(self, _face_index, distance):
        offset = self._offset_loop(distance)
        if offset is None or len(offset) < 2:
            self.report({"WARNING"}, _T("Offset failed for this shape"))
            return
        bm = self.edit_context.begin()
        try:
            count = len(offset)
            seg_count = count if self._closed else count - 1
            created = list(offset)
            for i in range(seg_count):
                geometry_mod.apply_line(bm, offset[i], offset[(i + 1) % count])
            self.edit_context.commit(bm)
        except Exception:
            self.edit_context.abort(bm)
            raise
        undo_push("SketchUp Offset")
        self._last_op = (
            list(self._loop),
            self._closed,
            Vector(self._normal),
            distance,
            created,
        )


# ---------------------------------------------------------------------------
# Follow Me (automatic mode).
# ---------------------------------------------------------------------------


class SKETCHUP_OT_tool_follow_me(SketchUpToolBase):
    bl_idname = "sketchup.tool_follow_me"
    bl_label = "Follow Me"
    bl_description = "Sweep a face along preselected path edges."
    vcb_kind = None

    def on_setup(self, context, event):
        self._path = None  # (points, closed, curve_edges_flag)
        self._mode = "manual"
        self._state = "profile"
        self._profile = None  # (coords, normal)
        self._path_end = None
        bm = self.edit_context.begin()
        try:
            refresh(bm)
            selected = [e for e in bm.edges if e.select]
            if len(selected) >= 1:
                pairs = [(e.verts[0].co, e.verts[1].co) for e in selected]
                ordered = sweep_mod.order_path(pairs)
                if ordered is not None:
                    points, closed = ordered
                    curved = any(
                        curve_mod.curve_id_of(bm, e) != 0 for e in selected
                    )
                    self._path = ([Vector(p) for p in points], closed, curved)
                    self._mode = "auto"
                    return
                self.report({"WARNING"}, _T("Path edges must form one chain"))
        finally:
            self.edit_context.abort(bm)
        self.overlay.set_screentip(
            _T("Click a profile face, then click path edges"), (20, 60)
        )

    def modal(self, context, event):
        # Enter finishes manual path building (geometry is
        # committed per segment, so Enter just ends the tool).
        if (
            getattr(self, "_mode", None) == "manual"
            and event.type in {"RET", "NUMPAD_ENTER"}
            and event.value == "PRESS"
        ):
            return self._finish(context)
        return SketchUpToolBase.modal(self, context, event)

    def on_left_press(self, context, event):
        if getattr(self, "_mode", "auto") == "auto":
            return self._auto_press(context, event)
        return self._manual_press(context, event)

    def _auto_press(self, context, event):
        if self._path is None:
            return {"FINISHED"}
        picked = self.pick_at(context, event)
        if picked is None or picked[0] != "face":
            return None
        face_index = picked[1]
        path_points, closed, curved = self._path
        bm = self.edit_context.begin()
        try:
            refresh(bm)
            geometry_mod.ensure_layers(bm)
            face = bm.faces[face_index]
            profile = [v.co.copy() for v in face.verts]
            profile_verts = list(face.verts)
            normal = Vector(face.normal)
            swept = sweep_mod.sweep_profile(profile, normal, path_points, closed)
            if swept is None:
                self.report({"WARNING"}, _T("Could not sweep this profile"))
                self.edit_context.abort(bm)
                return {"FINISHED"}
            rings, side_quads = swept
            profile_count = len(profile)
            # Ring 0 reuses the profile face's verts when coincident.
            ring_verts = []
            reuse = all(
                (rings[0][j] - profile[j]).length <= 1e-6
                for j in range(profile_count)
            )
            for i, ring in enumerate(rings):
                if i == 0 and reuse:
                    ring_verts.append(list(profile_verts))
                else:
                    ring_verts.append([bm.verts.new(co) for co in ring])
            refresh(bm)
            flat = [v for ring in ring_verts for v in ring]
            for quad in side_quads:
                verts = tuple(flat[i] for i in quad)
                if bm.faces.get(verts) is None:
                    try:
                        bm.faces.new(verts)
                    except ValueError:
                        pass
            refresh(bm)
            if not closed:
                # End cap at the last ring (same winding as profile).
                cap = tuple(ring_verts[-1])
                if bm.faces.get(cap) is None:
                    try:
                        bm.faces.new(cap)
                    except ValueError:
                        pass
            refresh(bm)
            if curved:
                # Soften the path-direction edges of the sweep.
                for i in range(len(rings) - (0 if closed else 1)):
                    ring_a = ring_verts[i]
                    ring_b = ring_verts[(i + 1) % len(rings)]
                    for j in range(profile_count):
                        edge = bm.edges.get((ring_a[j], ring_b[j]))
                        if edge is not None:
                            geometry_mod.set_edge_flags(bm, edge, soft=True)
            self.edit_context.commit(bm)
        except Exception:
            self.edit_context.abort(bm)
            raise
        undo_push("SketchUp Follow Me")
        return {"FINISHED"}

    # -- manual mode: profile first, then one edge click per segment --

    def _manual_press(self, context, event):
        picked = self.pick_at(context, event)
        if picked is None:
            return None
        if self._state == "profile":
            if picked[0] != "face":
                return None
            bm = self.edit_context.begin()
            try:
                refresh(bm)
                face = bm.faces[picked[1]]
                coords = [v.co.copy() for v in face.verts]
                self._profile = (coords, Vector(face.normal))
                self._path_end = None
            finally:
                self.edit_context.abort(bm)
            self._state = "path"
            self.overlay.set_screentip(
                _T("Click a path edge; Alt+click a face for its perimeter"),
                (20, 60),
            )
            return None
        # State "path".
        if event.alt and picked[0] == "face":
            return self._manual_perimeter(context, picked[1])
        if picked[0] != "edge":
            return None
        return self._manual_segment(context, picked[1])

    def _manual_segment(self, context, edge_key):
        profile, normal = self._profile
        bm = self.edit_context.begin()
        try:
            refresh(bm)
            edge = bm.edges.get(
                (bm.verts[edge_key[0]], bm.verts[edge_key[1]])
            )
            if edge is None:
                self.edit_context.abort(bm)
                return None
            a = edge.verts[0].co.copy()
            b = edge.verts[1].co.copy()
            if self._path_end is None:
                center = sum(profile, Vector()) / len(profile)
                if (a - center).length <= (b - center).length:
                    start, end = a, b
                else:
                    start, end = b, a
            elif (a - self._path_end).length <= 1e-6:
                start, end = a, b
            elif (b - self._path_end).length <= 1e-6:
                start, end = b, a
            else:
                self.report(
                    {"WARNING"},
                    _T("Path edge must connect to the current end"),
                )
                self.edit_context.abort(bm)
                return None
            direction = end - start
            length = direction.length
            if length < 1e-9:
                self.edit_context.abort(bm)
                return None
            direction.normalize()
            ring1, quads = sweep_mod.sweep_segment(
                profile, normal, start, direction, length
            )
            get_vert = geometry_mod.get_or_create_vert
            ring0_verts = [get_vert(bm, co) for co in profile]
            ring1_verts = [get_vert(bm, co) for co in ring1]
            refresh(bm)
            flat = ring0_verts + ring1_verts
            for quad in quads:
                verts = tuple(flat[i] for i in quad)
                if bm.faces.get(verts) is None:
                    try:
                        bm.faces.new(verts)
                    except ValueError:
                        pass
            refresh(bm)
            cap = tuple(ring1_verts)
            if bm.faces.get(cap) is None:
                try:
                    bm.faces.new(cap)
                except ValueError:
                    pass
            self.edit_context.commit(bm)
        except Exception:
            self.edit_context.abort(bm)
            raise
        undo_push("SketchUp Follow Me")
        self._profile = (ring1, direction)
        self._path_end = end
        return None

    def _manual_perimeter(self, context, face_index):
        profile, normal = self._profile
        bm = self.edit_context.begin()
        try:
            refresh(bm)
            face = bm.faces[face_index]
            path = [v.co.copy() for v in face.verts]
            swept = sweep_mod.sweep_profile(profile, normal, path, True)
            if swept is None:
                self.report({"WARNING"}, _T("Could not sweep this profile"))
                self.edit_context.abort(bm)
                return {"FINISHED"}
            rings, side_quads = swept
            get_vert = geometry_mod.get_or_create_vert
            ring_verts = [[get_vert(bm, co) for co in ring] for ring in rings]
            refresh(bm)
            flat = [v for ring in ring_verts for v in ring]
            for quad in side_quads:
                verts = tuple(flat[i] for i in quad)
                if bm.faces.get(verts) is None:
                    try:
                        bm.faces.new(verts)
                    except ValueError:
                        pass
            self.edit_context.commit(bm)
        except Exception:
            self.edit_context.abort(bm)
            raise
        undo_push("SketchUp Follow Me")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Flip.
# ---------------------------------------------------------------------------


class SKETCHUP_OT_tool_flip(SketchUpToolBase):
    bl_idname = "sketchup.tool_flip"
    bl_label = "Flip"
    bl_description = "Mirror the selection across a plane (arrow keys pick the axis)."
    vcb_kind = None

    AXES = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
    AXIS_NAMES = ("Red", "Green", "Blue")

    def on_setup(self, context, event):
        bm = self.edit_context.begin()
        try:
            indices = transform_mod.selection_vert_indices(bm)
            if not indices:
                self.report({"WARNING"}, _T("Select something to flip first"))
                self._no_selection = True
                return
            self._no_selection = False
            self._snapshot = transform_mod.capture_snapshot(bm, indices)
        finally:
            self.edit_context.abort(bm)
        self._axis_index = 0
        low, high = transform_mod.bbox_of_points(self._snapshot.verts.values())
        self._center = (low + high) * 0.5
        self._draw_plane()

    def _draw_plane(self):
        matrix = self.edit_context.object.matrix_world
        axis = self.AXES[self._axis_index]
        others = [a for a in range(3) if a != self._axis_index]
        low, high = transform_mod.bbox_of_points(self._snapshot.verts.values())
        size = max((high - low).length, 0.1) * 0.75
        corners = []
        for s1 in (-1, 1):
            for s2 in (-1, 1):
                pos = Vector(self._center)
                pos[others[0]] += s1 * size
                pos[others[1]] += s2 * size
                corners.append(matrix @ pos)
        lines = []
        for i, a in enumerate(corners):
            for b in corners[i + 1 :]:
                diff = a - b
                if sum(1 for c in diff if abs(c) > 1e-9) == 1:
                    lines.append((a, b, PREVIEW_COLOR, True))
        self.overlay.set_lines(lines)
        self.overlay.set_screentip(
            _T("Flip Along %s") % self.AXIS_NAMES[self._axis_index], (20, 60)
        )

    def on_mouse_move(self, context, event):
        # Arrow keys cycle the axis via the base lock handler; also
        # accept plain key events here through modal fallthrough.
        return None

    def modal(self, context, event):
        # Intercept arrow keys before the base lock handling: in the
        # Flip tool they pick the mirror plane, not a lock.
        if event.type in {"RIGHT_ARROW", "LEFT_ARROW", "UP_ARROW"} and event.value == "PRESS":
            self._axis_index = {
                "RIGHT_ARROW": 0,
                "LEFT_ARROW": 1,
                "UP_ARROW": 2,
            }[event.type]
            self._draw_plane()
            return {"RUNNING_MODAL"}
        return SketchUpToolBase.modal(self, context, event)

    def on_left_press(self, context, event):
        if getattr(self, "_no_selection", False):
            return {"FINISHED"}
        matrix = transform_mod.mirror_matrix(
            self._center, self.AXES[self._axis_index]
        )
        bm = self.edit_context.begin()
        try:
            if event.ctrl:
                transform_mod.duplicate_snapshot(bm, self._snapshot, matrix)
            else:
                transform_mod.move_snapshot_verts(bm, self._snapshot, matrix)
            self.edit_context.commit(bm)
        except Exception:
            self.edit_context.abort(bm)
            raise
        undo_push("SketchUp Flip")
        # Refresh the snapshot so repeated flips keep working.
        bm = self.edit_context.begin()
        try:
            indices = transform_mod.selection_vert_indices(bm)
            if indices:
                self._snapshot = transform_mod.capture_snapshot(bm, indices)
        finally:
            self.edit_context.abort(bm)
        return None


EXTRUDE_OPERATORS = [
    SKETCHUP_OT_tool_push_pull,
    SKETCHUP_OT_tool_offset,
    SKETCHUP_OT_tool_follow_me,
    SKETCHUP_OT_tool_flip,
]
