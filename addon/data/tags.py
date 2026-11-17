"""Tags (layers): scene-level tag list + per-object ``su_tag``.

The list lives in Scene.su_tags (a CollectionProperty, saved with
the file); each object carries its tag name in the ``su_tag`` ID
property. "Untagged" always exists and cannot be renamed or
deleted. Visibility maps to the object's viewport hiding.
"""

UNTAGGED = "Untagged"

_PALETTE = [
    (0.85, 0.25, 0.25),
    (0.25, 0.55, 0.85),
    (0.30, 0.70, 0.35),
    (0.90, 0.65, 0.20),
    (0.60, 0.40, 0.80),
    (0.20, 0.75, 0.70),
    (0.85, 0.45, 0.65),
    (0.55, 0.55, 0.55),
]


def ensure_defaults(scene):
    """Make sure Untagged exists; returns the tag list."""
    tags = scene.su_tags
    if UNTAGGED not in tags:
        item = tags.add()
        item.name = UNTAGGED
        item.color = (0.8, 0.8, 0.8)
        item.visible = True
    return tags


def find_tag(scene, name):
    ensure_defaults(scene)
    return scene.su_tags.get(name)


def add_tag(scene, name=None):
    tags = ensure_defaults(scene)
    if name is None:
        index = 1
        while "Tag %d" % index in tags:
            index += 1
        name = "Tag %d" % index
    if name in tags:
        return tags[name]
    item = tags.add()
    item.name = name
    item.color = _PALETTE[(len(tags) - 2) % len(_PALETTE)]
    item.visible = True
    return item


def rename_tag(scene, old_name, new_name):
    if old_name == UNTAGGED or not new_name or new_name == old_name:
        return False
    tags = ensure_defaults(scene)
    if old_name not in tags or new_name in tags:
        return False
    tags[old_name].name = new_name
    for obj in scene.objects:
        if object_tag(obj) == old_name:
            obj["su_tag"] = new_name
    return True


def delete_tag(scene, name):
    if name == UNTAGGED:
        return False
    tags = ensure_defaults(scene)
    if name not in tags:
        return False
    for obj in scene.objects:
        if object_tag(obj) == name:
            obj["su_tag"] = UNTAGGED
    index = tags.find(name)
    tags.remove(index)
    if scene.su_tags_index >= len(tags):
        scene.su_tags_index = max(0, len(tags) - 1)
    apply_visibility(scene)
    return True


def object_tag(obj):
    return obj.get("su_tag", UNTAGGED)


def set_object_tag(obj, name):
    obj["su_tag"] = name


def active_tag_name(scene):
    tags = ensure_defaults(scene)
    index = scene.su_tags_index
    if 0 <= index < len(tags):
        return tags[index].name
    return UNTAGGED


def tag_color(scene, name):
    tag = find_tag(scene, name)
    if tag is None:
        return (0.8, 0.8, 0.8)
    return tuple(tag.color)


def tag_visible(scene, name):
    tag = find_tag(scene, name)
    return True if tag is None else bool(tag.visible)


def apply_visibility(scene):
    """Sync every object's viewport hiding to its tag's flag."""
    tags = ensure_defaults(scene)
    visibility = {tag.name: bool(tag.visible) for tag in tags}
    for obj in scene.objects:
        obj.hide_viewport = not visibility.get(object_tag(obj), True)
