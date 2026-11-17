"""Header "SketchUp" menu, generated from the data table.

Menu classes are generated from ``data/menu_data.py`` (proposal §2.5):
correcting the layout means editing the data table, not this file.
SketchUp menus carry no icons, so P0 menu items are text-only.
"""

import bpy

from .data.menu_data import MENUS
from .i18n.translations import translate as _T

MAIN_MENU_ID = "SKETCHUP_MT_MAIN"


def _submenu_idname(item_id):
    return "SKETCHUP_MT_" + item_id.upper()


def _draw_items(layout, items):
    for item in items:
        if item.get("separator"):
            layout.separator()
            continue
        if "note" in item:
            row = layout.row()
            row.enabled = False
            row.label(text=_T(item["note"]))
            continue
        if item.get("scope", "in") == "out":
            continue
        label = item.get("label")
        if label is None:
            # Unverified English label: never render a guessed name.
            continue
        if "submenu" in item:
            layout.menu(_submenu_idname(item["id"]), text=_T(label))
        else:
            operator_id = item.get("operator", "sketchup.stub")
            operator = layout.operator(operator_id, text=_T(label))
            if operator_id == "sketchup.stub":
                operator.tool_id = item["id"]
            for key, value in item.get("props", {}).items():
                try:
                    setattr(operator, key, value)
                except Exception:
                    pass


def _make_menu_class(bl_idname, bl_label, items):
    def draw(self, context):
        _draw_items(self.layout, items)

    return type(
        bl_idname,
        (bpy.types.Menu,),
        {
            "bl_idname": bl_idname,
            "bl_label": bl_label,
            "draw": draw,
            "__module__": __name__,
            "__doc__": "Generated from the menu data table.",
        },
    )


def _collect_classes():
    classes = []

    def main_draw(self, context):
        layout = self.layout
        for menu in MENUS:
            layout.menu(_submenu_idname(menu["id"]), text=_T(menu["label"]))

    classes.append(
        type(
            "SKETCHUP_MT_MAIN",
            (bpy.types.Menu,),
            {
                "bl_idname": MAIN_MENU_ID,
                "bl_label": "SketchUp",
                "draw": main_draw,
                "__module__": __name__,
                "__doc__": "Top-level SketchUp menu.",
            },
        )
    )

    def walk(items):
        for item in items:
            if "submenu" in item and item.get("scope", "in") == "in":
                classes.append(
                    _make_menu_class(
                        _submenu_idname(item["id"]), item["label"], item["submenu"]
                    )
                )
                walk(item["submenu"])

    for menu in MENUS:
        classes.append(
            _make_menu_class(
                _submenu_idname(menu["id"]), menu["label"], menu["items"]
            )
        )
        walk(menu["items"])
    return classes


MENU_CLASSES = _collect_classes()


def _iter_search_items(items, group, found):
    for item in items:
        if item.get("separator") or "note" in item:
            continue
        if item.get("scope", "in") == "out":
            continue
        label = item.get("label")
        if label is None:
            continue
        if "submenu" in item:
            _iter_search_items(item["submenu"], label, found)
        else:
            found.append((group, label, item.get("operator", "sketchup.stub"), item["id"]))


class SKETCHUP_MT_search(bpy.types.Menu):
    bl_idname = "SKETCHUP_MT_search"
    bl_label = "Search SketchUp Tools"

    def draw(self, context):
        found = []
        for menu in MENUS:
            _iter_search_items(menu["items"], menu["label"], found)
        layout = self.layout
        current_group = None
        for group, label, operator_id, item_id in found:
            if group != current_group:
                current_group = group
                layout.label(text=group)
            operator = layout.operator(operator_id, text="  " + _T(label))
            if operator_id == "sketchup.stub":
                operator.tool_id = item_id


class SKETCHUP_OT_search(bpy.types.Operator):
    bl_idname = "sketchup.search"
    bl_label = "Search"
    bl_description = "Search all SketchUp tools and commands"

    def execute(self, context):
        bpy.ops.wm.call_menu(name="SKETCHUP_MT_search")
        return {"FINISHED"}


def _draw_header_menu(self, context):
    self.layout.menu(MAIN_MENU_ID, text="SketchUp")


def register():
    for cls in MENU_CLASSES:
        bpy.utils.register_class(cls)
    bpy.utils.register_class(SKETCHUP_MT_search)
    bpy.utils.register_class(SKETCHUP_OT_search)
    bpy.types.VIEW3D_MT_editor_menus.append(_draw_header_menu)


def unregister():
    bpy.types.VIEW3D_MT_editor_menus.remove(_draw_header_menu)
    bpy.utils.unregister_class(SKETCHUP_OT_search)
    bpy.utils.unregister_class(SKETCHUP_MT_search)
    for cls in reversed(MENU_CLASSES):
        bpy.utils.unregister_class(cls)
