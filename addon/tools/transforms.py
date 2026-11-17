"""Move / Rotate / Scale / Array: thin wrappers over Blender's
native transform operators (native-first, Sen 2026-11-17).

Rationale: Blender's own transform tools already provide the drag
interaction, axis constraints (X/Y/Z keys), numeric input and
snapping that SU users expect. Re-implementing them modally
duplicated Blender with worse feel and more bugs. These operators
therefore delegate:

- ``invoke()`` (keyboard / toolbar / menu): make sure a mesh is in
  Edit Mode, snapshot the selection (for the Array follow-up),
  duplicate first when Ctrl is held (SU copy), place the 3D cursor
  at the selection center for Rotate/Scale, then hand over to
  ``transform.translate`` / ``transform.rotate`` /
  ``transform.resize`` with SU snapping properties. The native
  modal operator owns the interaction; this operator returns
  FINISHED once delegation is done.
- ``execute()`` (scripted / tests): the same steps with explicit
  value properties, calling the native operators in EXEC mode.

SU behaviors layered on top of the native tools:

- Snapping: vertex / edge / edge-midpoint / face / face-center snap
  with CLOSEST target (SU inference equivalents available in
  Blender's snap system). SU Mode also configures the same snap in
  the tool settings, so the snap stays on for every native tool.
- Copy: Ctrl at invoke duplicates the selection first (like
  Blender's Shift+D), then the native move/rotate/scale moves the
  copy.
- Pivot: Rotate/Scale pivot at the selection center via the 3D
  cursor (SU Mode sets the pivot point to CURSOR); the wrappers
  place the cursor at the selection center before delegating.
- Array: ``sketchup.array_repeat`` replays the last copy-move or
  copy-rotate N times (``3x`` external / ``/3`` internal). The
  move vector is derived from the snapshot vs. the current
  selection; a rotate array needs the angle typed in its dialog,
  because the interactive native rotate does not report its angle
  back (honest limitation, documented in the test notes).

The old custom modal Move/Rotate/Scale implementations (0.4.0)
were replaced wholesale by this delegation; the snapshot and
matrix math in ``core.transform`` is reused for copy/array.
"""

import math

import bpy
from mathutils import Matrix, Vector

from ..context import EditContext, undo_push
from ..core.transform import (
    bbox_of_points,
    capture_snapshot,
    duplicate_snapshot,
    rotation_matrix,
    selection_vert_indices,
)
from ..i18n.translations import translate as _T

# Snap properties passed to the native transform operators. These
# mirror the SU Mode tool-settings snap (mode.py); passing them
# explicitly also covers use outside SU Mode.
SNAP_PROPS = {
    "snap": True,
    "snap_elements": {"VERTEX", "EDGE", "EDGE_MIDPOINT", "FACE", "FACE_MIDPOINT"},
    "snap_target": "CLOSEST",
}

# Last transform, for sketchup.array_repeat. Session-scoped:
# {"kind", "object", "snapshot", "center", "copied", "angle", "axis"}.
_LAST_OP = None


def _ensure_edit_mesh(context):
    """Active mesh object in Edit Mode (creates SketchUp Model when
    no mesh is active). Returns the object."""
    obj = context.active_object
    if obj is None or obj.type != "MESH":
        obj = EditContext(context).object
    if getattr(context, "mode", None) != "EDIT_MESH":
        try:
            bpy.ops.object.mode_set(mode="EDIT")
        except Exception:
            pass
    return obj


def _selection_info(context):
    """(snapshot, local_center, edit_context) for the current
    selection, or None when nothing is selected."""
    edit_context = EditContext(context)
    bm = edit_context.begin()
    try:
        indices = selection_vert_indices(bm)
        if not indices:
            return None
        snapshot = capture_snapshot(bm, indices)
        points = [Vector(co) for co in snapshot.verts.values()]
        low, high = bbox_of_points(points)
        center = (low + high) * 0.5
        return snapshot, center, edit_context
    finally:
        edit_context.abort(bm)


def _record_last_op(context, kind, copied, angle=None, axis="Z"):
    """Snapshot the selection before the transform for Array."""
    global _LAST_OP
    info = _selection_info(context)
    if info is None:
        _LAST_OP = None
        return None
    snapshot, center, edit_context = info
    _LAST_OP = {
        "kind": kind,
        "object": edit_context.object.name,
        "snapshot": snapshot,
        "center": center.copy(),
        "copied": bool(copied),
        "angle": angle,
        "axis": axis,
    }
    return _LAST_OP


def _place_cursor_at_selection(context):
    """Move the 3D cursor to the selection center (world coords).

    Returns the world center, or None when nothing is selected.
    """
    info = _selection_info(context)
    if info is None:
        return None
    _snapshot, center, edit_context = info
    world_center = edit_context.to_world(center)
    try:
        context.scene.cursor.location = world_center
    except Exception:
        pass
    return world_center


def _delegate(operator, **kwargs):
    """Call a native transform operator with INVOKE_DEFAULT.

    Falls back to a plain call when a property is unknown to this
    Blender version (snap properties exist since 2.8, but never
    fail the tool over them).
    """
    try:
        return operator("INVOKE_DEFAULT", **kwargs)
    except TypeError:
        return operator("INVOKE_DEFAULT")


def _has_selection(context):
    return _selection_info(context) is not None


class SKETCHUP_OT_tool_move(bpy.types.Operator):
    bl_idname = "sketchup.tool_move"
    bl_label = "Move"
    bl_description = "Move the selection with Blender's Move tool and SketchUp snapping (Ctrl = copy)."
    bl_options = {"REGISTER"}  # native ops / undo_push own the Undo step

    vector: bpy.props.FloatVectorProperty(
        name="Vector",
        description="Move offset in meters (execute path)",
        default=(0.0, 0.0, 0.0),
        subtype="TRANSLATION",
    )
    copy: bpy.props.BoolProperty(
        name="Copy",
        description="Duplicate the selection before moving",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return context.area is None or context.area.type == "VIEW_3D"

    def invoke(self, context, event):
        _ensure_edit_mesh(context)
        if not _has_selection(context):
            self.report({"WARNING"}, _T("Select something to move first"))
            return {"CANCELLED"}
        copied = bool(event.ctrl)
        _record_last_op(context, "move", copied)
        if copied:
            bpy.ops.mesh.duplicate()
        _delegate(bpy.ops.transform.translate, **SNAP_PROPS)
        return {"FINISHED"}

    def execute(self, context):
        _ensure_edit_mesh(context)
        if not _has_selection(context):
            self.report({"WARNING"}, _T("Select something to move first"))
            return {"CANCELLED"}
        _record_last_op(context, "move", self.copy)
        if self.copy:
            bpy.ops.mesh.duplicate()
        bpy.ops.transform.translate(value=self.vector)
        return {"FINISHED"}


class SKETCHUP_OT_tool_rotate(bpy.types.Operator):
    bl_idname = "sketchup.tool_rotate"
    bl_label = "Rotate"
    bl_description = "Rotate the selection with Blender's Rotate tool about the selection center (Ctrl = copy)."
    bl_options = {"REGISTER"}  # native ops / undo_push own the Undo step

    angle: bpy.props.FloatProperty(
        name="Angle",
        description="Rotation angle in degrees (execute path)",
        default=0.0,
        subtype="ANGLE",
    )
    axis: bpy.props.EnumProperty(
        name="Axis",
        description="Rotation axis (execute path)",
        items=[
            ("X", "X", "Global X axis"),
            ("Y", "Y", "Global Y axis"),
            ("Z", "Z", "Global Z axis"),
        ],
        default="Z",
    )
    copy: bpy.props.BoolProperty(
        name="Copy",
        description="Duplicate the selection before rotating",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return context.area is None or context.area.type == "VIEW_3D"

    def invoke(self, context, event):
        _ensure_edit_mesh(context)
        if not _has_selection(context):
            self.report({"WARNING"}, _T("Select something to rotate first"))
            return {"CANCELLED"}
        copied = bool(event.ctrl)
        _record_last_op(context, "rotate", copied)
        if copied:
            bpy.ops.mesh.duplicate()
        _place_cursor_at_selection(context)
        _delegate(bpy.ops.transform.rotate, **SNAP_PROPS)
        return {"FINISHED"}

    def execute(self, context):
        _ensure_edit_mesh(context)
        if not _has_selection(context):
            self.report({"WARNING"}, _T("Select something to rotate first"))
            return {"CANCELLED"}
        _record_last_op(context, "rotate", self.copy, angle=self.angle, axis=self.axis)
        if self.copy:
            bpy.ops.mesh.duplicate()
        center = _place_cursor_at_selection(context)
        kwargs = {
            "value": math.radians(self.angle),
            "orient_axis": self.axis,
            "orient_type": "GLOBAL",
        }
        if center is not None:
            # center_override is in world coordinates; the SketchUp
            # Model object stays at identity, so local == world.
            kwargs["center_override"] = center
        bpy.ops.transform.rotate(**kwargs)
        return {"FINISHED"}


class SKETCHUP_OT_tool_scale(bpy.types.Operator):
    bl_idname = "sketchup.tool_scale"
    bl_label = "Scale"
    bl_description = "Scale the selection with Blender's Scale tool about the selection center."
    bl_options = {"REGISTER"}  # native ops / undo_push own the Undo step

    factors: bpy.props.FloatVectorProperty(
        name="Factors",
        description="Scale factors (execute path)",
        default=(1.0, 1.0, 1.0),
        subtype="XYZ",
    )

    @classmethod
    def poll(cls, context):
        return context.area is None or context.area.type == "VIEW_3D"

    def invoke(self, context, event):
        _ensure_edit_mesh(context)
        if not _has_selection(context):
            self.report({"WARNING"}, _T("Select something to scale first"))
            return {"CANCELLED"}
        _record_last_op(context, "scale", False)
        _place_cursor_at_selection(context)
        _delegate(bpy.ops.transform.resize, **SNAP_PROPS)
        return {"FINISHED"}

    def execute(self, context):
        _ensure_edit_mesh(context)
        if not _has_selection(context):
            self.report({"WARNING"}, _T("Select something to scale first"))
            return {"CANCELLED"}
        _record_last_op(context, "scale", False)
        center = _place_cursor_at_selection(context)
        kwargs = {"value": self.factors}
        if center is not None:
            kwargs["center_override"] = center
        bpy.ops.transform.resize(**kwargs)
        return {"FINISHED"}


class SKETCHUP_OT_array_repeat(bpy.types.Operator):
    bl_idname = "sketchup.array_repeat"
    bl_label = "Repeat Array"
    bl_description = "Repeat the last copy-move or copy-rotate as an array (3x external, /3 internal)."
    bl_options = {"REGISTER"}  # native ops / undo_push own the Undo step

    count: bpy.props.IntProperty(
        name="Count",
        description="Number of copies in the array (the manual copy counts as the first)",
        default=3,
        min=1,
    )
    internal: bpy.props.BoolProperty(
        name="Internal",
        description="Place copies between the original and the manual copy (/N instead of Nx)",
        default=False,
    )
    angle: bpy.props.FloatProperty(
        name="Angle",
        description="Rotation angle in degrees (rotate arrays only; type the angle used)",
        default=0.0,
        subtype="ANGLE",
    )
    axis: bpy.props.EnumProperty(
        name="Axis",
        description="Rotation axis (rotate arrays only)",
        items=[
            ("X", "X", "Global X axis"),
            ("Y", "Y", "Global Y axis"),
            ("Z", "Z", "Global Z axis"),
        ],
        default="Z",
    )

    @classmethod
    def poll(cls, context):
        return context.area is None or context.area.type == "VIEW_3D"

    def invoke(self, context, event):
        # Prefill the dialog from the last executed rotate, if any.
        if _LAST_OP is not None and _LAST_OP["kind"] == "rotate":
            if _LAST_OP.get("angle") is not None:
                self.angle = _LAST_OP["angle"]
            self.axis = _LAST_OP.get("axis", "Z")
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if _LAST_OP is None:
            self.report({"WARNING"}, _T("Arrays need a copy-move first"))
            return {"CANCELLED"}
        kind = _LAST_OP["kind"]
        if kind not in ("move", "rotate"):
            self.report({"WARNING"}, _T("Arrays need a copy-move first"))
            return {"CANCELLED"}
        if not _LAST_OP["copied"]:
            if kind == "move":
                self.report({"WARNING"}, _T("Arrays need a copy-move first"))
            else:
                self.report({"WARNING"}, _T("Arrays need a copy-rotate first"))
            return {"CANCELLED"}
        obj = bpy.data.objects.get(_LAST_OP["object"])
        if obj is None or obj.type != "MESH":
            self.report({"WARNING"}, _T("Arrays need a copy-move first"))
            return {"CANCELLED"}
        try:
            context.view_layer.objects.active = obj
            obj.select_set(True)
        except Exception:
            pass
        _ensure_edit_mesh(context)
        edit_context = EditContext(context)
        snapshot = _LAST_OP["snapshot"]
        bm = edit_context.begin()
        try:
            if kind == "move":
                matrices = self._move_matrices(bm, snapshot)
            else:
                matrices = self._rotate_matrices(snapshot)
            if matrices is None:
                return {"CANCELLED"}
            for matrix in matrices:
                duplicate_snapshot(bm, snapshot, matrix)
        finally:
            edit_context.commit(bm)
        undo_push("SketchUp Array")
        return {"FINISHED"}

    def _move_matrices(self, bm, snapshot):
        """Matrices for the additional copies of a copy-move array."""
        indices = selection_vert_indices(bm)
        if not indices:
            self.report({"WARNING"}, _T("Arrays need a copy-move first"))
            return None
        current = [bm.verts[i].co for i in indices if i < len(bm.verts)]
        if not current:
            self.report({"WARNING"}, _T("Arrays need a copy-move first"))
            return None
        low, high = bbox_of_points(current)
        current_center = (low + high) * 0.5
        snap_points = [Vector(co) for co in snapshot.verts.values()]
        slow, shigh = bbox_of_points(snap_points)
        snap_center = (slow + shigh) * 0.5
        delta = current_center - snap_center
        if delta.length < 1e-9:
            self.report({"WARNING"}, _T("Move first, then type a distance"))
            return None
        matrices = []
        if self.internal:
            for i in range(1, self.count + 1):
                factor = i / (self.count + 1.0)
                matrices.append(Matrix.Translation(delta * factor))
        else:
            # The manual copy is copy #1; add copies #2..#N.
            for i in range(2, self.count + 1):
                matrices.append(Matrix.Translation(delta * i))
        return matrices

    def _rotate_matrices(self, snapshot):
        """Matrices for the additional copies of a copy-rotate array."""
        angle = self.angle
        if abs(angle) < 1e-9:
            self.report({"WARNING"}, _T("Arrays need a copy-rotate first"))
            return None
        axis_map = {"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}
        axis = Vector(axis_map[self.axis])
        center = _LAST_OP["center"]
        matrices = []
        if self.internal:
            for i in range(1, self.count + 1):
                factor = i / (self.count + 1.0)
                matrices.append(rotation_matrix(center, axis, angle * factor))
        else:
            for i in range(2, self.count + 1):
                matrices.append(rotation_matrix(center, axis, angle * i))
        return matrices


TRANSFORM_OPERATORS = [
    SKETCHUP_OT_tool_move,
    SKETCHUP_OT_tool_rotate,
    SKETCHUP_OT_tool_scale,
    SKETCHUP_OT_array_repeat,
]
