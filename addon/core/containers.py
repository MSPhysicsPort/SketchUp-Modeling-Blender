"""Group and Component containers (proposal §3.6).

Mapping (root architecture: one edit context = one Mesh Object):
- Group = its own Mesh Object; copies are independent (deep copy).
- Component = several Objects sharing ONE Mesh data block (linked
  duplicates). Editing any instance edits the definition, so all
  instances update. ``su_definition`` on the Mesh names the
  definition; the mesh keeps a fake user so the definition survives
  in the file like SketchUp's component browser.
- Nesting = Object parenting. A child container's local frame equals
  its parent's frame (identity parent inverse), so geometry moves
  between contexts without re-baking transforms.
- Nested content inside a component: children are stored on the
  edited instance and synced to the other instances when the edit
  closes (:func:`sync_component_children`), giving SketchUp's
  "edit one, update all" semantics including nesting.

The edit-context stack lives in the session state
(``context_stack``: object names, root first, current last).
Entering a container switches the active object and Edit Mode to it;
closing pops back to the parent context.
"""

import bmesh
import bpy
from mathutils import Matrix

from ..core import geometry as geometry_mod
from ..core.state import get_session

PROP_KIND = "su_kind"
PROP_DEF = "su_definition"
PROP_COMPONENT = "su_component"
PROP_LOCKED = "su_locked"
PROP_DESC = "su_description"

KIND_GROUP = "GROUP"
KIND_COMPONENT = "COMPONENT"


# -- identity ------------------------------------------------------------

def kind_of(obj):
    if obj is None:
        return ""
    return obj.get(PROP_KIND, "")


def is_group(obj):
    return kind_of(obj) == KIND_GROUP


def is_component(obj):
    return kind_of(obj) == KIND_COMPONENT


def is_container(obj):
    return kind_of(obj) in (KIND_GROUP, KIND_COMPONENT)


def is_locked(obj):
    if obj is None:
        return False
    return bool(obj.get(PROP_LOCKED, False))


def definition_name(obj):
    """Component definition name (mesh property, else mesh name)."""
    if obj is None or obj.data is None:
        return ""
    name = obj.data.get(PROP_DEF, "")
    return name if name else obj.data.name


def instances_of(mesh):
    """All objects sharing this mesh data block."""
    if mesh is None:
        return []
    return [obj for obj in bpy.data.objects if obj.data is mesh]


def component_definitions():
    """{definition name: [mesh, [instance objects]]} for the file."""
    definitions = {}
    for mesh in bpy.data.meshes:
        if not mesh.get(PROP_COMPONENT, False):
            continue
        name = mesh.get(PROP_DEF, "") or mesh.name
        definitions[name] = [mesh, instances_of(mesh)]
    return definitions


# -- context stack -------------------------------------------------------

def context_stack():
    return get_session().context_stack


def current_context_name():
    stack = context_stack()
    return stack[-1] if stack else ""


def reset_context_stack(root_name):
    session = get_session()
    session.context_stack = [root_name] if root_name else []
    session.selected_container = None


def enter_context(context, obj):
    """Switch editing to ``obj`` (must be a mesh object)."""
    if obj is None or obj.type != "MESH":
        return False
    stack = context_stack()
    if obj.name in stack:
        # Re-entering an ancestor: pop back to it.
        while stack and stack[-1] != obj.name:
            stack.pop()
        return _activate(context, obj)
    stack.append(obj.name)
    get_session().selected_container = None
    return _activate(context, obj)


def _activate(context, obj):
    try:
        context.view_layer.objects.active = obj
    except (AttributeError, ReferenceError):
        return False
    if not bpy.app.background and context.area is not None:
        try:
            bpy.ops.object.mode_set(mode="EDIT")
        except Exception:
            pass
    return True


def close_context(context):
    """Pop one context level; False when already at the root."""
    stack = context_stack()
    if len(stack) <= 1:
        return False
    closing_name = stack.pop()
    closing = bpy.data.objects.get(closing_name)
    if closing is not None and is_component(closing):
        sync_component_children(closing)
    parent = bpy.data.objects.get(stack[-1]) if stack else None
    if parent is None:
        return False
    return _activate(context, parent)


_pending_enter = None


def request_enter_context(obj_name):
    """Deferred enter (from inside a modal tool): the mode switch
    runs on a timer, after the modal handler has finished, and the
    Select tool restarts in the new context."""
    global _pending_enter
    _pending_enter = obj_name
    try:
        bpy.app.timers.register(_run_pending_enter, first_interval=0.0)
    except Exception:
        pass


def _run_pending_enter():
    global _pending_enter
    name = _pending_enter
    _pending_enter = None
    if name:
        obj = bpy.data.objects.get(name)
        if obj is not None:
            enter_context(bpy.context, obj)
            try:
                bpy.ops.sketchup.tool_select("INVOKE_DEFAULT")
            except Exception:
                pass
    return None


_pending_close = False


def request_close_context():
    """Deferred close (from inside a modal tool)."""
    global _pending_close
    _pending_close = True
    try:
        bpy.app.timers.register(_run_pending_close, first_interval=0.0)
    except Exception:
        pass


def _run_pending_close():
    global _pending_close
    _pending_close = False
    if close_context(bpy.context):
        try:
            bpy.ops.sketchup.tool_select("INVOKE_DEFAULT")
        except Exception:
            pass
    return None


# -- creation ------------------------------------------------------------

def extract_selection_to_object(bm, source_obj, name, kind):
    """Move the selected elements of ``bm`` into a new object.

    ``bm`` is the source's edit bmesh (live or standalone); the
    caller commits it. Returns the new object, or None when nothing
    is selected. Shared edges stay in the source (SketchUp splits
    shared edges when grouping); curve metadata is dropped (curves
    become plain edges inside the container).
    """
    # Layers FIRST: creating a layer invalidates element wrappers
    # fetched earlier (probe-verified, see geometry.ensure_layers).
    geometry_mod.ensure_layers(bm)
    geometry_mod.refresh(bm)
    selected_faces = [f for f in bm.faces if f.select]
    selected_edges = [e for e in bm.edges if e.select]
    selected_verts = [v for v in bm.verts if v.select]
    if not (selected_faces or selected_edges or selected_verts):
        return None
    source_uv = bm.loops.layers.uv.active
    new_bm = bmesh.new()
    geometry_mod.ensure_layers(new_bm)
    target_uv = None
    if source_uv is not None:
        target_uv = new_bm.loops.layers.uv.new("UVMap")
    vert_map = {}
    for vert in selected_verts:
        vert_map[vert.index] = new_bm.verts.new(vert.co)
    for face in selected_faces:
        for vert in face.verts:
            if vert.index not in vert_map:
                vert_map[vert.index] = new_bm.verts.new(vert.co)
    for edge in selected_edges:
        for vert in edge.verts:
            if vert.index not in vert_map:
                vert_map[vert.index] = new_bm.verts.new(vert.co)
    new_bm.verts.ensure_lookup_table()

    def get_edge(edge):
        verts = (vert_map[edge.verts[0].index], vert_map[edge.verts[1].index])
        if verts[0] is verts[1]:
            return None
        if (verts[0].co - verts[1].co).length <= geometry_mod.MERGE_DISTANCE:
            # Zero-length edge (coincident endpoints): copying it
            # would crash set_edge_flags' coordinate re-fetch and
            # adds nothing to the container.
            return None
        existing = new_bm.edges.get(verts)
        if existing is not None:
            return existing
        new_edge = new_bm.edges.new(verts)
        flags = geometry_mod.edge_flags(bm, edge)
        geometry_mod.set_edge_flags(
            new_bm,
            new_edge,
            soft=bool(flags & geometry_mod.FLAG_SOFT),
            hidden=bool(flags & geometry_mod.FLAG_HIDDEN),
        )
        return new_edge

    for edge in selected_edges:
        get_edge(edge)
    face_map = {}
    for face in selected_faces:
        verts = [vert_map[v.index] for v in face.verts]
        new_face = new_bm.faces.new(verts)
        new_face.material_index = face.material_index
        new_face.smooth = face.smooth
        face_map[face.index] = new_face.index
    if target_uv is not None:
        geometry_mod.refresh(new_bm)
        geometry_mod.refresh(bm)
        for source_index, target_index in face_map.items():
            source_face = bm.faces[source_index]
            target_face = new_bm.faces[target_index]
            for source_loop, target_loop in zip(
                source_face.loops, target_face.loops
            ):
                target_loop[target_uv].uv = source_loop[source_uv].uv
    new_mesh = bpy.data.meshes.new(name)
    new_bm.to_mesh(new_mesh)
    new_bm.free()
    for material in source_obj.data.materials:
        new_mesh.materials.append(material)
    new_obj = bpy.data.objects.new(name, new_mesh)
    collections = source_obj.users_collection or [bpy.context.collection]
    collections[0].objects.link(new_obj)
    new_obj.parent = source_obj
    new_obj.matrix_parent_inverse = Matrix.Identity(4)
    new_obj.matrix_local = Matrix.Identity(4)
    new_obj[PROP_KIND] = kind
    if kind == KIND_COMPONENT:
        new_mesh[PROP_COMPONENT] = True
        new_mesh[PROP_DEF] = name
        new_mesh.use_fake_user = True
    # Remove the moved elements from the source, keeping anything
    # still used by unselected geometry. Re-fetch by index: earlier
    # refreshes may have invalidated the collected wrappers.
    # Remove by wrapper: indexing (bm.faces[i]) goes stale after any
    # removal, but wrappers of surviving elements stay valid.
    for face in selected_faces:
        bm.faces.remove(face)
    for edge in selected_edges:
        if not edge.link_faces:
            bm.edges.remove(edge)
    for vert in selected_verts:
        if not vert.link_edges and not vert.link_faces:
            bm.verts.remove(vert)
    geometry_mod.refresh(bm)
    return new_obj


def make_group_from_objects(objects, name):
    """Group whole objects (object-mode path): reparent under a new
    empty group shell object. Groups of objects share one parent
    empty; the shell carries the GROUP identity."""
    shell = bpy.data.objects.new(name, None)
    shell.empty_display_type = "PLAIN_AXES"
    shell.empty_display_size = 0.1
    bpy.context.collection.objects.link(shell)
    shell[PROP_KIND] = KIND_GROUP
    for obj in objects:
        world = obj.matrix_world.copy()
        obj.parent = shell
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.matrix_world = world
    return shell


# -- explode / unique / sync ----------------------------------------------

def _material_slot_index(mesh, material):
    for index, slot in enumerate(mesh.materials):
        if slot is material:
            return index
    mesh.materials.append(material)
    return len(mesh.materials) - 1


def append_mesh_into(target_obj, source_mesh, matrix):
    """Append ``source_mesh`` (transformed by ``matrix``) into the
    target object's mesh, welding coincident verts (explode re-sticks
    geometry, SketchUp-style). Works in Edit Mode and Object Mode."""
    target_mesh = target_obj.data
    live = False
    try:
        live = target_obj.mode == "EDIT"
    except Exception:
        pass
    if live:
        bm = bmesh.from_edit_mesh(target_mesh)
    else:
        bm = bmesh.new()
        bm.from_mesh(target_mesh)
    try:
        geometry_mod.ensure_layers(bm)
        source_bm = bmesh.new()
        source_bm.from_mesh(source_mesh)
        try:
            geometry_mod.ensure_layers(source_bm)
            vert_map = {}
            for vert in source_bm.verts:
                world_co = matrix @ vert.co
                vert_map[vert.index] = geometry_mod.get_or_create_vert(bm, world_co)
            bm.verts.ensure_lookup_table()
            for edge in source_bm.edges:
                verts = (vert_map[edge.verts[0].index], vert_map[edge.verts[1].index])
                if bm.edges.get(verts) is None:
                    new_edge = bm.edges.new(verts)
                    flags = geometry_mod.edge_flags(source_bm, edge)
                    geometry_mod.set_edge_flags(
                        bm,
                        new_edge,
                        soft=bool(flags & geometry_mod.FLAG_SOFT),
                        hidden=bool(flags & geometry_mod.FLAG_HIDDEN),
                    )
            for face in source_bm.faces:
                verts = [vert_map[v.index] for v in face.verts]
                if len(verts) < 3 or len(set(v.index for v in verts)) < 3:
                    continue
                try:
                    new_face = bm.faces.new(verts)
                except ValueError:
                    continue
                material = None
                if face.material_index < len(source_mesh.materials):
                    material = source_mesh.materials[face.material_index]
                if material is not None:
                    new_face.material_index = _material_slot_index(target_mesh, material)
                new_face.smooth = face.smooth
        finally:
            source_bm.free()
        if live:
            bmesh.update_edit_mesh(target_mesh)
        else:
            bm.to_mesh(target_mesh)
            bm.free()
        target_mesh.update()
    except Exception:
        if not live:
            bm.free()
        raise


def explode_object(context, obj, target_obj):
    """Merge a container's geometry into ``target_obj`` and delete
    the container. Children are reparented to the target, keeping
    their world transforms."""
    if obj is None or target_obj is None or obj is target_obj:
        return False
    if obj.type == "MESH" and obj.data is not None:
        matrix = target_obj.matrix_world.inverted() @ obj.matrix_world
        append_mesh_into(target_obj, obj.data, matrix)
    for child in list(obj.children):
        world = child.matrix_world.copy()
        child.parent = target_obj
        child.matrix_parent_inverse = Matrix.Identity(4)
        child.matrix_world = world
    bpy.data.objects.remove(obj, do_unlink=True)
    return True


def make_unique(obj):
    """Detach one component instance from its definition."""
    if obj is None or obj.type != "MESH" or obj.data is None:
        return False
    new_mesh = obj.data.copy()
    base = definition_name(obj)
    new_mesh[PROP_DEF] = _unique_definition_name(base)
    new_mesh[PROP_COMPONENT] = True
    new_mesh.use_fake_user = True
    obj.data = new_mesh
    return True


def _unique_definition_name(base):
    existing = set(component_definitions())
    if base not in existing:
        return base
    index = 1
    while "%s #%d" % (base, index) in existing:
        index += 1
    return "%s #%d" % (base, index)


def _duplicate_subtree(obj, new_parent):
    """Deep-copy ``obj`` and its children under ``new_parent``.

    Nested component children keep their shared mesh (staying
    linked instances); group children get copied mesh data."""
    copy = obj.copy()
    if obj.type == "MESH" and obj.data is not None and not is_component(obj):
        copy.data = obj.data.copy()
    bpy.context.collection.objects.link(copy)
    copy.parent = new_parent
    copy.matrix_parent_inverse = obj.matrix_parent_inverse.copy()
    copy.matrix_local = obj.matrix_local.copy()
    for child in obj.children:
        _duplicate_subtree(child, copy)
    return copy


def sync_component_children(edited_instance):
    """Copy the edited instance's child subtree to every other
    instance of the same definition (nested content stays in sync)."""
    if edited_instance is None or edited_instance.data is None:
        return 0
    synced = 0
    for other in instances_of(edited_instance.data):
        if other is edited_instance:
            continue
        for child in list(other.children):
            bpy.data.objects.remove(child, do_unlink=True)
        for child in edited_instance.children:
            _duplicate_subtree(child, other)
        synced += 1
    return synced


# -- axes / scale ----------------------------------------------------------

def reset_scale(obj):
    """Reset an instance's scale to 1 (definition size)."""
    if obj is None:
        return False
    obj.scale = (1.0, 1.0, 1.0)
    return True


def reset_skew(obj):
    """Remove shear from the object's world matrix, keeping its
    position, rotation and scale."""
    if obj is None:
        return False
    loc, rot, scale = obj.matrix_world.decompose()
    obj.matrix_world = Matrix.LocRotScale(loc, rot, scale)
    return True


def scale_definition(obj):
    """Bake the instance scale into the (shared) mesh and reset the
    instance scale to 1: all instances take the new definition size."""
    if obj is None or obj.type != "MESH" or obj.data is None:
        return False
    scale = obj.scale
    obj.data.transform(Matrix.Diagonal((scale.x, scale.y, scale.z, 1.0)))
    obj.scale = (1.0, 1.0, 1.0)
    return True


def change_axes(obj, origin_world, x_world, y_world):
    """Redefine a container's local axes. World geometry of every
    instance stays put: the mesh is counter-transformed and each
    instance matrix is adjusted by the frame change."""
    if obj is None or obj.type != "MESH" or obj.data is None:
        return False
    from mathutils import Vector

    x = Vector(x_world).normalized()
    y = Vector(y_world).normalized()
    z = x.cross(y).normalized()
    y = z.cross(x).normalized()
    new_frame = Matrix((
        (x.x, y.x, z.x, origin_world[0]),
        (x.y, y.y, z.y, origin_world[1]),
        (x.z, y.z, z.z, origin_world[2]),
        (0.0, 0.0, 0.0, 1.0),
    ))
    old_frame = obj.matrix_world.copy()
    frame_change = old_frame.inverted() @ new_frame
    obj.data.transform(frame_change.inverted())
    for instance in instances_of(obj.data):
        instance.matrix_world = instance.matrix_world @ frame_change
    return True


def set_locked(obj, locked):
    if obj is None:
        return False
    obj[PROP_LOCKED] = bool(locked)
    try:
        obj.hide_select = bool(locked)
    except Exception:
        pass
    return True
