"""Dimensions and text annotations (proposal §3.10, P6).

Stored as JSON in Scene.su_annotations_json; drawn by the
persistent viewport overlay. Dimension endpoints keep an optional
object reference so the displayed length follows the model when
the object moves.
"""

import json

from mathutils import Vector

PROP_NAME = "su_annotations_json"


def get_annotations(scene):
    raw = scene.get(PROP_NAME, "")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return data if isinstance(data, list) else []


def save_annotations(scene, annotations):
    scene[PROP_NAME] = json.dumps(annotations)


def add_dimension(scene, p1, p2, offset, ref1=None, ref2=None):
    """ref: (object name, local coords) or None."""
    annotations = get_annotations(scene)
    entry = {
        "type": "dimension",
        "p1": [float(c) for c in p1],
        "p2": [float(c) for c in p2],
        "offset": [float(c) for c in offset],
    }
    if ref1 is not None:
        entry["ref1"] = [ref1[0], [float(c) for c in ref1[1]]]
    if ref2 is not None:
        entry["ref2"] = [ref2[0], [float(c) for c in ref2[1]]]
    annotations.append(entry)
    save_annotations(scene, annotations)
    return entry


def add_text(scene, point, text, anchor_offset=(0.5, 0.0, 0.3)):
    annotations = get_annotations(scene)
    entry = {
        "type": "text",
        "point": [float(c) for c in point],
        "text": text,
        "anchor_offset": [float(c) for c in anchor_offset],
    }
    annotations.append(entry)
    save_annotations(scene, annotations)
    return entry


def remove_annotation(scene, index):
    annotations = get_annotations(scene)
    if 0 <= index < len(annotations):
        annotations.pop(index)
        save_annotations(scene, annotations)
        return True
    return False


def resolve_point(scene, entry, key):
    """Current world position of an endpoint: object reference when
    resolvable, else the stored world coordinates."""
    import bpy

    ref = entry.get(key)
    if ref:
        obj = bpy.data.objects.get(ref[0])
        if obj is not None:
            try:
                return obj.matrix_world @ Vector(ref[1])
            except Exception:
                pass
    return Vector(entry["p1" if key == "ref1" else "p2"])


def dimension_geometry(p1, p2, offset):
    """Aligned-dimension layout (pure math).

    Returns a dict: dim_a/dim_b (dimension line ends), ext1/ext2
    (extension line segments), text_point, length. The dimension
    line passes through ``offset`` parallel to p1-p2.
    """
    p1, p2, offset = Vector(p1), Vector(p2), Vector(offset)
    direction = p2 - p1
    length = direction.length
    if length < 1e-9:
        return None
    direction.normalize()
    # Offset of the dimension line from the measured segment.
    rel = offset - p1
    along = rel.dot(direction)
    perp = rel - direction * along
    dim_a = p1 + perp
    dim_b = p2 + perp
    # Extension lines overshoot the dimension line slightly.
    overshoot = perp.normalized() * min(0.1, perp.length * 0.1) if perp.length > 1e-9 else Vector()
    ext1 = (p1, dim_a + overshoot)
    ext2 = (p2, dim_b + overshoot)
    text_point = (dim_a + dim_b) * 0.5
    return {
        "dim_a": dim_a,
        "dim_b": dim_b,
        "ext1": ext1,
        "ext2": ext2,
        "text_point": text_point,
        "length": length,
        "direction": direction,
    }
