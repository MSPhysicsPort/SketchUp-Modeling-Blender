"""Scenes (proposal §3.11, P6): named snapshots of the camera,
tag visibility, active section, and hidden objects, stored as
JSON in Scene.su_scenes_json.
"""

import json

from mathutils import Quaternion, Vector

PROP_NAME = "su_scenes_json"


def get_scenes(scene):
    raw = scene.get(PROP_NAME, "")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return data if isinstance(data, list) else []


def save_scenes(scene, entries):
    scene[PROP_NAME] = json.dumps(entries)


def capture_scene(context, name):
    """Capture the current state as a scene entry dict."""
    scene = context.scene
    entry = {"name": name}
    rv3d = getattr(context.space_data, "region_3d", None)
    if rv3d is not None:
        entry["view"] = {
            "location": [float(c) for c in rv3d.view_location],
            "rotation": [float(c) for c in rv3d.view_rotation],
            "distance": float(rv3d.view_distance),
            "perspective": rv3d.view_perspective,
        }
    from ..data import sections as sections_mod
    from ..data import tags as tags_mod

    tags_mod.ensure_defaults(scene)
    entry["tags"] = {
        tag.name: bool(tag.visible) for tag in scene.su_tags
    }
    active = sections_mod.get_active_section(scene)
    entry["section"] = active.name if active is not None else None
    entry["hidden"] = [
        obj.name for obj in scene.objects if obj.hide_viewport
    ]
    return entry


def apply_scene(context, entry):
    """Restore a captured scene entry. Returns True when the view
    could be applied (needs a 3D view context)."""
    scene = context.scene
    from ..data import sections as sections_mod
    from ..data import tags as tags_mod

    import bpy

    tags_mod.ensure_defaults(scene)
    for tag in scene.su_tags:
        if tag.name in entry.get("tags", {}):
            tag.visible = entry["tags"][tag.name]
    tags_mod.apply_visibility(scene)
    section_name = entry.get("section")
    plane = bpy.data.objects.get(section_name) if section_name else None
    if plane is not None and plane.get(sections_mod.PROP_SECTION, False):
        sections_mod.set_active_section(scene, plane)
    else:
        sections_mod.set_active_section(scene, None)
    hidden = set(entry.get("hidden", []))
    for obj in scene.objects:
        if obj.name in hidden:
            obj.hide_viewport = True
    view = entry.get("view")
    rv3d = getattr(context.space_data, "region_3d", None)
    if view is None or rv3d is None:
        return False
    rv3d.view_location = Vector(view["location"])
    rv3d.view_rotation = Quaternion(view["rotation"])
    rv3d.view_distance = view["distance"]
    try:
        rv3d.view_perspective = view["perspective"]
    except Exception:
        pass
    return True


def add_scene(context, name):
    entries = get_scenes(context.scene)
    if any(entry["name"] == name for entry in entries):
        index = 1
        base = name
        while any(entry["name"] == "%s %d" % (base, index) for entry in entries):
            index += 1
        name = "%s %d" % (base, index)
    entries.append(capture_scene(context, name))
    save_scenes(context.scene, entries)
    return name


def update_scene(context, index):
    entries = get_scenes(context.scene)
    if 0 <= index < len(entries):
        name = entries[index]["name"]
        entries[index] = capture_scene(context, name)
        save_scenes(context.scene, entries)
        return True
    return False


def delete_scene(scene, index):
    entries = get_scenes(scene)
    if 0 <= index < len(entries):
        entries.pop(index)
        save_scenes(scene, entries)
        return True
    return False
