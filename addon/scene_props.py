"""Scene-level saved state (proposal §10.6): guides, drawing axes,
tags, and the active material/tag, persisted as JSON in Scene
custom properties so they survive save/load. A load_post handler
restores the session copies when a file opens.
"""

import json

import bpy

from .core.state import DrawingAxes, get_session
from .data.guides import GuideSet


class SketchUpTagItem(bpy.types.PropertyGroup):
    """One SketchUp tag (layer): name, display color, visibility."""

    color: bpy.props.FloatVectorProperty(
        name="Color", subtype="COLOR", size=3, default=(0.8, 0.8, 0.8),
        min=0.0, max=1.0,
    )
    visible: bpy.props.BoolProperty(name="Visible", default=True)


def _get_json(scene, name):
    raw = scene.get(name, "")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _set_json(scene, name, data):
    scene[name] = json.dumps(data)


# -- guides ---------------------------------------------------------------

def save_guides(scene=None):
    scene = scene or bpy.context.scene
    if scene is None:
        return
    _set_json(scene, "su_guides_json", get_session().guides.to_dict())


def load_guides(scene=None):
    scene = scene or bpy.context.scene
    if scene is None:
        return
    data = _get_json(scene, "su_guides_json")
    if data is not None:
        get_session().guides = GuideSet.from_dict(data)


# -- drawing axes ---------------------------------------------------------

def save_axes(scene=None):
    scene = scene or bpy.context.scene
    if scene is None:
        return
    _set_json(scene, "su_axes_json", get_session().axes.to_dict())


def load_axes(scene=None):
    scene = scene or bpy.context.scene
    if scene is None:
        return
    data = _get_json(scene, "su_axes_json")
    if data is not None:
        get_session().axes = DrawingAxes.from_dict(data)


# -- load handler ---------------------------------------------------------

def _on_load(_dummy):
    load_guides()
    load_axes()


def register():
    bpy.utils.register_class(SketchUpTagItem)
    bpy.types.Scene.su_tags = bpy.props.CollectionProperty(
        type=SketchUpTagItem
    )
    bpy.types.Scene.su_tags_index = bpy.props.IntProperty(
        name="Active Tag Index", default=0
    )
    bpy.types.Scene.su_guides_json = bpy.props.StringProperty(
        name="SketchUp Guides", default="", options={"HIDDEN"}
    )
    bpy.types.Scene.su_axes_json = bpy.props.StringProperty(
        name="SketchUp Drawing Axes", default="", options={"HIDDEN"}
    )
    bpy.types.Scene.su_active_material = bpy.props.StringProperty(
        name="Active Material", default=""
    )
    bpy.types.Scene.su_paint_mode = bpy.props.EnumProperty(
        name="Paint Mode",
        items=[
            ("FACE", "Face", "Paint the clicked face"),
            ("CONNECTED", "Connected", "Paint connected faces with the same material"),
            ("ALL", "All Matching", "Paint all faces with the same material"),
            ("OBJECT", "Object", "Paint the whole object"),
        ],
        default="FACE",
    )
    bpy.types.Scene.su_color_by_tag = bpy.props.BoolProperty(
        name="Color by Tag", default=False
    )
    bpy.types.Scene.su_sections_enabled = bpy.props.BoolProperty(
        name="Section Cuts Enabled", default=True
    )
    bpy.types.Scene.su_annotations_json = bpy.props.StringProperty(
        name="SketchUp Annotations", default="", options={"HIDDEN"}
    )
    bpy.types.Scene.su_scenes_json = bpy.props.StringProperty(
        name="SketchUp Scenes", default="", options={"HIDDEN"}
    )
    bpy.types.Scene.su_color_by_axis = bpy.props.BoolProperty(
        name="Color by Axis", default=False
    )
    bpy.app.handlers.load_post.append(_on_load)


def unregister():
    try:
        bpy.app.handlers.load_post.remove(_on_load)
    except ValueError:
        pass
    del bpy.types.Scene.su_color_by_axis
    del bpy.types.Scene.su_scenes_json
    del bpy.types.Scene.su_annotations_json
    del bpy.types.Scene.su_sections_enabled
    del bpy.types.Scene.su_color_by_tag
    del bpy.types.Scene.su_paint_mode
    del bpy.types.Scene.su_active_material
    del bpy.types.Scene.su_axes_json
    del bpy.types.Scene.su_guides_json
    del bpy.types.Scene.su_tags_index
    del bpy.types.Scene.su_tags
    bpy.utils.unregister_class(SketchUpTagItem)
