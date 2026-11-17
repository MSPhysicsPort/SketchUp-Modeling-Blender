"""Shortcut registration: SketchUp keys in the keymaps Blender
actually consults, driven by the SU Mode switch.

Root cause of the 0.4.0 failure (reproduced 2026-11-17 with real X
key events under Xvfb): items registered ONLY in the "3D View"
keymap lose to Blender's mode keymaps, which the event system tries
first. In Edit Mode the "Mesh" keymap consumes R/S/A/L/E/M/F/P; in
Object Mode the "Object Mode" keymap consumes A/R/S/M. Only keys
unbound in the mode keymaps (E/Q in Object Mode) ever reached our
"3D View" items. Registering the same items in all three keymaps
("3D View", "Mesh", "Object Mode") of ``keyconfigs.addon`` makes
the add-on items win within each keymap name, while keys we do not
bind still fall through to Blender's defaults.

Only ``keyconfigs.addon`` is ever written for OUR items; the user's
keymaps are never modified. Level 0 = no keys, level 1 = SketchUp
defaults (single letters), level 2 = Alt+key combos only. The level
is the key *variant*; whether any keys are registered at all is
decided by the SU Mode switch (see mode.py). Level changes
unregister the old items and register the new ones; the level is
never enforced through ``poll``.

Why disabling defaults is also needed (proven 2026-11-17 with real
X key events): the event system consults the add-on keyconfig's
"3D View" keymap (add-on items win within that keymap), but it does
NOT consult the add-on keyconfig's "Mesh" / "Object Mode" keymaps
at all — a key bound only there never fires, even when the add-on
was enabled at startup. The mode keymaps are tried before "3D View",
so Blender's Mesh/Object Mode items (A/R/S/M/L/E/F/P) swallow the
event before it can fall through to our "3D View" items. The fix,
while SU Mode is ON, is to temporarily set ``active = False`` on
exactly those conflicting default items in the ACTIVE keyconfig
and restore them when the mode turns off. The disabled set is
recorded in the add-on preferences so a restart (or a saved
userpref) can restore exactly what we disabled, never touching
items the user disabled themselves.
"""

import bpy
import json

from .core import compat

# (operator idname, level-1 key, level-1 modifiers, level-2 key, level-2 modifiers)
KEYMAP_TABLE = [
    ("sketchup.tool_select", "SPACE", {}, "SPACE", {"alt": True}),
    ("sketchup.tool_lasso", "SPACE", {"shift": True}, "SPACE", {"alt": True, "shift": True}),
    ("sketchup.tool_line", "L", {}, "L", {"alt": True}),
    ("sketchup.tool_eraser", "E", {}, "E", {"alt": True}),
    ("sketchup.tool_rectangle", "R", {}, "R", {"alt": True}),
    ("sketchup.tool_circle", "C", {}, "C", {"alt": True}),
    ("sketchup.tool_arc_2_point", "A", {}, "A", {"alt": True}),
    ("sketchup.tool_move", "M", {}, "M", {"alt": True}),
    ("sketchup.tool_push_pull", "P", {}, "P", {"alt": True}),
    ("sketchup.tool_rotate", "Q", {}, "Q", {"alt": True}),
    ("sketchup.tool_scale", "S", {}, "S", {"alt": True}),
    ("sketchup.tool_offset", "F", {}, "F", {"alt": True}),
    ("sketchup.make_group", "G", {}, "G", {"alt": True}),
    ("sketchup.tool_tape_measure", "T", {}, "T", {"alt": True}),
    ("sketchup.tool_paint_bucket", "B", {}, "B", {"alt": True}),
    ("sketchup.toggle_back_edges", "K", {}, "K", {"alt": True}),
    ("sketchup.tool_orbit", "O", {}, "O", {"alt": True}),
    ("sketchup.tool_pan", "H", {}, "H", {"alt": True}),
    ("sketchup.tool_zoom", "Z", {}, "Z", {"alt": True}),
    ("sketchup.zoom_extents", "Z", {"shift": True}, "Z", {"alt": True, "shift": True}),
    ("sketchup.parallel_projection", "N", {}, "N", {"alt": True}),
    ("sketchup.view_top", "F2", {}, "F2", {"alt": True}),
    ("sketchup.view_front", "F3", {}, "F3", {"alt": True}),
    ("sketchup.view_left", "F4", {}, "F4", {"alt": True}),
    ("sketchup.view_right", "F5", {}, "F5", {"alt": True}),
    ("sketchup.search", "S", {"shift": True}, "S", {"alt": True, "shift": True}),
    ("sketchup.tool_zoom_window", "W", {"ctrl": True, "shift": True}, "W", {"alt": True, "ctrl": True, "shift": True}),
    ("sketchup.zoom_extents", "E", {"ctrl": True, "shift": True}, "E", {"alt": True, "ctrl": True, "shift": True}),
]

# Keymaps consulted for the 3D View in Object and Edit Mesh modes.
KEYMAP_NAMES = ("3D View", "Mesh", "Object Mode")

# Function keys live in the global Window keymap in Blender's
# default preset (F3 = search, F4 = console); registering our F2-F5
# view keys there too, so they win before the window-level defaults.
WINDOW_KEYMAP_NAMES = ("Window",)
FUNCTION_KEYS = {"F2", "F3", "F4", "F5"}

DEFAULT_LEVEL = 1
CURRENT_LEVEL = DEFAULT_LEVEL

_registered = []  # List of (keymap, keymap_item) for clean removal.

_OUR_OPERATORS = frozenset(entry[0] for entry in KEYMAP_TABLE)


def _preferred_level():
    """Read the saved preference level; fall back to CURRENT_LEVEL."""
    try:
        addon = bpy.context.preferences.addons.get(__package__)
        if addon is not None:
            return int(addon.preferences.keymap_level)
    except Exception:
        pass
    return CURRENT_LEVEL


def _get_or_create_keymap(keyconfig, name):
    keymap = keyconfig.keymaps.get(name)
    if keymap is None:
        # Add-on keyconfigs start empty: create the keymap. The
        # global keymaps use space EMPTY, the 3D View ones VIEW_3D.
        space_type = "EMPTY" if name in ("Window", "Screen") else "VIEW_3D"
        keymap = keyconfig.keymaps.new(name, space_type=space_type)
    return keymap


def _sweep_stale_items(keyconfig):
    """Remove any of our items not tracked in _registered.

    Catches strays left by older versions or a double registration,
    so re-enabling never stacks duplicate items.
    """
    for name in KEYMAP_NAMES + WINDOW_KEYMAP_NAMES:
        keymap = keyconfig.keymaps.get(name)
        if keymap is None:
            continue
        tracked = {id(item) for km, item in _registered if km == keymap}
        for item in list(keymap.keymap_items):
            if item.idname in _OUR_OPERATORS and id(item) not in tracked:
                try:
                    keymap.keymap_items.remove(item)
                except (ReferenceError, RuntimeError):
                    pass


def register_keymaps(level=None):
    """Register the key table at the given level; returns item count.

    Safe to call from register(): a missing add-on keyconfig (headless
    or restricted context) simply registers nothing.
    """
    if level is None:
        level = _preferred_level()
    keyconfig = compat.addon_keyconfig()
    if keyconfig is None:
        return 0
    _sweep_stale_items(keyconfig)
    count = 0
    for entry in KEYMAP_TABLE:
        count += _register_entry(keyconfig, entry, level)
    return count


def _register_entry(keyconfig, entry, level):
    operator_id, key, modifiers, combo_key, combo_modifiers = entry
    if level == 0:
        return 0
    use_key, use_modifiers = (
        (combo_key, combo_modifiers) if level == 2 else (key, modifiers)
    )
    count = 0
    names = KEYMAP_NAMES
    if use_key in FUNCTION_KEYS:
        names = names + WINDOW_KEYMAP_NAMES
    for name in names:
        keymap = _get_or_create_keymap(keyconfig, name)
        item = keymap.keymap_items.new(operator_id, use_key, "PRESS", **use_modifiers)
        _registered.append((keymap, item))
        count += 1
    return count


def unregister_keymaps():
    """Remove every keymap item this add-on registered."""
    for keymap, item in _registered:
        try:
            keymap.keymap_items.remove(item)
        except (ReferenceError, RuntimeError):
            pass
    _registered.clear()


def apply_level(level):
    """Switch keymap level: unregister old items, register new ones."""
    global CURRENT_LEVEL
    unregister_keymaps()
    CURRENT_LEVEL = level
    return register_keymaps(level)


def our_key_count(keymap_name="3D View"):
    """Count our items in one add-on keymap (-1 when unavailable)."""
    keyconfig = compat.addon_keyconfig()
    if keyconfig is None:
        return -1
    keymap = keyconfig.keymaps.get(keymap_name)
    if keymap is None:
        return 0
    return sum(1 for item in keymap.keymap_items if item.idname in _OUR_OPERATORS)


# -- temporarily disabling conflicting defaults (SU Mode ON only) ---

# Mode keymaps whose default items swallow our keys before the event
# can fall through to the add-on "3D View" keymap. "Frames" holds
# SPACE = animation play, which is global (space EMPTY) and eats our
# SPACE = Select. "Window"/"Screen" hold the F-key defaults (F3 =
# search, F4 = console) that would swallow our F2-F5 view keys.
_CONFLICT_KEYMAPS = ("Mesh", "Object Mode", "Frames", "Window", "Screen")


def _level_chords(level):
    """Set of (type, alt, ctrl, shift, oskey) our table uses at level."""
    chords = set()
    for _op, key, mods, combo_key, combo_mods in KEYMAP_TABLE:
        use_key, use_mods = (
            (combo_key, combo_mods) if level == 2 else (key, mods)
        )
        chords.add(
            (
                use_key,
                bool(use_mods.get("alt")),
                bool(use_mods.get("ctrl")),
                bool(use_mods.get("shift")),
                bool(use_mods.get("oskey")),
            )
        )
    return chords


def _get_preferences():
    try:
        addon = bpy.context.preferences.addons.get(__package__)
        return addon.preferences if addon is not None else None
    except Exception:
        return None


def _save_disabled(records):
    prefs = _get_preferences()
    if prefs is not None:
        try:
            prefs.disabled_conflicts_json = json.dumps(records)
        except Exception:
            pass


def _load_disabled():
    prefs = _get_preferences()
    if prefs is None:
        return []
    try:
        records = json.loads(prefs.disabled_conflicts_json or "[]")
        return records if isinstance(records, list) else []
    except Exception:
        return []


def disable_conflicts(level=1):
    """Deactivate conflicting default items; returns record list.

    Only items in the ACTIVE keyconfig's mode keymaps that use one
    of our chords are touched. Already-inactive items are left
    alone (they may be the user's own choice) and are NOT recorded.
    The record list is persisted in the preferences so a later
    session can restore exactly these items.
    """
    chords = _level_chords(level)
    records = []
    try:
        keyconfig = bpy.context.window_manager.keyconfigs.active
    except Exception:
        return records
    if keyconfig is None:
        return records
    for keymap_name in _CONFLICT_KEYMAPS:
        keymap = keyconfig.keymaps.get(keymap_name)
        if keymap is None:
            continue
        for item in keymap.keymap_items:
            if not item.active or item.idname in _OUR_OPERATORS:
                continue
            if item.value != "PRESS":
                continue
            chord = (item.type, item.alt, item.ctrl, item.shift, item.oskey)
            if chord not in chords:
                continue
            item.active = False
            records.append(
                {
                    "keymap": keymap_name,
                    "idname": item.idname,
                    "type": item.type,
                    "value": item.value,
                    "alt": item.alt,
                    "ctrl": item.ctrl,
                    "shift": item.shift,
                    "oskey": item.oskey,
                }
            )
    if records:
        _save_disabled(records)
    return records


def restore_conflicts(records=None):
    """Re-activate items disabled by disable_conflicts().

    With no argument, restores the set recorded in the preferences.
    Returns the number of items re-activated.
    """
    if records is None:
        records = _load_disabled()
    if not records:
        return 0
    try:
        keyconfig = bpy.context.window_manager.keyconfigs.active
    except Exception:
        return 0
    if keyconfig is None:
        return 0
    restored = 0
    for record in records:
        keymap = keyconfig.keymaps.get(record.get("keymap", ""))
        if keymap is None:
            continue
        for item in keymap.keymap_items:
            if item.active or item.idname != record.get("idname"):
                continue
            if (
                item.type == record.get("type")
                and item.value == record.get("value")
                and item.alt == bool(record.get("alt"))
                and item.ctrl == bool(record.get("ctrl"))
                and item.shift == bool(record.get("shift"))
                and item.oskey == bool(record.get("oskey"))
            ):
                item.active = True
                restored += 1
                break
    _save_disabled([])
    return restored


def scan_conflicts(level=1):
    """Report Blender functions shadowed by our keys at this level.

    Returns a list of {"key", "keymap", "operator", "name"} for
    active-keyconfig items using the same key + modifiers in any of
    the keymaps we register into. Best-effort: any context problem
    yields an empty list, never an exception.
    """
    conflicts = []
    try:
        keyconfig = bpy.context.window_manager.keyconfigs.active
    except Exception:
        return []
    if keyconfig is None:
        return []
    for keymap_name in KEYMAP_NAMES:
        keymap = keyconfig.keymaps.get(keymap_name)
        if keymap is None:
            continue
        for entry in KEYMAP_TABLE:
            operator_id, key, modifiers, combo_key, combo_modifiers = entry
            use_key, use_modifiers = (
                (combo_key, combo_modifiers) if level == 2 else (key, modifiers)
            )
            for item in keymap.keymap_items:
                if item.idname == operator_id:
                    continue
                if item.type != use_key or item.value != "PRESS":
                    continue
                if (
                    item.alt == bool(use_modifiers.get("alt"))
                    and item.ctrl == bool(use_modifiers.get("ctrl"))
                    and item.shift == bool(use_modifiers.get("shift"))
                    and item.oskey == bool(use_modifiers.get("oskey"))
                ):
                    conflicts.append(
                        {
                            "key": use_key,
                            "keymap": keymap_name,
                            "operator": item.idname,
                            "name": item.name,
                        }
                    )
    return conflicts
