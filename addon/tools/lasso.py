"""Lasso selection tool (proposal §3.2, P6): drag a freehand
polygon; clockwise selects fully contained entities,
counter-clockwise selects everything touched (D14).
"""

from bpy_extras.view3d_utils import location_3d_to_region_2d
from mathutils import Vector

from ..core import geometry as geometry_mod
from ..i18n.translations import translate as _T
from .base import SketchUpToolBase
from .switching import request_switch


def polygon_signed_area(points):
    """Signed area (y-up screen coords): > 0 is counter-clockwise."""
    area = 0.0
    count = len(points)
    for i in range(count):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % count]
        area += x1 * y2 - x2 * y1
    return area * 0.5


def point_in_polygon(point, polygon):
    x, y = point
    inside = False
    count = len(polygon)
    for i in range(count):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % count]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                inside = not inside
    return inside


def _orientation(a, b, c):
    value = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if abs(value) < 1e-12:
        return 0
    return 1 if value > 0 else -1


def segments_intersect_2d(a, b, c, d):
    o1, o2 = _orientation(a, b, c), _orientation(a, b, d)
    o3, o4 = _orientation(c, d, a), _orientation(c, d, b)
    return o1 != o2 and o3 != o4


def edge_crosses_polygon(a, b, polygon):
    count = len(polygon)
    for i in range(count):
        if segments_intersect_2d(a, b, polygon[i], polygon[(i + 1) % count]):
            return True
    return False


class SKETCHUP_OT_tool_lasso(SketchUpToolBase):
    bl_idname = "sketchup.tool_lasso"
    bl_label = "Lasso"
    bl_description = "Drag a freehand loop to select (clockwise: contained, counter-clockwise: touched)."
    vcb_kind = None

    def on_setup(self, context, event):
        self.points = []
        self.dragging = False
        self.overlay.set_screentip(
            _T("Drag a loop to select"), (20, 60)
        )

    def on_left_press(self, context, event):
        self.points = [(event.mouse_region_x, event.mouse_region_y)]
        self.dragging = True
        self.overlay.set_lasso(self.points)
        return None

    def on_mouse_move(self, context, event):
        if not self.dragging:
            return
        point = (event.mouse_region_x, event.mouse_region_y)
        last = self.points[-1]
        if abs(point[0] - last[0]) + abs(point[1] - last[1]) >= 3:
            self.points.append(point)
            self.overlay.set_lasso(self.points)

    def on_left_release(self, context, event):
        if not self.dragging:
            return None
        self.dragging = False
        self.overlay.set_lasso([])
        if len(self.points) < 3:
            return None
        crossing = polygon_signed_area(self.points) > 0
        self._apply_selection(context, event, crossing)
        request_switch("sketchup.tool_select")
        return {"FINISHED"}

    def _apply_selection(self, context, event, crossing):
        region = context.region
        rv3d = getattr(context.space_data, "region_3d", None)
        if region is None or rv3d is None:
            return
        matrix = self.edit_context.object.matrix_world
        bm = self.edit_context.begin()
        try:
            geometry_mod.refresh(bm)
            projected = {}
            inside = {}
            for vert in bm.verts:
                xy = location_3d_to_region_2d(
                    region, rv3d, matrix @ vert.co
                )
                if xy is None:
                    projected[vert.index] = None
                    inside[vert.index] = False
                else:
                    point = (xy.x, xy.y)
                    projected[vert.index] = point
                    inside[vert.index] = point_in_polygon(point, self.points)
            if not event.shift:
                for vert in bm.verts:
                    vert.select = False
                for edge in bm.edges:
                    edge.select = False
                for face in bm.faces:
                    face.select = False
            for vert in bm.verts:
                if inside[vert.index]:
                    vert.select = True
            for edge in bm.edges:
                a, b = edge.verts[0].index, edge.verts[1].index
                if crossing:
                    hit = inside[a] or inside[b]
                    if not hit and projected[a] and projected[b]:
                        hit = edge_crosses_polygon(
                            projected[a], projected[b], self.points
                        )
                else:
                    hit = inside[a] and inside[b]
                if hit:
                    edge.select = True
            for face in bm.faces:
                indices = [v.index for v in face.verts]
                if crossing:
                    hit = any(inside[i] for i in indices)
                    if not hit:
                        for edge in face.edges:
                            a, b = edge.verts[0].index, edge.verts[1].index
                            if projected[a] and projected[b] and edge_crosses_polygon(
                                projected[a], projected[b], self.points
                            ):
                                hit = True
                                break
                else:
                    hit = all(inside[i] for i in indices)
                if hit:
                    face.select = True
            self.edit_context.commit(bm)
        except Exception:
            self.edit_context.abort(bm)
            raise


LASSO_OPERATORS = [SKETCHUP_OT_tool_lasso]
