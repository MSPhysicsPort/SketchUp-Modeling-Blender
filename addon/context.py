"""Edit context: one SketchUp context = one Mesh Object (proposal §3).

Tools always edit the active context object through this helper. Two
paths (research/02 §10.3): in the GUI the object is put in Edit Mode
and edits go through ``bmesh.from_edit_mesh`` / ``update_edit_mesh``
(live viewport sync, BMesh BVH picking); headless / scripted use
goes through a standalone BMesh synced with ``from_mesh`` / ``to_mesh``.
Callers must pair ``begin()`` with ``commit()`` or ``abort()``.
"""

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

CONTEXT_OBJECT_NAME = "SketchUp Model"


def view_3d_override():
    """Context override dict pointing at a 3D view (for timer
    callbacks, which may fire without an area). Empty when no
    window/view is available (headless)."""
    try:
        window = bpy.context.window
        if window is None:
            return {}
        area = next(
            (a for a in window.screen.areas if a.type == "VIEW_3D"), None
        )
        if area is None:
            return {}
        region = next((r for r in area.regions if r.type == "WINDOW"), None)
        override = {"window": window, "area": area}
        if region is not None:
            override["region"] = region
        return override
    except Exception:
        return {}


class EditContext:
    def __init__(self, context):
        self.background = bpy.app.background or context.area is None
        self.object = self._ensure_object(context)
        self.mesh = self.object.data
        self._bvh = None
        self._bvh_version = -1
        self.version = 0
        if not self.background:
            self._ensure_edit_mode(context)

    def _ensure_object(self, context):
        obj = context.active_object
        if obj is not None and obj.type == "MESH":
            return obj
        mesh = bpy.data.meshes.new(CONTEXT_OBJECT_NAME)
        obj = bpy.data.objects.new(CONTEXT_OBJECT_NAME, mesh)
        from .data import materials as materials_mod

        mesh.materials.append(materials_mod.ensure_default_material())
        collection = context.collection
        collection.objects.link(obj)
        context.view_layer.objects.active = obj
        obj.select_set(True)
        return obj

    def _ensure_edit_mode(self, context):
        if context.active_object is not self.object:
            context.view_layer.objects.active = self.object
        if context.mode != "EDIT_MESH":
            bpy.ops.object.mode_set(mode="EDIT")

    # -- BMesh lifecycle -------------------------------------------------

    def _live_edit_bmesh(self):
        """True when the object is currently in Edit Mode: edits must
        go through the live edit bmesh, in the GUI and headless
        alike. Writing the standalone mesh copy while an edit
        bmesh is active would be overwritten when leaving Edit
        Mode (found by the 0.5.0 native-transform tests)."""
        try:
            return self.object.mode == "EDIT"
        except Exception:
            return False

    def begin(self):
        """Return a BMesh for reading/editing; pair with commit/abort."""
        if self._live_edit_bmesh():
            return bmesh.from_edit_mesh(self.mesh)
        bm = bmesh.new()
        bm.from_mesh(self.mesh)
        return bm

    def commit(self, bm):
        """Write the BMesh back and bump the version (invalidates BVH)."""
        if self._live_edit_bmesh():
            bmesh.update_edit_mesh(self.mesh)
        else:
            bm.to_mesh(self.mesh)
            bm.free()
        self.mesh.update()
        self.version += 1
        self._bvh = None

    def abort(self, bm):
        """Discard a BMesh obtained from begin() without writing."""
        if not self._live_edit_bmesh():
            bm.free()

    # -- Picking ---------------------------------------------------------

    def bvh(self, bm):
        """BVHTree over the BMesh (local coordinates), cached per version."""
        if self._bvh is None or self._bvh_version != self.version:
            self._bvh = BVHTree.FromBMesh(bm)
            self._bvh_version = self.version
        return self._bvh

    def ray_cast_face(self, bm, ray_origin_world, ray_dir_world):
        """Ray cast against the context mesh; returns
        (world_point, world_normal, face_index) or None."""
        matrix = self.object.matrix_world
        inv = matrix.inverted()
        origin = inv @ Vector(ray_origin_world)
        direction = (inv.to_3x3() @ Vector(ray_dir_world)).normalized()
        location, normal, index, _distance = self.bvh(bm).ray_cast(origin, direction)
        if location is None:
            return None
        world_point = matrix @ location
        world_normal = (matrix.to_3x3() @ normal).normalized()
        return (world_point, world_normal, index)

    # -- Coordinate conversion -------------------------------------------

    def to_world(self, co):
        return self.object.matrix_world @ Vector(co)

    def to_local(self, co):
        return self.object.matrix_world.inverted() @ Vector(co)


def undo_push(message):
    """Push one Undo step; guarded (headless/context failures ignored)."""
    try:
        bpy.ops.ed.undo_push(message=message)
    except Exception:
        pass
