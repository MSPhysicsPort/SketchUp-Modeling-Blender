"""Curve commands: Divide, Weld Edges, Explode Curve, Convert to
Polygon, and the Entity Info curve edit (proposal §3.2 / research A
§5.2.2, §5.2.4, §5.2.7).

Execute-only operators on the current selection. They run through
EditContext, so they work in both Edit Mode (GUI) and headless
tests. Menu placement (right-click context menu) arrives with P5;
until then they are available via operator search.
"""

import bmesh
import bpy

from ..context import EditContext, undo_push
from ..core import curves as curve_mod
from ..core import geometry as geometry_mod


def _selected_edges(bm):
    geometry_mod.refresh(bm)
    return [edge for edge in bm.edges if edge.select]


class SKETCHUP_OT_divide_edge(bpy.types.Operator):
    bl_idname = "sketchup.divide_edge"
    bl_label = "Divide"
    bl_description = "Divide the selected edges into equal segments."
    bl_options = {"REGISTER", "UNDO"}

    segments: bpy.props.IntProperty(
        name="Segments", description="Number of equal parts", default=2, min=2, max=100
    )

    def execute(self, context):
        edit_context = EditContext(context)
        bm = edit_context.begin()
        try:
            edges = _selected_edges(bm)
            if not edges:
                self.report({"WARNING"}, "No edges selected")
                edit_context.abort(bm)
                return {"CANCELLED"}
            from mathutils import Vector

            for edge in edges:
                if not edge.is_valid:
                    continue
                v1, v2 = edge.verts[0].co.copy(), edge.verts[1].co.copy()
                for i in range(1, self.segments):
                    point = v1.lerp(v2, i / self.segments)
                    # Re-find the live edge containing this point.
                    geometry_mod.refresh(bm)
                    target = None
                    for candidate in bm.edges:
                        if not candidate.is_valid:
                            continue
                        dist, t = geometry_mod.point_on_edge_distance(
                            point, candidate
                        )
                        if dist <= 1e-6 and 1e-6 < t < 1.0 - 1e-6:
                            target = candidate
                            break
                    if target is not None:
                        geometry_mod.split_edge_at_point(bm, target, point)
            edit_context.commit(bm)
        except Exception:
            edit_context.abort(bm)
            raise
        undo_push("SketchUp Divide")
        return {"FINISHED"}


class SKETCHUP_OT_weld_edges(bpy.types.Operator):
    bl_idname = "sketchup.weld_edges"
    bl_label = "Weld Edges"
    bl_description = "Weld the selected edges into one curve entity."
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        edit_context = EditContext(context)
        bm = edit_context.begin()
        try:
            edges = _selected_edges(bm)
            if len(edges) < 2:
                self.report({"WARNING"}, "Select at least two edges to weld")
                edit_context.abort(bm)
                return {"CANCELLED"}
            record = {
                "type": "curve",
                "center": [0.0, 0.0, 0.0],
                "radius": 0.0,
                "segments": len(edges),
                "normal": [0.0, 0.0, 1.0],
                "start_angle": 0.0,
                "end_angle": 0.0,
                "closed": False,
            }
            curve_id = curve_mod.register_curve(edit_context.mesh, record)
            curve_mod.tag_edges(bm, edges, curve_id)
            edit_context.commit(bm)
        except Exception:
            edit_context.abort(bm)
            raise
        undo_push("SketchUp Weld Edges")
        return {"FINISHED"}


class SKETCHUP_OT_explode_curve(bpy.types.Operator):
    bl_idname = "sketchup.explode_curve"
    bl_label = "Explode Curve"
    bl_description = "Remove the curve entity, keeping its edges."
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        edit_context = EditContext(context)
        bm = edit_context.begin()
        try:
            edges = _selected_edges(bm)
            curve_ids = {
                curve_mod.curve_id_of(bm, edge) for edge in edges
            } - {0}
            if not curve_ids:
                self.report({"WARNING"}, "No curve selected")
                edit_context.abort(bm)
                return {"CANCELLED"}
            for curve_id in curve_ids:
                curve_mod.untag_edges(bm, curve_mod.edges_of_curve(bm, curve_id))
                curve_mod.remove_curve(edit_context.mesh, curve_id)
            edit_context.commit(bm)
        except Exception:
            edit_context.abort(bm)
            raise
        undo_push("SketchUp Explode Curve")
        return {"FINISHED"}


class SKETCHUP_OT_convert_to_polygon(bpy.types.Operator):
    bl_idname = "sketchup.convert_to_polygon"
    bl_label = "Convert to Polygon"
    bl_description = "Convert the selected circle/arc curve to a polygon."
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        edit_context = EditContext(context)
        bm = edit_context.begin()
        try:
            edges = _selected_edges(bm)
            curve_ids = {
                curve_mod.curve_id_of(bm, edge) for edge in edges
            } - {0}
            changed = False
            for curve_id in curve_ids:
                record = curve_mod.get_curve(edit_context.mesh, curve_id)
                if record is None or record.get("type") not in ("circle", "arc", "pie"):
                    continue
                record["type"] = "polygon"
                curve_mod.update_curve(edit_context.mesh, curve_id, record)
                for edge in curve_mod.edges_of_curve(bm, curve_id):
                    geometry_mod.set_edge_flags(bm, edge, soft=False)
                changed = True
            if not changed:
                self.report({"WARNING"}, "No circle/arc curve selected")
                edit_context.abort(bm)
                return {"CANCELLED"}
            edit_context.commit(bm)
        except Exception:
            edit_context.abort(bm)
            raise
        undo_push("SketchUp Convert to Polygon")
        return {"FINISHED"}


class SKETCHUP_OT_curve_edit(bpy.types.Operator):
    bl_idname = "sketchup.curve_edit"
    bl_label = "Edit Curve"
    bl_description = "Change the selected curve's radius and segment count."
    bl_options = {"REGISTER", "UNDO"}

    radius: bpy.props.FloatProperty(
        name="Radius", description="Curve radius in meters", default=1.0, min=0.001
    )
    segments: bpy.props.IntProperty(
        name="Segments", description="Number of segments", default=24, min=3, max=1000
    )

    def invoke(self, context, event):
        edit_context = EditContext(context)
        bm = edit_context.begin()
        try:
            edges = _selected_edges(bm)
            for edge in edges:
                curve_id = curve_mod.curve_id_of(bm, edge)
                record = curve_mod.get_curve(edit_context.mesh, curve_id) if curve_id else None
                if record is not None and record.get("radius", 0.0) > 0.0:
                    self.radius = record["radius"]
                    self.segments = record["segments"]
                    break
        finally:
            edit_context.abort(bm)
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        edit_context = EditContext(context)
        bm = edit_context.begin()
        try:
            edges = _selected_edges(bm)
            curve_ids = {
                curve_mod.curve_id_of(bm, edge) for edge in edges
            } - {0}
            rebuilt = False
            for curve_id in curve_ids:
                record = curve_mod.get_curve(edit_context.mesh, curve_id)
                if record is None or record.get("type") not in (
                    "circle",
                    "polygon",
                    "arc",
                    "pie",
                ):
                    continue
                self._rebuild(edit_context, bm, curve_id, record)
                rebuilt = True
            if not rebuilt:
                self.report({"WARNING"}, "No editable curve selected")
                edit_context.abort(bm)
                return {"CANCELLED"}
            edit_context.commit(bm)
        except Exception:
            edit_context.abort(bm)
            raise
        undo_push("SketchUp Edit Curve")
        return {"FINISHED"}

    def _rebuild(self, edit_context, bm, curve_id, record):
        # Delete the old curve edges (and dependent faces).
        geometry_mod.refresh(bm)
        for edge in list(curve_mod.edges_of_curve(bm, curve_id)):
            if edge.is_valid:
                geometry_mod.delete_edge(bm, edge, heal=False)
        curve_mod.remove_curve(edit_context.mesh, curve_id)
        # Re-apply with the new radius/segments.
        center = tuple(record["center"])
        normal = tuple(record["normal"])
        curve_type = record["type"]
        if curve_type in ("circle", "polygon"):
            points = curve_mod.circle_points(center, normal, self.radius, self.segments)
            closed = True
        else:
            points = curve_mod.arc_points(
                center,
                normal,
                self.radius,
                record["start_angle"],
                record["end_angle"],
                self.segments,
            )
            closed = curve_type == "pie"
            if closed:
                points = points + [center]
        new_record = dict(record)
        new_record["radius"] = self.radius
        new_record["segments"] = self.segments
        new_id = curve_mod.register_curve(edit_context.mesh, new_record)
        segments = list(zip(points, points[1:]))
        if closed and len(points) > 2:
            segments.append((points[-1], points[0]))
        committed = []
        for a, b in segments:
            local_a = edit_context.to_local(a)
            local_b = edit_context.to_local(b)
            geometry_mod.apply_line(bm, local_a, local_b)
            committed.append((local_a, local_b))
        geometry_mod.refresh(bm)
        layer = curve_mod.ensure_curve_layer(bm)
        for edge in bm.edges:
            for local_a, local_b in committed:
                v1, v2 = edge.verts
                if (
                    (v1.co - local_a).length <= 1e-6 and (v2.co - local_b).length <= 1e-6
                ) or (
                    (v1.co - local_b).length <= 1e-6 and (v2.co - local_a).length <= 1e-6
                ):
                    edge[layer] = new_id
                    if curve_type in ("circle", "arc", "pie"):
                        geometry_mod.set_edge_flags(bm, edge, soft=True)
                    break


CURVE_OPERATORS = [
    SKETCHUP_OT_divide_edge,
    SKETCHUP_OT_weld_edges,
    SKETCHUP_OT_explode_curve,
    SKETCHUP_OT_convert_to_polygon,
    SKETCHUP_OT_curve_edit,
]
