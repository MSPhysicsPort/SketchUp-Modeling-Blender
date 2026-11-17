"""Paint Bucket tool: click to paint faces with the active
material. Alt samples the clicked face's material. The replace
mode (Face / Connected / All Matching / Object) comes from the
Materials panel.
"""

import bpy

from ..context import undo_push
from ..core import geometry as geometry_mod
from ..data import materials as materials_mod
from ..i18n.translations import translate as _T
from .base import SketchUpToolBase


class SKETCHUP_OT_tool_paint_bucket(SketchUpToolBase):
    bl_idname = "sketchup.tool_paint_bucket"
    bl_label = "Paint Bucket"
    bl_description = "Paint faces with the active material (Alt samples)."
    vcb_kind = None

    def on_setup(self, context, event):
        material = materials_mod.get_active_material(context.scene)
        if "su_texture_size" not in material:
            material["su_texture_size"] = 1.0
        self.overlay.set_screentip(
            _T("Click a face to paint: %s") % material.name, (20, 60)
        )

    def on_left_press(self, context, event):
        picked = self.pick_at(context, event)
        if picked is None or picked[0] != "face":
            return None
        face_index = picked[1]
        scene = context.scene
        if event.alt:
            bm = self.edit_context.begin()
            try:
                geometry_mod.refresh(bm)
                face = bm.faces[face_index]
                mesh = self.edit_context.mesh
                if face.material_index < len(mesh.materials):
                    sampled = mesh.materials[face.material_index]
                    if sampled is not None:
                        materials_mod.set_active_material(scene, sampled)
                        self.report(
                            {"INFO"}, _T("Sampled: %s") % sampled.name
                        )
            finally:
                self.edit_context.abort(bm)
            return None
        material = materials_mod.get_active_material(scene)
        mode = scene.su_paint_mode
        bm = self.edit_context.begin()
        try:
            geometry_mod.refresh(bm)
            if mode == "CONNECTED":
                targets = materials_mod.connected_same_material_faces(
                    bm, face_index
                )
            elif mode == "ALL":
                targets = materials_mod.all_same_material_faces(bm, face_index)
            elif mode == "OBJECT":
                targets = [f.index for f in bm.faces]
            else:
                targets = [face_index]
            materials_mod.assign_material(
                bm, targets, material, self.edit_context.mesh
            )
            if materials_mod.has_image_texture(material):
                materials_mod.apply_true_size_uv(
                    bm, targets, materials_mod.material_texture_size(material)
                )
            self.edit_context.commit(bm)
        except Exception:
            self.edit_context.abort(bm)
            raise
        if mode == "OBJECT":
            self.edit_context.object["su_material"] = material.name
        undo_push("SketchUp Paint Bucket")
        return None


PAINT_TOOL_OPERATORS = [SKETCHUP_OT_tool_paint_bucket]
