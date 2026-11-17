"""Version detection and API adaptation layer (4.x-5.x).

This is the ONLY module allowed to branch on the Blender version or probe
for API differences. Every other module calls the consistent interface
provided here; no ``bpy.app.version`` checks may be scattered elsewhere
(see proposal §5.6).
"""

import bpy


def version():
    """Return ``bpy.app.version`` as a ``(major, minor, patch)`` tuple."""
    return bpy.app.version


def version_string():
    major, minor, patch = bpy.app.version
    return "%d.%d.%d" % (major, minor, patch)


def at_least(major, minor, patch=0):
    return bpy.app.version >= (major, minor, patch)


def is_background():
    """True when Blender runs headless (no GPU context, no windows)."""
    return bool(bpy.app.background)


def has_translations():
    return hasattr(bpy.app, "translations")


def has_temp_override():
    return hasattr(bpy.context, "temp_override")


def has_extension_path_user():
    return hasattr(bpy.utils, "extension_path_user")


def addon_keyconfig():
    """Return the add-on keyconfig, or None when unavailable.

    Headless runs and restricted registration contexts may not provide
    one; callers must handle None.
    """
    try:
        wm = bpy.context.window_manager
        keyconfigs = wm.keyconfigs if wm is not None else None
        return keyconfigs.addon if keyconfigs is not None else None
    except AttributeError:
        return None


def temp_override(context, **keywords):
    """Context override using ``context.temp_override()`` (4.0+ API)."""
    return context.temp_override(**keywords)


def extension_user_path(package, create=False):
    """Per-extension user data directory (never assume it is writable)."""
    return bpy.utils.extension_path_user(package, create=create)


def check_shader_name(name):
    """Reject removed ``3D_``/``2D_``-prefixed shader names (4.0+)."""
    if name.startswith(("3D_", "2D_")):
        raise ValueError(
            "removed shader name %r: use the unprefixed name" % (name,)
        )
    return name


def feature_flags():
    """Snapshot of the API features this add-on depends on."""
    return {
        "version": version_string(),
        "background": is_background(),
        "translations": has_translations(),
        "temp_override": has_temp_override(),
        "extension_path_user": has_extension_path_user(),
        "addon_keyconfig": addon_keyconfig() is not None,
    }
