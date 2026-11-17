"""Dimension and Text tools (proposal §3.10, P6)."""

import bpy
from mathutils import Vector

from ..context import undo_push
from ..data import annotations as annotations_mod
from ..i18n.translations import translate as _T
from .base import SketchUpToolBase

DIMENSION_COLOR = (0.1, 0.1, 0.1, 1.0)


class SKETCHUP_OT_tool_dimension(SketchUpToolBase):
    bl_idname = "sketchup.tool_dimension"
    bl_label = "Dimension"
    bl_description = "Place an aligned dimension with three clicks."
    vcb_kind = None

    def on_setup(self, context, event):
        self.state = "WAIT_P1"
        self.p1 = None
        self.p2 = None
        self.current_point = None
        self.overlay.set_screentip(
            _T("Click the first measured point"), (20, 60)
        )

    def on_mouse_move(self, context, event):
        inference = self.compute_inference(context, event)
        if inference is None:
            return
        self.current_point = Vector(inference.point)
        self.overlay.set_marker(
            inference.point, inference.kind, inference.color
        )
        lines = []
        if self.state == "WAIT_P2" and self.p1 is not None:
            lines.append((self.p1, self.current_point, DIMENSION_COLOR, False))
        elif self.state == "WAIT_OFFSET":
            layout = annotations_mod.dimension_geometry(
                self.p1, self.p2, self.current_point
            )
            if layout is not None:
                lines.append(
                    (layout["dim_a"], layout["dim_b"], DIMENSION_COLOR, False)
                )
                lines.append(
                    (layout["ext1"][0], layout["ext1"][1], DIMENSION_COLOR, False)
                )
                lines.append(
                    (layout["ext2"][0], layout["ext2"][1], DIMENSION_COLOR, False)
                )
        self.overlay.set_lines(lines)

    def on_left_press(self, context, event):
        if self.current_point is None:
            inference = self.compute_inference(context, event)
            if inference is None:
                return None
            self.current_point = Vector(inference.point)
        if self.state == "WAIT_P1":
            self.p1 = Vector(self.current_point)
            self.state = "WAIT_P2"
            self.overlay.set_screentip(
                _T("Click the second measured point"), (20, 60)
            )
            return None
        if self.state == "WAIT_P2":
            if (self.current_point - self.p1).length < 1e-9:
                return None
            self.p2 = Vector(self.current_point)
            self.state = "WAIT_OFFSET"
            self.overlay.set_screentip(
                _T("Click to place the dimension line"), (20, 60)
            )
            return None
        obj = self.edit_context.object
        ref1 = (obj.name, self.edit_context.to_local(self.p1))
        ref2 = (obj.name, self.edit_context.to_local(self.p2))
        annotations_mod.add_dimension(
            context.scene, self.p1, self.p2, self.current_point, ref1, ref2
        )
        undo_push("SketchUp Dimension")
        self.state = "WAIT_P1"
        self.p1 = None
        self.p2 = None
        self.overlay.set_lines([])
        return None


# -- Text tool: click a point, then type the text in a dialog --------

_pending_text = {"point": None, "anchor_offset": (0.5, 0.0, 0.3)}


class SKETCHUP_OT_tool_text(SketchUpToolBase):
    bl_idname = "sketchup.tool_text"
    bl_label = "Text"
    bl_description = "Click a point and type a leader note."
    vcb_kind = None

    def on_setup(self, context, event):
        self.overlay.set_screentip(
            _T("Click the point the note refers to"), (20, 60)
        )

    def on_left_press(self, context, event):
        inference = self.compute_inference(context, event)
        if inference is None:
            return None
        point = Vector(inference.point)
        rv3d = getattr(context.space_data, "region_3d", None)
        if rv3d is not None:
            rotation = rv3d.view_rotation
            right = rotation @ Vector((1, 0, 0))
            up = rotation @ Vector((0, 1, 0))
            offset = right * 0.5 + up * 0.3
        else:
            offset = Vector((0.5, 0.0, 0.3))
        _pending_text["point"] = tuple(point)
        _pending_text["anchor_offset"] = tuple(offset)

        def _invoke():
            try:
                bpy.ops.sketchup.text_input("INVOKE_DEFAULT")
            except Exception:
                pass
            return None

        try:
            bpy.app.timers.register(_invoke, first_interval=0.0)
        except Exception:
            pass
        return {"FINISHED"}


ANNOTATE_TOOL_OPERATORS = [
    SKETCHUP_OT_tool_dimension,
    SKETCHUP_OT_tool_text,
]
