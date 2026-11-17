"""Edit-menu one-shot commands (proposal §3.4, §3.6, P4): Intersect
Faces, Soften Edges, Hide / Unhide, and the Hidden Geometry and
Back Edges view toggles.
"""

import math

import bpy

from ..context import EditContext, undo_push
from ..core import geometry as geometry_mod
from ..core import intersect as intersect_mod
from ..core.state import get_session
from ..i18n.translations import translate as _T


def _edit_context_or_report(operator, context):
    if context.mode != "EDIT_MESH":
        operator.report({"WARNING"}, _T("Enter SU Mode first"))
        return None
    try:
        return EditContext(context)
    except Exception:
        operator.report({"WARNING"}, _T("Enter SU Mode first"))
        return None


class SKETCHUP_OT_intersect_faces(bpy.types.Operator):
    bl_idname = "sketchup.intersect_faces"
    bl_label = "Intersect Faces"
    bl_description = "Intersect selected faces with the model, context, or selection"
    bl_options = {"REGISTER", "UNDO"}

    scope: bpy.props.EnumProperty(
        name="Scope",
        items=[
            ("SELECTION", "With Selection", ""),
            ("CONTEXT", "With Context", ""),
            ("MODEL", "With Model", ""),
        ],
        default="CONTEXT",
    )

    def execute(self, context):
        edit = _edit_context_or_report(self, context)
        if edit is None:
            return {"CANCELLED"}
        bm = edit.begin()
        try:
            geometry_mod.refresh(bm)
            targets = [f.index for f in bm.faces if f.select]
            if not targets:
                edit.abort(bm)
                self.report({"WARNING"}, _T("Select faces to intersect first"))
                return {"CANCELLED"}
            count = intersect_mod.intersect_in_bmesh(
                bm, targets, self.scope, edit.object
            )
            edit.commit(bm)
        except Exception:
            edit.abort(bm)
            raise
        undo_push("SketchUp Intersect Faces")
        self.report({"INFO"}, _T("Intersect Faces: %d edges added") % count)
        return {"FINISHED"}


class SKETCHUP_OT_soften_edges(bpy.types.Operator):
    bl_idname = "sketchup.soften_edges"
    bl_label = "Soften Edges"
    bl_description = "Soften and smooth edges below an angle threshold"
    bl_options = {"REGISTER", "UNDO"}

    angle: bpy.props.FloatProperty(
        name="Angle",
        description="Soften edges whose dihedral angle is below this",
        default=math.radians(20.0),
        subtype="ANGLE",
        min=0.0,
        max=math.radians(180.0),
    )
    smooth_normals: bpy.props.BoolProperty(
        name="Smooth Normals", default=True
    )
    soften_coplanar: bpy.props.BoolProperty(
        name="Soften Coplanar", default=True
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        edit = _edit_context_or_report(self, context)
        if edit is None:
            return {"CANCELLED"}
        bm = edit.begin()
        try:
            geometry_mod.refresh(bm)
            selected = [e.index for e in bm.edges if e.select]
            indices = selected if selected else [e.index for e in bm.edges]
            softened = 0
            for index in indices:
                # Re-fetch per edge: set_edge_flags refreshes the
                # bmesh, invalidating wrappers held across calls.
                edge = bm.edges[index]
                faces = edge.link_faces
                if len(faces) != 2:
                    continue
                angle = faces[0].normal.angle(faces[1].normal)
                soft = angle <= self.angle and (
                    self.soften_coplanar or angle > 1e-6
                )
                geometry_mod.set_edge_flags(bm, edge, soft=soft)
                bm.edges[index].smooth = bool(soft and self.smooth_normals)
                if soft:
                    softened += 1
            edit.commit(bm)
        except Exception:
            edit.abort(bm)
            raise
        undo_push("SketchUp Soften Edges")
        self.report({"INFO"}, _T("Softened %d edges") % softened)
        return {"FINISHED"}


class SKETCHUP_OT_toggle_hidden_geometry(bpy.types.Operator):
    bl_idname = "sketchup.toggle_hidden_geometry"
    bl_label = "Hidden Geometry"
    bl_description = "Show hidden edges as dashed lines"
    bl_options = {"REGISTER"}

    def execute(self, context):
        session = get_session()
        session.show_hidden_geometry = not session.show_hidden_geometry
        state = _T("on") if session.show_hidden_geometry else _T("off")
        self.report({"INFO"}, _T("Hidden Geometry: %s") % state)
        return {"FINISHED"}


class SKETCHUP_OT_toggle_back_edges(bpy.types.Operator):
    bl_idname = "sketchup.toggle_back_edges"
    bl_label = "Back Edges"
    bl_description = "Show edges behind faces as dashed lines (K)"
    bl_options = {"REGISTER"}

    def execute(self, context):
        session = get_session()
        session.show_back_edges = not session.show_back_edges
        state = _T("on") if session.show_back_edges else _T("off")
        self.report({"INFO"}, _T("Back Edges: %s") % state)
        return {"FINISHED"}


def _face_key(face):
    return tuple(sorted((round(v.co.x, 6), round(v.co.y, 6), round(v.co.z, 6))
                        for v in face.verts))


def _edge_key(edge):
    return tuple(sorted((round(v.co.x, 6), round(v.co.y, 6), round(v.co.z, 6))
                        for v in edge.verts))


def _unhide_keys_in_bmesh(bm, face_keys, edge_keys):
    face_set = {frozenset(k) for k in face_keys}
    edge_set = {frozenset(k) for k in edge_keys}
    # Indices + re-fetch: set_edge_flags refreshes the bmesh.
    face_indices = [f.index for f in bm.faces]
    for index in face_indices:
        face = bm.faces[index]
        if frozenset(_face_key(face)) in face_set:
            face.hide_set(False)
    edge_indices = [e.index for e in bm.edges]
    for index in edge_indices:
        edge = bm.edges[index]
        if frozenset(_edge_key(edge)) in edge_set:
            geometry_mod.set_edge_flags(bm, edge, hidden=False)


def _unhide_mesh_entry(entry, context):
    """Apply a mesh hide batch on its object, live when it is the
    edit object, standalone otherwise."""
    import bmesh

    obj = bpy.data.objects.get(entry["object"])
    if obj is None or obj.type != "MESH":
        return
    if context.mode == "EDIT_MESH" and context.active_object is obj:
        edit = EditContext(context)
        bm = edit.begin()
        try:
            geometry_mod.refresh(bm)
            _unhide_keys_in_bmesh(bm, entry["faces"], entry["edges"])
            edit.commit(bm)
        except Exception:
            edit.abort(bm)
            raise
        return
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        geometry_mod.refresh(bm)
        _unhide_keys_in_bmesh(bm, entry["faces"], entry["edges"])
        bm.to_mesh(obj.data)
    finally:
        bm.free()


def _unhide_entry(entry, context):
    if entry["kind"] == "objects":
        for name in entry["names"]:
            obj = bpy.data.objects.get(name)
            if obj is not None:
                obj.hide_viewport = False
    else:
        _unhide_mesh_entry(entry, context)


class SKETCHUP_OT_hide(bpy.types.Operator):
    bl_idname = "sketchup.hide"
    bl_label = "Hide"
    bl_description = "Hide the selection"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        session = get_session()
        if context.mode != "EDIT_MESH":
            targets = [o for o in context.selected_objects]
            if not targets:
                self.report({"WARNING"}, _T("Select something to hide first"))
                return {"CANCELLED"}
            for obj in targets:
                obj.hide_viewport = True
            session.hidden_history.append(
                {"kind": "objects", "names": [o.name for o in targets]}
            )
            undo_push("SketchUp Hide")
            return {"FINISHED"}
        edit = _edit_context_or_report(self, context)
        if edit is None:
            return {"CANCELLED"}
        bm = edit.begin()
        try:
            geometry_mod.refresh(bm)
            faces = [f for f in bm.faces if f.select]
            edges = [e for e in bm.edges if e.select]
            if not faces and not edges:
                edit.abort(bm)
                self.report({"WARNING"}, _T("Select something to hide first"))
                return {"CANCELLED"}
            entry = {
                "kind": "mesh",
                "object": edit.object.name,
                "faces": [_face_key(f) for f in faces],
                "edges": [_edge_key(e) for e in edges],
            }
            for face in faces:
                face.hide_set(True)
            for edge in edges:
                geometry_mod.set_edge_flags(bm, edge, hidden=True)
            edit.commit(bm)
        except Exception:
            edit.abort(bm)
            raise
        session.hidden_history.append(entry)
        undo_push("SketchUp Hide")
        return {"FINISHED"}


def _unhide_batch(bm, batch):
    """Back-compat shim: old tuple batches (faces, edges)."""
    if isinstance(batch, dict):
        _unhide_keys_in_bmesh(bm, batch["faces"], batch["edges"])
    else:
        _unhide_keys_in_bmesh(bm, batch[0], batch[1])


class SKETCHUP_OT_unhide_all(bpy.types.Operator):
    bl_idname = "sketchup.unhide_all"
    bl_label = "Unhide All"
    bl_description = "Show all hidden geometry"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        import bmesh

        session = get_session()
        if context.mode == "EDIT_MESH":
            edit = _edit_context_or_report(self, context)
            if edit is None:
                return {"CANCELLED"}
            bm = edit.begin()
            try:
                geometry_mod.refresh(bm)
                for face in bm.faces:
                    face.hide_set(False)
                for index in [e.index for e in bm.edges]:
                    edge = bm.edges[index]
                    if geometry_mod.is_hidden_edge(bm, edge):
                        geometry_mod.set_edge_flags(bm, edge, hidden=False)
                edit.commit(bm)
            except Exception:
                edit.abort(bm)
                raise
        else:
            for obj in bpy.data.objects:
                if obj.type != "MESH":
                    continue
                bm = bmesh.new()
                try:
                    bm.from_mesh(obj.data)
                    geometry_mod.refresh(bm)
                    for face in bm.faces:
                        face.hide_set(False)
                    for index in [e.index for e in bm.edges]:
                        edge = bm.edges[index]
                        if geometry_mod.is_hidden_edge(bm, edge):
                            geometry_mod.set_edge_flags(bm, edge, hidden=False)
                    bm.to_mesh(obj.data)
                finally:
                    bm.free()
        for entry in session.hidden_history:
            if entry["kind"] == "objects":
                for name in entry["names"]:
                    obj = bpy.data.objects.get(name)
                    if obj is not None:
                        obj.hide_viewport = False
        session.hidden_history.clear()
        undo_push("SketchUp Unhide")
        return {"FINISHED"}


class SKETCHUP_OT_unhide_last(bpy.types.Operator):
    bl_idname = "sketchup.unhide_last"
    bl_label = "Unhide Last"
    bl_description = "Show the most recently hidden geometry"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        session = get_session()
        if not session.hidden_history:
            self.report({"WARNING"}, _T("Nothing hidden"))
            return {"CANCELLED"}
        entry = session.hidden_history[-1]
        _unhide_entry(entry, context)
        session.hidden_history.pop()
        undo_push("SketchUp Unhide")
        return {"FINISHED"}


def _apply_selection_action(context, action):
    """Mode-aware select-all/deselect/invert (Edit menu)."""
    if context.mode == "EDIT_MESH":
        bpy.ops.mesh.select_all(action=action)
    else:
        if action == "SELECT":
            bpy.ops.object.select_all(action="SELECT")
        elif action == "DESELECT":
            bpy.ops.object.select_all(action="DESELECT")
        else:
            bpy.ops.object.select_all(action="INVERT")


class SKETCHUP_OT_select_all(bpy.types.Operator):
    bl_idname = "sketchup.select_all"
    bl_label = "Select All"
    bl_description = "Select everything in the current context"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _apply_selection_action(context, "SELECT")
        return {"FINISHED"}


class SKETCHUP_OT_deselect_all(bpy.types.Operator):
    bl_idname = "sketchup.deselect_all"
    bl_label = "Deselect All"
    bl_description = "Clear the selection"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _apply_selection_action(context, "DESELECT")
        return {"FINISHED"}


class SKETCHUP_OT_invert_selection(bpy.types.Operator):
    bl_idname = "sketchup.invert_selection"
    bl_label = "Invert Selection"
    bl_description = "Invert the current selection"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _apply_selection_action(context, "INVERT")
        return {"FINISHED"}


EDIT_OPERATORS = [
    SKETCHUP_OT_intersect_faces,
    SKETCHUP_OT_soften_edges,
    SKETCHUP_OT_toggle_hidden_geometry,
    SKETCHUP_OT_toggle_back_edges,
    SKETCHUP_OT_hide,
    SKETCHUP_OT_unhide_all,
    SKETCHUP_OT_unhide_last,
    SKETCHUP_OT_select_all,
    SKETCHUP_OT_deselect_all,
    SKETCHUP_OT_invert_selection,
]
