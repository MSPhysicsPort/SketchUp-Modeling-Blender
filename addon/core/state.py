"""Session state (pure Python, no bpy) + VCB keystroke buffer.

Two storage classes (research/02 §10.6): model data that must be
saved with the file goes to PropertyGroups / ID Properties; session
state (inference lock, hover reference, VCB buffer, guides, drawing
axes) lives in this module-level singleton and never touches the
file or Undo. `reset_session()` clears it on unregister.
"""

from . import inference
from .vcb import parse_vcb


class DrawingAxes:
    """Drawing axes: origin + three unit directions (default = world).

    The Axes tool (P6) reorients this; inference and VCB coordinate
    input both take it as their reference (proposal §3.9).
    """

    def __init__(self, origin=(0.0, 0.0, 0.0), x=(1.0, 0.0, 0.0), y=(0.0, 1.0, 0.0), z=(0.0, 0.0, 1.0)):
        self.origin = tuple(origin)
        self.x = inference.vnorm(x)
        self.y = inference.vnorm(y)
        self.z = inference.vnorm(z)

    def as_axes(self):
        return inference.Axes(self.origin, self.x, self.y, self.z)

    def reset(self):
        self.__init__()

    def to_dict(self):
        return {
            "origin": list(self.origin),
            "x": list(self.x),
            "y": list(self.y),
            "z": list(self.z),
        }

    @classmethod
    def from_dict(cls, data):
        try:
            return cls(
                origin=tuple(data["origin"]),
                x=tuple(data["x"]),
                y=tuple(data["y"]),
                z=tuple(data["z"]),
            )
        except (KeyError, TypeError, ValueError):
            return cls()


class VCBBuffer:
    """Keystroke buffer for Measurements input inside modal tools.

    Characters arrive one key at a time; Enter commits the text
    through the VCB parser, Escape/Right-click clears it. The buffer
    holds raw text only — parsing happens at commit time.
    """

    def __init__(self):
        self.text = ""

    @property
    def is_empty(self):
        return self.text == ""

    def feed(self, char):
        if len(char) == 1:
            self.text += char

    def backspace(self):
        self.text = self.text[:-1]

    def clear(self):
        self.text = ""

    def commit(self, kind, default_unit="mm"):
        """Parse and clear; returns the parser's value, None if empty.

        kind selects the VCB parser ("length", "coordinate", "angle",
        "count", "array", "scale", ...); see core/vcb.py. On a parse
        error the ValueError propagates and the text is kept, so the
        user can correct it instead of retyping.
        """
        if self.is_empty:
            return None
        result = parse_vcb(self.text, kind, default_unit=default_unit)
        self.text = ""
        return result


class SessionState:
    """All per-session (non-saved) plugin state in one place."""

    def __init__(self):
        try:
            from ..data.guides import GuideSet
        except (ImportError, ValueError):
            # T1 shim imports `core` as a top-level package.
            from data.guides import GuideSet

        self.axes = DrawingAxes()
        self.lock = inference.LockState()
        self.vcb = VCBBuffer()
        self.guides = GuideSet()
        self.from_point = None
        self.hover_point = None
        self.hover_since = None
        self.active_tool_id = None
        self.last_line_direction = None
        # Edit-context stack (proposal §3.6): object names, root
        # first, current last. Empty until SU Mode turns on.
        self.context_stack = []
        # Container object picked (single click) by the Select tool,
        # awaiting a double-click to enter its edit context.
        self.selected_container = None
        # View toggles (View menu, proposal §3.4/P4-P6).
        self.show_hidden_geometry = False
        self.show_back_edges = False
        # Hide batches for Unhide Last: dicts {"kind": "mesh",
        # "object": name, "faces": [...], "edges": [...]} or
        # {"kind": "objects", "names": [...]}.
        self.hidden_history = []
        # Camera view history: entries are (location, rotation,
        # distance, perspective) tuples; index points at current.
        self.view_history = []
        self.view_history_index = -1

    def reset(self):
        self.__init__()


_SESSION = None


def get_session():
    global _SESSION
    if _SESSION is None:
        _SESSION = SessionState()
    return _SESSION


def reset_session():
    global _SESSION
    _SESSION = None
