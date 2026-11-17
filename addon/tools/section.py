"""Section Plane tool: click a face to place a cutting plane
aligned to it, or click empty space for a horizontal plane on the
ground. The new plane becomes active immediately.
"""

from mathutils import Vector
from mathutils.geometry import intersect_line_plane

from ..context import undo_push
from ..data import sections as sections_mod
from ..i18n.translations import translate as _T
from .base import SketchUpToolBase

PREVIEW_COLOR = (1.0, 0.55, 0.0, 0.9)


class SKETCHUP_OT_tool_section_plane(SketchUpToolBase):
    bl_idname = "sketchup.tool_section_plane"
    bl_label = "Section Plane"
    bl_description = "Place a section plane to cut the model for display."
    vcb_kind = None

    def on_setup(self, context, event):
        self._hover = None
        self.overlay.set_screentip(
            _T("Click a face to place the section plane"), (20, 60)
        )

    def _plane_at(self, context, event):
        """(world point, world normal) under the cursor, or None."""
        picked = self.pick_at(context, event)
        if picked is not None and picked[0] == "face":
            matrix = self.edit_context.object.matrix_world
            bm = self.edit_context.begin()
            try:
                from ..core import geometry as geometry_mod

                geometry_mod.refresh(bm)
                face = bm.faces[picked[1]]
                center = Vector(face.calc_center_median())
                normal = Vector(face.normal)
            finally:
                self.edit_context.abort(bm)
            return matrix @ center, (matrix.to_3x3() @ normal).normalized()
        # Fallback: horizontal plane on the ground (z=0).
        region = context.region
        rv3d = getattr(context.space_data, "region_3d", None)
        if region is None or rv3d is None:
            return None
        from bpy_extras.view3d_utils import (
            region_2d_to_origin_3d,
            region_2d_to_vector_3d,
        )

        coord = (event.mouse_region_x, event.mouse_region_y)
        origin = region_2d_to_origin_3d(region, rv3d, coord)
        direction = region_2d_to_vector_3d(region, rv3d, coord)
        hit = intersect_line_plane(
            origin, origin + direction, Vector((0, 0, 0)), Vector((0, 0, 1))
        )
        if hit is None:
            return None
        return hit, Vector((0, 0, 1))

    def on_mouse_move(self, context, event):
        placed = self._plane_at(context, event)
        self._hover = placed
        if placed is None:
            self.overlay.set_lines([])
            return
        point, normal = placed
        helper = Vector((1, 0, 0)) if abs(normal.x) < 0.9 else Vector((0, 1, 0))
        u = normal.cross(helper).normalized()
        v = normal.cross(u)
        size = 1.0
        corners = [
            point + (+u + v) * size,
            point + (-u + v) * size,
            point + (-u - v) * size,
            point + (+u - v) * size,
        ]
        lines = [
            (corners[i], corners[(i + 1) % 4], PREVIEW_COLOR, False)
            for i in range(4)
        ]
        self.overlay.set_lines(lines)

    def on_left_press(self, context, event):
        placed = self._hover or self._plane_at(context, event)
        if placed is None:
            return None
        point, normal = placed
        scene = context.scene
        plane = sections_mod.create_section_plane(scene, point, normal)
        sections_mod.set_active_section(scene, plane)
        try:
            context.view_layer.objects.active = plane
            plane.select_set(True)
        except Exception:
            pass
        undo_push("SketchUp Section Plane")
        self.report({"INFO"}, _T("Section plane placed: %s") % plane.name)
        return {"FINISHED"}


SECTION_TOOL_OPERATORS = [SKETCHUP_OT_tool_section_plane]
