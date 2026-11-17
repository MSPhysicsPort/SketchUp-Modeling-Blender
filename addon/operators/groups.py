"""Group / Component commands (proposal §3.6).

Edit-mode path: the selected mesh elements move into a new container
object parented to the edited context. Object-mode path: whole
selected objects are grouped under a shell, or merged into one
component object. All commands are single Undo steps.
"""

import bpy

from ..context import EditContext, undo_push
from ..core import containers
from ..i18n.translations import translate as _T


def _unique_object_name(base):
    if base not in bpy.data.objects:
        return base
    index = 1
    while "%s.%03d" % (base, index) in bpy.data.objects:
        index += 1
    return "%s.%03d" % (base, index)


def _edit_selection_to_container(context, name, kind):
    edit = EditContext(context)
    bm = edit.begin()
    try:
        new_obj = containers.extract_selection_to_object(
            bm, edit.object, name, kind
        )
        if new_obj is None:
            edit.abort(bm)
            return None
        edit.commit(bm)
    except Exception:
        edit.abort(bm)
        raise
    return new_obj


class SKETCHUP_OT_make_group(bpy.types.Operator):
    bl_idname = "sketchup.make_group"
    bl_label = "Make Group"
    bl_description = "Group the selection so it no longer sticks to other geometry"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.mode == "EDIT_MESH":
            new_obj = _edit_selection_to_container(
                context, _unique_object_name("Group"), containers.KIND_GROUP
            )
            if new_obj is None:
                self.report({"WARNING"}, _T("Select something to group first"))
                return {"CANCELLED"}
        else:
            selected = [o for o in context.selected_objects if o.type == "MESH"]
            if not selected:
                self.report({"WARNING"}, _T("Select something to group first"))
                return {"CANCELLED"}
            new_obj = containers.make_group_from_objects(
                selected, _unique_object_name("Group")
            )
        undo_push("SketchUp Make Group")
        self.report({"INFO"}, _T("Group created: %s") % new_obj.name)
        return {"FINISHED"}


class SKETCHUP_OT_make_component(bpy.types.Operator):
    bl_idname = "sketchup.make_component"
    bl_label = "Make Component"
    bl_description = "Create a component definition from the selection"
    bl_options = {"REGISTER", "UNDO"}

    name: bpy.props.StringProperty(name="Name", default="Component")
    description: bpy.props.StringProperty(name="Description", default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        name = self.name.strip() or "Component"
        name = containers._unique_definition_name(name)
        if context.mode == "EDIT_MESH":
            new_obj = _edit_selection_to_container(
                context, name, containers.KIND_COMPONENT
            )
            if new_obj is None:
                self.report({"WARNING"}, _T("Select something to make a component first"))
                return {"CANCELLED"}
        else:
            selected = [o for o in context.selected_objects if o.type == "MESH"]
            if not selected:
                self.report({"WARNING"}, _T("Select something to make a component first"))
                return {"CANCELLED"}
            new_obj = self._merge_objects(context, selected, name)
        if self.description:
            new_obj.data[containers.PROP_DESC] = self.description
        undo_push("SketchUp Make Component")
        self.report({"INFO"}, _T("Component created: %s") % name)
        return {"FINISHED"}

    def _merge_objects(self, context, objects, name):
        """Merge whole objects into one component object (world frame)."""
        mesh = bpy.data.meshes.new(name)
        target = bpy.data.objects.new(name, mesh)
        context.collection.objects.link(target)
        for obj in objects:
            containers.append_mesh_into(target, obj.data, obj.matrix_world.copy())
            bpy.data.objects.remove(obj, do_unlink=True)
        target[containers.PROP_KIND] = containers.KIND_COMPONENT
        mesh[containers.PROP_COMPONENT] = True
        mesh[containers.PROP_DEF] = name
        mesh.use_fake_user = True
        return target


class SKETCHUP_OT_explode(bpy.types.Operator):
    bl_idname = "sketchup.explode"
    bl_label = "Explode"
    bl_description = "Explode the selected group/component back into its parent context"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        exploded = 0
        if context.mode == "EDIT_MESH":
            current = context.active_object
            if current is not None and containers.is_container(current):
                stack = containers.context_stack()
                parent = None
                if len(stack) > 1:
                    parent = bpy.data.objects.get(stack[-2])
                if parent is None:
                    parent = current.parent
                if parent is not None and parent.type == "MESH":
                    containers.close_context(context)
                    if containers.explode_object(context, current, parent):
                        exploded += 1
        else:
            for obj in list(context.selected_objects):
                if not containers.is_container(obj):
                    continue
                parent = obj.parent
                if parent is None or parent.type != "MESH":
                    parent = self._root_object(context)
                if parent is not None and containers.explode_object(
                    context, obj, parent
                ):
                    exploded += 1
        if not exploded:
            self.report({"WARNING"}, _T("Select a group or component to explode"))
            return {"CANCELLED"}
        undo_push("SketchUp Explode")
        return {"FINISHED"}

    def _root_object(self, context):
        root = bpy.data.objects.get("SketchUp Model")
        if root is not None:
            return root
        for obj in context.scene.objects:
            if obj.type == "MESH" and not containers.is_container(obj):
                return obj
        mesh = bpy.data.meshes.new("SketchUp Model")
        root = bpy.data.objects.new("SketchUp Model", mesh)
        context.collection.objects.link(root)
        return root


class SKETCHUP_OT_make_unique(bpy.types.Operator):
    bl_idname = "sketchup.make_unique"
    bl_label = "Make Unique"
    bl_description = "Detach the selected component instances from their definition"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if containers.is_component(obj) and containers.make_unique(obj):
                count += 1
        if not count:
            self.report({"WARNING"}, _T("Select a component instance first"))
            return {"CANCELLED"}
        undo_push("SketchUp Make Unique")
        return {"FINISHED"}


class SKETCHUP_OT_convert_to_component(bpy.types.Operator):
    bl_idname = "sketchup.convert_to_component"
    bl_label = "Make Component"
    bl_description = "Convert the selected groups into components"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if containers.is_group(obj) and obj.type == "MESH":
                obj[containers.PROP_KIND] = containers.KIND_COMPONENT
                obj.data[containers.PROP_COMPONENT] = True
                obj.data[containers.PROP_DEF] = containers._unique_definition_name(
                    obj.name
                )
                obj.data.use_fake_user = True
                count += 1
        if not count:
            self.report({"WARNING"}, _T("Select a group first"))
            return {"CANCELLED"}
        undo_push("SketchUp Make Component")
        return {"FINISHED"}


class SKETCHUP_OT_convert_to_group(bpy.types.Operator):
    bl_idname = "sketchup.convert_to_group"
    bl_label = "Make Group"
    bl_description = "Convert the selected components into independent groups"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if containers.is_component(obj):
                containers.make_unique(obj)
                obj[containers.PROP_KIND] = containers.KIND_GROUP
                obj.data[containers.PROP_COMPONENT] = False
                count += 1
        if not count:
            self.report({"WARNING"}, _T("Select a component first"))
            return {"CANCELLED"}
        undo_push("SketchUp Make Group")
        return {"FINISHED"}


class SKETCHUP_OT_edit_container(bpy.types.Operator):
    bl_idname = "sketchup.edit_container"
    bl_label = "Edit Group/Component"
    bl_description = "Enter the selected group or component for editing"
    bl_options = {"REGISTER"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or not containers.is_container(obj):
            for candidate in context.selected_objects:
                if containers.is_container(candidate):
                    obj = candidate
                    break
        if obj is None or not containers.is_container(obj):
            self.report({"WARNING"}, _T("Select a group or component first"))
            return {"CANCELLED"}
        if containers.is_locked(obj):
            self.report({"WARNING"}, _T("This group/component is locked"))
            return {"CANCELLED"}
        containers.enter_context(context, obj)
        return {"FINISHED"}


class SKETCHUP_OT_close_group_component(bpy.types.Operator):
    bl_idname = "sketchup.close_group_component"
    bl_label = "Close Group/Component"
    bl_description = "Close the current group/component and return to the parent context"
    bl_options = {"REGISTER"}

    def execute(self, context):
        if not containers.close_context(context):
            self.report({"INFO"}, _T("Already at the top level"))
            return {"CANCELLED"}
        return {"FINISHED"}


class SKETCHUP_OT_lock_selection(bpy.types.Operator):
    bl_idname = "sketchup.lock_selection"
    bl_label = "Lock"
    bl_description = "Lock the selected groups/components"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if containers.is_container(obj) and containers.set_locked(obj, True):
                count += 1
        if not count:
            self.report({"WARNING"}, _T("Select a group or component first"))
            return {"CANCELLED"}
        undo_push("SketchUp Lock")
        return {"FINISHED"}


class SKETCHUP_OT_unlock_selection(bpy.types.Operator):
    bl_idname = "sketchup.unlock_selection"
    bl_label = "Unlock Selected"
    bl_description = "Unlock the selected groups/components"
    bl_options = {"REGISTER", "UNDO"}

    all_locked: bpy.props.BoolProperty(name="All", default=False)

    def execute(self, context):
        targets = list(bpy.data.objects) if self.all_locked else context.selected_objects
        count = 0
        for obj in targets:
            if containers.is_container(obj) and containers.is_locked(obj):
                containers.set_locked(obj, False)
                count += 1
        if not count:
            self.report({"INFO"}, _T("Nothing locked"))
            return {"CANCELLED"}
        undo_push("SketchUp Unlock")
        return {"FINISHED"}


class SKETCHUP_OT_reset_scale(bpy.types.Operator):
    bl_idname = "sketchup.reset_scale"
    bl_label = "Reset Scale"
    bl_description = "Reset the selected instances to definition size"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        count = sum(
            1
            for obj in context.selected_objects
            if containers.is_container(obj) and containers.reset_scale(obj)
        )
        if not count:
            self.report({"WARNING"}, _T("Select a group or component first"))
            return {"CANCELLED"}
        undo_push("SketchUp Reset Scale")
        return {"FINISHED"}


class SKETCHUP_OT_reset_skew(bpy.types.Operator):
    bl_idname = "sketchup.reset_skew"
    bl_label = "Reset Skew"
    bl_description = "Remove shear from the selected groups/components"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        count = sum(
            1
            for obj in context.selected_objects
            if containers.is_container(obj) and containers.reset_skew(obj)
        )
        if not count:
            self.report({"WARNING"}, _T("Select a group or component first"))
            return {"CANCELLED"}
        undo_push("SketchUp Reset Skew")
        return {"FINISHED"}


class SKETCHUP_OT_scale_definition(bpy.types.Operator):
    bl_idname = "sketchup.scale_definition"
    bl_label = "Scale Definition"
    bl_description = "Bake the instance scale into the component definition"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        count = sum(
            1
            for obj in context.selected_objects
            if containers.is_component(obj) and containers.scale_definition(obj)
        )
        if not count:
            self.report({"WARNING"}, _T("Select a component instance first"))
            return {"CANCELLED"}
        undo_push("SketchUp Scale Definition")
        return {"FINISHED"}


class SKETCHUP_OT_flip_along(bpy.types.Operator):
    bl_idname = "sketchup.flip_along"
    bl_label = "Flip Along"
    bl_description = "Mirror the selected groups/components along a local axis"
    bl_options = {"REGISTER", "UNDO"}

    axis: bpy.props.EnumProperty(
        name="Axis",
        items=[
            ("X", "Red Axis", ""),
            ("Y", "Green Axis", ""),
            ("Z", "Blue Axis", ""),
        ],
        default="X",
    )

    def execute(self, context):
        from mathutils import Matrix

        factors = {"X": (-1.0, 1.0, 1.0), "Y": (1.0, -1.0, 1.0), "Z": (1.0, 1.0, -1.0)}
        mirror = Matrix.Diagonal((*factors[self.axis], 1.0))
        count = 0
        for obj in context.selected_objects:
            if containers.is_container(obj):
                obj.matrix_world = obj.matrix_world @ mirror
                count += 1
        if not count:
            self.report({"WARNING"}, _T("Select a group or component first"))
            return {"CANCELLED"}
        undo_push("SketchUp Flip Along")
        return {"FINISHED"}


class SKETCHUP_OT_place_component(bpy.types.Operator):
    bl_idname = "sketchup.place_component"
    bl_label = "Place Component"
    bl_description = "Place a new instance of a component definition"
    bl_options = {"REGISTER", "UNDO"}

    definition: bpy.props.StringProperty(name="Definition", default="")

    def execute(self, context):
        definitions = containers.component_definitions()
        entry = definitions.get(self.definition)
        if entry is None:
            self.report({"WARNING"}, _T("Unknown component definition"))
            return {"CANCELLED"}
        mesh = entry[0]
        obj = bpy.data.objects.new(
            _unique_object_name(self.definition), mesh
        )
        context.collection.objects.link(obj)
        obj[containers.PROP_KIND] = containers.KIND_COMPONENT
        try:
            obj.location = context.scene.cursor.location
        except Exception:
            pass
        for child in _definition_children(mesh):
            containers._duplicate_subtree(child, obj)
        undo_push("SketchUp Place Component")
        return {"FINISHED"}


def _definition_children(mesh):
    """Children stored on the first instance (the definition holder)."""
    instances = containers.instances_of(mesh)
    if not instances:
        return []
    return list(instances[0].children)


GROUP_OPERATORS = [
    SKETCHUP_OT_make_group,
    SKETCHUP_OT_make_component,
    SKETCHUP_OT_explode,
    SKETCHUP_OT_make_unique,
    SKETCHUP_OT_convert_to_component,
    SKETCHUP_OT_convert_to_group,
    SKETCHUP_OT_edit_container,
    SKETCHUP_OT_close_group_component,
    SKETCHUP_OT_lock_selection,
    SKETCHUP_OT_unlock_selection,
    SKETCHUP_OT_reset_scale,
    SKETCHUP_OT_reset_skew,
    SKETCHUP_OT_scale_definition,
    SKETCHUP_OT_flip_along,
    SKETCHUP_OT_place_component,
]
