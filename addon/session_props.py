"""WindowManager session properties: the VCB text and active tool
shown in the N-panel and the tool header. Session-only state that
must be visible to panels (which cannot read module state reliably
across redraws); never saved with the file.
"""

import bpy


class SketchUpSessionProps(bpy.types.PropertyGroup):
    vcb_text: bpy.props.StringProperty(name="VCB", default="")
    active_tool: bpy.props.StringProperty(name="Active Tool", default="")


def register():
    bpy.utils.register_class(SketchUpSessionProps)
    bpy.types.WindowManager.sketchup_session = bpy.props.PointerProperty(
        type=SketchUpSessionProps
    )


def unregister():
    del bpy.types.WindowManager.sketchup_session
    bpy.utils.unregister_class(SketchUpSessionProps)


def set_vcb_text(context, text):
    """Update the shared VCB text (guarded: any context may lack it)."""
    try:
        session = context.window_manager.sketchup_session
    except (AttributeError, ReferenceError):
        return
    if session is not None:
        session.vcb_text = text


def set_active_tool(context, tool_id):
    try:
        session = context.window_manager.sketchup_session
    except (AttributeError, ReferenceError):
        return
    if session is not None:
        session.active_tool = tool_id or ""
