"""Tag tool: click an object to assign the active tag."""

import bpy
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d

from ..context import undo_push
from ..data import tags as tags_mod
from ..i18n.translations import translate as _T
from .base import SketchUpToolBase


class SKETCHUP_OT_tool_tag(SketchUpToolBase):
    bl_idname = "sketchup.tool_tag"
    bl_label = "Tag"
    bl_description = "Click an object to assign the active tag."
    vcb_kind = None

    def on_setup(self, context, event):
        tags_mod.ensure_defaults(context.scene)
        self.overlay.set_screentip(
            _T("Click an object to tag it: %s")
            % tags_mod.active_tag_name(context.scene),
            (20, 60),
        )

    def on_left_press(self, context, event):
        region = context.region
        rv3d = getattr(context.space_data, "region_3d", None)
        if region is None or rv3d is None:
            return None
        coord = (event.mouse_region_x, event.mouse_region_y)
        origin = region_2d_to_origin_3d(region, rv3d, coord)
        direction = region_2d_to_vector_3d(region, rv3d, coord)
        depsgraph = context.evaluated_depsgraph_get()
        hit, _loc, _normal, _index, obj, _matrix = context.scene.ray_cast(
            depsgraph, origin, direction
        )
        if not hit or obj is None:
            return None
        name = tags_mod.active_tag_name(context.scene)
        tags_mod.set_object_tag(obj, name)
        tags_mod.apply_visibility(context.scene)
        undo_push("SketchUp Tag")
        self.report({"INFO"}, _T("Tagged %s: %s") % (obj.name, name))
        return None


TAG_TOOL_OPERATORS = [SKETCHUP_OT_tool_tag]
