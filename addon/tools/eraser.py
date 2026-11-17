"""Eraser tool (research/01 §5.3.8): click an edge to delete it
and its adjacent faces (faces heal when a divider is removed);
drag to erase continuously. Ctrl softens+smooths, Shift hides,
Ctrl+Shift un-softens (D14 conflict resolved per QRC: Ctrl+Shift
is Unsoften), Alt clears all edge flags.
The Eraser never deletes a face directly.
"""

import bpy
from bpy_extras.view3d_utils import location_3d_to_region_2d
from mathutils import Vector

from ..core import geometry as geometry_mod
from ..core.inference import dist_point_to_segment_2d
from .base import SketchUpToolBase

PICK_TOLERANCE_PX = 8.0
HIGHLIGHT_COLOR = (1.0, 0.3, 0.3, 1.0)


class SKETCHUP_OT_tool_eraser(SketchUpToolBase):
    bl_idname = "sketchup.tool_eraser"
    bl_label = "Eraser"
    bl_description = "SketchUp Eraser tool: delete, soften, or hide edges."

    vcb_kind = None

    def on_setup(self, context, event):
        self.erasing = False
        self.erased = set()
        self.stroke_dirty = False
        self.stroke_mods = (False, False, False)
        self.hovered = None

    # -- picking -----------------------------------------------------------

    def _pick_edge(self, context, event):
        region = context.region
        rv3d = getattr(context.space_data, "region_3d", None)
        if region is None or rv3d is None:
            return None
        x, y = event.mouse_region_x, event.mouse_region_y
        bm = self.edit_context.begin()
        try:
            geometry_mod.refresh(bm)
            matrix = self.edit_context.object.matrix_world
            best = None
            for edge in bm.edges:
                w1 = matrix @ edge.verts[0].co
                w2 = matrix @ edge.verts[1].co
                xy1 = location_3d_to_region_2d(region, rv3d, w1)
                xy2 = location_3d_to_region_2d(region, rv3d, w2)
                if xy1 is None or xy2 is None:
                    continue
                dist = dist_point_to_segment_2d(x, y, xy1.x, xy1.y, xy2.x, xy2.y)
                if dist <= PICK_TOLERANCE_PX and (best is None or dist < best[0]):
                    best = (dist, tuple(w1), tuple(w2))
            if best is None:
                return None
            return (best[1], best[2])
        finally:
            self.edit_context.abort(bm)

    @staticmethod
    def _edge_key(world_pair):
        rounded = [tuple(round(c, 6) for c in co) for co in world_pair]
        return tuple(sorted(rounded))

    # -- mouse ---------------------------------------------------------------

    def on_mouse_move(self, context, event):
        picked = self._pick_edge(context, event)
        self.hovered = picked
        if picked is not None:
            self.overlay.set_lines(
                [(Vector(picked[0]), Vector(picked[1]), HIGHLIGHT_COLOR, False)]
            )
        else:
            self.overlay.set_lines([])
        if self.erasing and picked is not None:
            key = self._edge_key(picked)
            if key not in self.erased:
                self.erased.add(key)
                if self._apply_at(context, picked, self.stroke_mods):
                    self.stroke_dirty = True

    def on_left_press(self, context, event):
        self.erasing = True
        self.erased = set()
        self.stroke_mods = (event.shift, event.ctrl, event.alt)
        self.stroke_dirty = False
        picked = self._pick_edge(context, event)
        if picked is not None:
            self.erased.add(self._edge_key(picked))
            if self._apply_at(context, picked, self.stroke_mods):
                self.stroke_dirty = True
        return None

    def on_left_release(self, context, event):
        self.erasing = False
        if self.stroke_dirty:
            from ..context import undo_push

            undo_push("SketchUp Eraser")
        self.stroke_dirty = False
        self.erased = set()
        return None

    # -- actions ---------------------------------------------------------------

    def _apply_at(self, context, world_pair, mods):
        shift, ctrl, alt = mods
        bm = self.edit_context.begin()
        try:
            geometry_mod.refresh(bm)
            local_a = self.edit_context.to_local(Vector(world_pair[0]))
            local_b = self.edit_context.to_local(Vector(world_pair[1]))
            v1 = geometry_mod.find_vert_near(bm, local_a)
            v2 = geometry_mod.find_vert_near(bm, local_b)
            if v1 is None or v2 is None:
                return False
            edge = bm.edges.get((v1, v2))
            if edge is None:
                return False
            coords = (v1.co.copy(), v2.co.copy())

            def _live_edge():
                a = geometry_mod.find_vert_near(bm, coords[0])
                b = geometry_mod.find_vert_near(bm, coords[1])
                return bm.edges.get((a, b)) if a is not None and b is not None else None

            if alt:
                geometry_mod.clear_edge_flags(bm, edge)
                live = _live_edge()
                if live is not None:
                    live.smooth = False
            elif ctrl and shift:
                # D14: Ctrl+Shift is Unsoften (soft flag only).
                geometry_mod.set_edge_flags(bm, edge, soft=False)
                live = _live_edge()
                if live is not None:
                    live.smooth = False
            elif ctrl:
                geometry_mod.set_edge_flags(bm, edge, soft=True)
            elif shift:
                geometry_mod.set_edge_flags(bm, edge, hidden=True)
            else:
                geometry_mod.delete_edge(bm, edge, heal=True)
        finally:
            self.edit_context.commit(bm)
        return True
