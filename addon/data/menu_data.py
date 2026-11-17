"""Menu and toolbar data tables.

Single source of truth driving the header menu, the N-panel and the
toolbar (proposal §2.5): all three UIs are generated from these tables,
so correcting the layout means editing this file only.

Contents verified against Sen's real-machine screenshots on 2026-11-17
(proposal §2.2/§2.3). Items whose English label is unknown keep
``label=None`` and carry ``label_cn`` from the screenshot; never invent
a label. Submenus not yet expanded on the real machine carry a single
``note`` item instead of guessed contents (D1 remainder).

Item fields:
    id: stable snake_case identifier (also the stub operator's tool_id).
    label: English msgid (UI text; Chinese lives in i18n/translations.py).
    label_cn: screenshot Chinese label, only when the English label is
        unknown (label=None).
    shortcut: SketchUp default shortcut as seen on the screenshot
        (documentation; keymap binding arrives with the tools).
    scope: "in" (rendered) or "out" (kept as data, not rendered:
        online services, photo matching, dynamic components).
    submenu: nested item list.
    note: placeholder text for unverified submenu contents.
    separator: True for a separator row.
"""

# ---------------------------------------------------------------------------
# Tools menu (8 groups, verified)
# ---------------------------------------------------------------------------

MENU_TOOLS = [
    {"id": "select", "label": "Select", "shortcut": "Space", "operator": "sketchup.tool_select"},
    {"id": "lasso", "label": "Lasso", "shortcut": "Shift+Space", "operator": "sketchup.tool_lasso"},
    {"id": "eraser", "label": "Eraser", "shortcut": "E", "operator": "sketchup.tool_eraser"},
    {"id": "paint_bucket", "label": "Paint Bucket", "shortcut": "B", "operator": "sketchup.tool_paint_bucket"},
    {"id": "tag", "label": "Tag", "operator": "sketchup.tool_tag"},
    {"separator": True},
    {"id": "move", "label": "Move", "shortcut": "M", "operator": "sketchup.tool_move"},
    {"id": "rotate", "label": "Rotate", "shortcut": "Q", "operator": "sketchup.tool_rotate"},
    {"id": "scale", "label": "Scale", "shortcut": "S", "operator": "sketchup.tool_scale"},
    {"id": "flip", "label": "Flip", "operator": "sketchup.tool_flip"},
    {"separator": True},
    {"id": "push_pull", "label": "Push/Pull", "shortcut": "P", "operator": "sketchup.tool_push_pull"},
    {"id": "follow_me", "label": "Follow Me", "operator": "sketchup.tool_follow_me"},
    {"id": "offset", "label": "Offset", "shortcut": "F", "operator": "sketchup.tool_offset"},
    {"separator": True},
    {"id": "outer_shell", "label": "Outer Shell", "operator": "sketchup.solid_outer_shell"},
    {
        "id": "solid_tools",
        "label": "Solid Tools",
        "submenu": [
            {"id": "solid_union", "label": "Union", "operator": "sketchup.solid_union"},
            {"id": "solid_subtract", "label": "Subtract", "operator": "sketchup.solid_subtract"},
            {"id": "solid_trim", "label": "Trim", "operator": "sketchup.solid_trim"},
            {"id": "solid_intersect", "label": "Intersect", "operator": "sketchup.solid_intersect"},
            {"id": "solid_split", "label": "Split", "operator": "sketchup.solid_split"},
        ],
    },
    {"separator": True},
    {"id": "tape_measure", "label": "Tape Measure", "shortcut": "T", "operator": "sketchup.tool_tape_measure"},
    {"id": "protractor", "label": "Protractor", "operator": "sketchup.tool_protractor"},
    {"id": "axes", "label": "Axes", "operator": "sketchup.tool_axes"},
    {"separator": True},
    {"id": "dimensions", "label": "Dimensions", "operator": "sketchup.tool_dimension"},
    {"id": "text", "label": "Text", "operator": "sketchup.tool_text"},
    {"id": "text_3d", "label": "3D Text", "operator": "sketchup.text_3d"},
    {"separator": True},
    {"id": "section_plane", "label": "Section Plane", "operator": "sketchup.tool_section_plane"},
    {"separator": True},
    # Dynamic Components: out of scope (proposal §4.2, D11).
    {"id": "interact", "label": "Interact", "scope": "out"},
]

# ---------------------------------------------------------------------------
# Draw menu (3 submenus, all expanded and verified)
# ---------------------------------------------------------------------------

MENU_DRAW = [
    {
        "id": "lines",
        "label": "Lines",
        "submenu": [
            {"id": "line", "label": "Line", "shortcut": "L", "operator": "sketchup.tool_line"},
            {"id": "freehand", "label": "Freehand", "operator": "sketchup.tool_freehand"},
        ],
    },
    {
        "id": "arcs",
        "label": "Arcs",
        "submenu": [
            {"id": "arc", "label": "Arc", "operator": "sketchup.tool_arc"},
            {"id": "arc_2_point", "label": "2-Point Arc", "shortcut": "A", "operator": "sketchup.tool_arc_2_point"},
            {"id": "arc_3_point", "label": "3-Point Arc", "operator": "sketchup.tool_arc_3_point"},
            {"id": "pie", "label": "Pie", "operator": "sketchup.tool_pie"},
        ],
    },
    {
        "id": "shapes",
        "label": "Shapes",
        "submenu": [
            {"id": "rectangle", "label": "Rectangle", "shortcut": "R", "operator": "sketchup.tool_rectangle"},
            {"id": "rotated_rectangle", "label": "Rotated Rectangle", "operator": "sketchup.tool_rotated_rectangle"},
            {"id": "circle", "label": "Circle", "shortcut": "C", "operator": "sketchup.tool_circle"},
            {"id": "polygon", "label": "Polygon", "operator": "sketchup.tool_polygon"},
        ],
    },
]

# ---------------------------------------------------------------------------
# Camera menu (5 groups, verified; photo-matching items out of scope)
# ---------------------------------------------------------------------------

MENU_CAMERA = [
    {"id": "view_previous", "label": "Previous", "operator": "sketchup.view_previous"},
    {"id": "view_next", "label": "Next", "operator": "sketchup.view_next"},
    {
        "id": "standard_views",
        "label": "Standard Views",
        "submenu": [
            {"id": "view_top", "label": "Top", "shortcut": "F2", "operator": "sketchup.view_top"},
            {"id": "view_bottom", "label": "Bottom", "operator": "sketchup.view_bottom"},
            {"id": "view_front", "label": "Front", "shortcut": "F3", "operator": "sketchup.view_front"},
            {"id": "view_back", "label": "Back", "operator": "sketchup.view_back"},
            {"id": "view_left", "label": "Left", "shortcut": "F4", "operator": "sketchup.view_left"},
            {"id": "view_right", "label": "Right", "shortcut": "F5", "operator": "sketchup.view_right"},
            {"id": "view_iso", "label": "Iso", "operator": "sketchup.view_iso"},
        ],
    },
    {"separator": True},
    {"id": "parallel_projection", "label": "Parallel Projection", "shortcut": "N", "operator": "sketchup.parallel_projection", "props": {"mode": "ORTHO"}},
    {"id": "perspective", "label": "Perspective", "operator": "sketchup.parallel_projection", "props": {"mode": "PERSP"}},
    {"id": "two_point_perspective", "label": "Two-Point Perspective", "operator": "sketchup.two_point_perspective"},
    {"separator": True},
    # Photo matching: out of scope (proposal §4.2).
    {"id": "match_new_photo", "label": "Match New Photo", "scope": "out"},
    {"id": "edit_matched_photo", "label": "Edit Matched Photo", "scope": "out"},
    {"separator": True},
    {"id": "orbit", "label": "Orbit", "shortcut": "O", "operator": "sketchup.tool_orbit"},
    {"id": "pan", "label": "Pan", "shortcut": "H", "operator": "sketchup.tool_pan"},
    {"id": "zoom", "label": "Zoom", "shortcut": "Z", "operator": "sketchup.tool_zoom"},
    {"id": "field_of_view", "label": "Field of View", "operator": "sketchup.field_of_view"},
    {"id": "zoom_window", "label": "Zoom Window", "shortcut": "Ctrl+Shift+W", "operator": "sketchup.tool_zoom_window"},
    {"id": "zoom_extents", "label": "Zoom Extents", "shortcut": "Ctrl+Shift+E", "operator": "sketchup.zoom_extents"},
    # English mapping unverified; photo-matching related, out of scope.
    {"id": "zoom_to_photo", "label": None, "label_cn": "背景充满视窗", "scope": "out"},
    {"separator": True},
    {"id": "position_camera", "label": "Position Camera", "operator": "sketchup.tool_position_camera"},
    {"id": "walk", "label": "Walk", "operator": "sketchup.tool_walk"},
    {"id": "look_around", "label": "Look Around", "operator": "sketchup.tool_look_around"},
    # English mapping unverified; photo-matching related, out of scope.
    {"id": "preview_matched_photo", "label": None, "label_cn": "预览匹配照片", "shortcut": "I", "scope": "out"},
]

# ---------------------------------------------------------------------------
# Edit-menu modeling commands (verified list; wired to operators in P4-P6).
# The full Edit menu (undo/redo, copy/paste) is not replicated per
# proposal §2.1 — Blender's own Edit menu covers those.
# ---------------------------------------------------------------------------

EDIT_COMMANDS = [
    {"id": "delete_guides", "label": "Delete Guides", "operator": "sketchup.delete_guides"},
    {"id": "select_all", "label": "Select All", "shortcut": "Ctrl+A", "operator": "sketchup.select_all"},
    {"id": "deselect_all", "label": "Deselect All", "shortcut": "Ctrl+T", "operator": "sketchup.deselect_all"},
    {"id": "invert_selection", "label": "Invert Selection", "shortcut": "Ctrl+Shift+I", "operator": "sketchup.invert_selection"},
    {"id": "hide", "label": "Hide", "shortcut": "Ctrl+H", "operator": "sketchup.hide"},
    {
        "id": "unhide",
        "label": "Unhide",
        "submenu": [
            {"id": "unhide_all", "label": "All", "operator": "sketchup.unhide_all"},
            {"id": "unhide_last", "label": "Last", "operator": "sketchup.unhide_last"},
        ],
    },
    {"id": "lock", "label": "Lock", "operator": "sketchup.lock_selection"},
    {
        "id": "unlock",
        "label": "Unlock",
        "submenu": [
            {"id": "unlock_all", "label": "All", "operator": "sketchup.unlock_selection", "props": {"all_locked": True}},
            {"id": "unlock_selected", "label": "Selected", "operator": "sketchup.unlock_selection"},
        ],
    },
    {"id": "make_component", "label": "Make Component", "operator": "sketchup.make_component"},
    {"id": "make_group", "label": "Make Group", "shortcut": "G", "operator": "sketchup.make_group"},
    {"id": "close_group_component", "label": "Close Group/Component", "operator": "sketchup.close_group_component"},
    {
        "id": "intersect_faces",
        "label": "Intersect Faces",
        "submenu": [
            {"id": "intersect_with_model", "label": "With Model", "operator": "sketchup.intersect_faces", "props": {"scope": "MODEL"}},
            {"id": "intersect_with_context", "label": "With Context", "operator": "sketchup.intersect_faces", "props": {"scope": "CONTEXT"}},
            {"id": "intersect_with_selection", "label": "With Selection", "operator": "sketchup.intersect_faces", "props": {"scope": "SELECTION"}},
        ],
    },
]

# Top-level menus in SketchUp menubar order (Edit, Camera, Draw, Tools).
MENUS = [
    {"id": "edit", "label": "Edit", "items": EDIT_COMMANDS},
    {"id": "camera", "label": "Camera", "items": MENU_CAMERA},
    {"id": "draw", "label": "Draw", "items": MENU_DRAW},
    {"id": "tools", "label": "Tools", "items": MENU_TOOLS},
]


# ---------------------------------------------------------------------------
# Toolbar layouts (verified; used by later phases, documented here so the
# P0 data table already holds the full verified structure).
# ---------------------------------------------------------------------------

# Getting Started: 23 slots in reading order. "flyout" lists the tools
# behind the drop-down arrow (research-based, not screenshot-verified).
TOOLBAR_GETTING_STARTED = [
    {"id": "search", "label": "Search", "kind": "search_box"},
    {"separator": True},
    {"id": "select", "label": "Select", "flyout": ["lasso"]},
    {"separator": True},
    {"id": "eraser", "label": "Eraser"},
    {"id": "line", "label": "Line", "flyout": ["freehand"]},
    {"id": "arc", "label": "Arc", "flyout": ["arc_2_point", "arc_3_point", "pie"]},
    {"id": "rectangle", "label": "Rectangle", "flyout": ["rotated_rectangle", "circle", "polygon"]},
    {"separator": True},
    {"id": "push_pull", "label": "Push/Pull"},
    {"id": "offset", "label": "Offset"},
    {"id": "move", "label": "Move"},
    {"id": "rotate", "label": "Rotate"},
    {"id": "scale", "label": "Scale"},
    {"id": "flip", "label": "Flip"},
    {"separator": True},
    {"id": "tape_measure", "label": "Tape Measure"},
    {"id": "paint_bucket", "label": "Paint Bucket"},
    {"separator": True},
    {"id": "orbit", "label": "Orbit"},
    {"id": "pan", "label": "Pan"},
    {"id": "zoom", "label": "Zoom"},
    {"id": "zoom_extents", "label": "Zoom Extents"},
    {"separator": True},
    {"id": "warehouse_3d", "label": "3D Warehouse", "scope": "out"},
    {"id": "extension_warehouse", "label": "Extension Warehouse", "scope": "out"},
    {"id": "send_to_layout", "label": "Send to LayOut", "scope": "out"},
    {"separator": True},
    {"id": "extension_manager", "label": "Extension Manager", "scope": "out"},
    {"separator": True},
    {"id": "user_info", "label": "User Info", "scope": "out"},
]

# Large Tool Set: 7 groups of left|right pairs (second screenshot).
TOOLBAR_LARGE = [
    [("select", "lasso"), ("paint_bucket", "eraser"), ("make_component", "tag")],
    [("line", "freehand"), ("rectangle", "rotated_rectangle"), ("circle", "polygon"),
     ("arc", "arc_2_point"), ("arc_3_point", "pie")],
    [("move", "push_pull"), ("rotate", "follow_me"), ("scale", "offset"), ("axes", "flip")],
    [("tape_measure", "dimensions"), ("protractor", "text"), ("section_plane", "text_3d")],
    [("orbit", "pan"), ("zoom", "zoom_window"), ("zoom_extents", "view_previous")],
    [("position_camera", "walk"), ("look_around", "field_of_view")],
    [("warehouse_3d", "extension_warehouse"), ("send_to_layout", "extension_manager")],
]


def iter_tool_ids(items=None):
    """Yield every in-scope tool id from the menu tables (deduped)."""
    seen = set()
    stack = list(items) if items is not None else [
        item for menu in MENUS for item in menu["items"]
    ]
    while stack:
        item = stack.pop()
        if "submenu" in item:
            stack.extend(item["submenu"])
            continue
        tool_id = item.get("id")
        if tool_id and item.get("scope", "in") == "in" and tool_id not in seen:
            seen.add(tool_id)
            yield tool_id
