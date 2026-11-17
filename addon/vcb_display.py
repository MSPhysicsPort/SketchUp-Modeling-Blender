"""VCB text in the 3D View tool header (third display place).

The Measurements value shows in three places (proposal §3.7): the
viewport VCB box (primary, SketchUp-style), the N-panel, and this
tool-header label. The header only shows text while a SketchUp tool
is active and a VCB value/buffer exists.
"""

import bpy

from .i18n.translations import translate as _T


def _draw_tool_header(self, context):
    try:
        session = context.window_manager.sketchup_session
    except (AttributeError, ReferenceError):
        return
    if session is None or not session.active_tool:
        return
    text = session.vcb_text
    if not text:
        return
    self.layout.label(text=_T("VCB:") + " " + text)


def register():
    bpy.types.VIEW3D_HT_tool_header.append(_draw_tool_header)


def unregister():
    try:
        bpy.types.VIEW3D_HT_tool_header.remove(_draw_tool_header)
    except ValueError:
        pass
