"""Viewport overlay: inference markers, preview lines, ScreenTip,
VCB box, box-select rectangle. gpu + blf; fully background-guarded
(headless attach is a no-op) and exception-guarded (a draw failure
must never break the viewport).

Colors/shapes follow core/inference.py constants (configurable, D15).
Chinese ScreenTip/VCB text needs a CJK font for blf: a system font is
loaded when found, else the default font is used (English renders,
Chinese may show as boxes — real-machine verification item).
"""

import math
import os
import sys

import bpy

try:
    import blf
    import gpu
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    from gpu_extras.batch import batch_for_shader
    from mathutils import Vector

    _GPU_AVAILABLE = True
except ImportError:
    _GPU_AVAILABLE = False

_CJK_FONT_CANDIDATES = {
    "win32": [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\deng.ttf",
        r"C:\Windows\Fonts\msyhbd.ttc",
    ],
    "darwin": [
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/STHeiti Medium.ttc",
    ],
    "linux": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ],
}

MARKER_RADIUS_PX = 8.0
MARKER_SHAPES = {
    "endpoint": "circle",
    "midpoint": "circle",
    "center": "circle",
    "intersection": "cross",
    "guide_point": "diamond",
    "origin": "square",
    "on_edge": "square",
    "on_line": "diamond",
    "on_face": "square",
    "from_point": "circle",
    "axis": "circle",
    "free": None,
}


def find_cjk_font():
    """Return a loadable CJK font path, or None."""
    candidates = _CJK_FONT_CANDIDATES.get(sys.platform, [])
    if sys.platform.startswith("linux"):
        candidates = _CJK_FONT_CANDIDATES["linux"]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


class Overlay:
    def __init__(self):
        self.region = None
        self.rv3d = None
        self.handler_3d = None
        self.handler_2d = None
        self.font_id = 0
        self.markers = []  # (Vector world, kind, color)
        self.lines_3d = []  # (Vector, Vector, color, dashed)
        self.screentip = ("", (0, 0))  # (text, (x, y) screen)
        self.vcb_label = ""
        self.vcb_text = ""
        self.box_rect = None  # (x1, y1, x2, y2, color, dashed)
        self.lasso_points = []  # [(x, y)] screen polyline for the Lasso tool
        self.guide_lines = []  # [(point, direction)]
        self.guide_points = []  # [point]
        self._draw_error_reported = False

    # -- lifecycle -------------------------------------------------------

    @property
    def active(self):
        return self.handler_3d is not None or self.handler_2d is not None

    def attach(self, context):
        if bpy.app.background or not _GPU_AVAILABLE:
            return
        self.region = context.region
        self.rv3d = getattr(context.space_data, "region_3d", None)
        font_path = find_cjk_font()
        if font_path is not None:
            try:
                loaded = blf.load(font_path)
                if loaded >= 0:
                    self.font_id = loaded
            except Exception:
                pass
        try:
            self.handler_3d = bpy.types.SpaceView3D.draw_handler_add(
                self._draw_3d, (), "WINDOW", "POST_VIEW"
            )
            self.handler_2d = bpy.types.SpaceView3D.draw_handler_add(
                self._draw_2d, (), "WINDOW", "POST_PIXEL"
            )
        except Exception:
            self.handler_3d = None
            self.handler_2d = None

    def detach(self):
        for handler in (self.handler_3d, self.handler_2d):
            if handler is not None:
                try:
                    bpy.types.SpaceView3D.draw_handler_remove(handler, "WINDOW")
                except Exception:
                    pass
        self.handler_3d = None
        self.handler_2d = None
        self.region = None
        self.rv3d = None

    # -- data setters (called by tools each mouse move) ------------------

    def set_marker(self, point, kind, color):
        self.markers = [(Vector(point), kind, color)] if kind else []

    def set_lines(self, lines):
        self.lines_3d = list(lines)

    def set_screentip(self, text, xy):
        self.screentip = (text, xy)

    def set_vcb(self, label, text):
        self.vcb_label = label
        self.vcb_text = text

    def set_box_rect(self, rect):
        self.box_rect = rect

    def set_lasso(self, points):
        self.lasso_points = list(points)

    def set_guides(self, guide_lines, guide_points):
        self.guide_lines = list(guide_lines)
        self.guide_points = list(guide_points)

    def clear(self):
        self.markers = []
        self.lines_3d = []
        self.screentip = ("", (0, 0))
        self.box_rect = None
        self.lasso_points = []

    # -- drawing ---------------------------------------------------------

    def _draw_3d(self):
        try:
            self._draw_3d_inner()
        except Exception as exc:  # Never break the viewport.
            if not self._draw_error_reported:
                self._draw_error_reported = True
                print("SketchUp overlay 3D draw error: %r" % (exc,))

    def _draw_3d_inner(self):
        lines = list(self.lines_3d)
        guide_color = (1.0, 0.8, 0.0, 0.9)
        for point, direction in self.guide_lines:
            far_a = Vector(point) - Vector(direction) * 100.0
            far_b = Vector(point) + Vector(direction) * 100.0
            lines.append((far_a, far_b, guide_color, True))
        if not lines:
            return
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("NONE")
        try:
            for p1, p2, color, dashed in lines:
                segments = self._dash_segments(p1, p2) if dashed else [(p1, p2)]
                positions = []
                for a, b in segments:
                    positions.append(tuple(a))
                    positions.append(tuple(b))
                if not positions:
                    continue
                batch = batch_for_shader(shader, "LINES", {"pos": positions})
                shader.bind()
                shader.uniform_float("color", color)
                batch.draw(shader)
        finally:
            gpu.state.depth_test_set("LESS_EQUAL")
            gpu.state.blend_set("NONE")

    @staticmethod
    def _dash_segments(p1, p2, dash=0.05, gap=0.035):
        direction = Vector(p2) - Vector(p1)
        length = direction.length
        if length < 1e-9:
            return []
        direction.normalize()
        segments = []
        cursor = 0.0
        while cursor < length:
            end = min(cursor + dash, length)
            segments.append(
                (Vector(p1) + direction * cursor, Vector(p1) + direction * end)
            )
            cursor = end + gap
        return segments

    def _draw_2d(self):
        try:
            self._draw_2d_inner()
        except Exception as exc:
            if not self._draw_error_reported:
                self._draw_error_reported = True
                print("SketchUp overlay 2D draw error: %r" % (exc,))

    def _draw_2d_inner(self):
        self._draw_markers()
        self._draw_screentip()
        self._draw_box_rect()
        self._draw_lasso()
        self._draw_vcb_box()

    def _draw_markers(self):
        if self.region is None or self.rv3d is None:
            return
        markers = list(self.markers)
        for point in self.guide_points:
            markers.append((Vector(point), "guide_point", (1.0, 0.8, 0.0, 1.0)))
        if not markers:
            return
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        try:
            for point, kind, color in markers:
                shape = MARKER_SHAPES.get(kind)
                if shape is None:
                    continue
                xy = location_3d_to_region_2d(self.region, self.rv3d, point)
                if xy is None:
                    continue
                positions = self._marker_lines(shape, xy[0], xy[1], MARKER_RADIUS_PX)
                batch = batch_for_shader(shader, "LINES", {"pos": positions})
                shader.bind()
                shader.uniform_float("color", color)
                batch.draw(shader)
        finally:
            gpu.state.blend_set("NONE")

    @staticmethod
    def _marker_lines(shape, x, y, radius):
        lines = []
        if shape == "circle":
            segments = 16
            prev = None
            for i in range(segments + 1):
                angle = 2.0 * math.pi * i / segments
                point = (x + radius * math.cos(angle), y + radius * math.sin(angle), 0.0)
                if prev is not None:
                    lines.append(prev)
                    lines.append(point)
                prev = point
        elif shape == "square":
            corners = [
                (x - radius, y - radius, 0.0),
                (x + radius, y - radius, 0.0),
                (x + radius, y + radius, 0.0),
                (x - radius, y + radius, 0.0),
            ]
            for i in range(4):
                lines.append(corners[i])
                lines.append(corners[(i + 1) % 4])
        elif shape == "diamond":
            corners = [
                (x, y + radius, 0.0),
                (x + radius, y, 0.0),
                (x, y - radius, 0.0),
                (x - radius, y, 0.0),
            ]
            for i in range(4):
                lines.append(corners[i])
                lines.append(corners[(i + 1) % 4])
        elif shape == "cross":
            lines.extend(
                [
                    (x - radius, y - radius, 0.0),
                    (x + radius, y + radius, 0.0),
                    (x - radius, y + radius, 0.0),
                    (x + radius, y - radius, 0.0),
                ]
            )
        return lines

    def _text_size(self, text, size=14):
        blf.size(self.font_id, size)
        width, height = blf.dimensions(self.font_id, text)
        return width, height

    def _draw_text_box(self, text, x, y, size=14, bg=(0.08, 0.08, 0.08, 0.85)):
        if not text:
            return 0.0, 0.0
        pad_x, pad_y = 6.0, 4.0
        width, height = self._text_size(text, size)
        box_w, box_h = width + pad_x * 2, height + pad_y * 2
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        try:
            quad = [
                (x, y, 0.0),
                (x + box_w, y, 0.0),
                (x + box_w, y + box_h, 0.0),
                (x, y, 0.0),
                (x + box_w, y + box_h, 0.0),
                (x, y + box_h, 0.0),
            ]
            batch = batch_for_shader(shader, "TRIS", {"pos": quad})
            shader.bind()
            shader.uniform_float("color", bg)
            batch.draw(shader)
        finally:
            gpu.state.blend_set("NONE")
        blf.size(self.font_id, size)
        blf.color(self.font_id, 1.0, 1.0, 1.0, 1.0)
        blf.position(self.font_id, x + pad_x, y + pad_y, 0.0)
        blf.draw(self.font_id, text)
        return box_w, box_h

    def _draw_screentip(self):
        text, (x, y) = self.screentip
        if not text:
            return
        self._draw_text_box(text, x + 14, y + 14)

    def _draw_box_rect(self):
        if self.box_rect is None:
            return
        x1, y1, x2, y2, color, dashed = self.box_rect
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        try:
            fill = [
                (x1, y1, 0.0),
                (x2, y1, 0.0),
                (x2, y2, 0.0),
                (x1, y1, 0.0),
                (x2, y2, 0.0),
                (x1, y2, 0.0),
            ]
            batch = batch_for_shader(shader, "TRIS", {"pos": fill})
            shader.bind()
            shader.uniform_float("color", (color[0], color[1], color[2], 0.08))
            batch.draw(shader)
            corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
            lines = []
            for i in range(4):
                a, b = corners[i], corners[(i + 1) % 4]
                if dashed:
                    seg_len = math.hypot(b[0] - a[0], b[1] - a[1])
                    steps = max(1, int(seg_len / 8))
                    for s in range(steps):
                        if s % 2 == 0:
                            t0, t1 = s / steps, min(1.0, (s + 0.7) / steps)
                            lines.append((a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0, 0.0))
                            lines.append((a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1, 0.0))
                else:
                    lines.append((a[0], a[1], 0.0))
                    lines.append((b[0], b[1], 0.0))
            batch = batch_for_shader(shader, "LINES", {"pos": lines})
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)
        finally:
            gpu.state.blend_set("NONE")

    def _draw_lasso(self):
        points = self.lasso_points
        if len(points) < 2:
            return
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        try:
            lines = []
            closed = points + [points[0]]
            for i in range(len(closed) - 1):
                a, b = closed[i], closed[i + 1]
                lines.append((a[0], a[1], 0.0))
                lines.append((b[0], b[1], 0.0))
            batch = batch_for_shader(shader, "LINES", {"pos": lines})
            shader.bind()
            shader.uniform_float("color", (0.2, 0.5, 1.0, 0.9))
            batch.draw(shader)
        finally:
            gpu.state.blend_set("NONE")

    def _draw_vcb_box(self):
        if self.region is None:
            return
        text = self.vcb_text
        if not text and not self.vcb_label:
            return
        display = ("%s: %s" % (self.vcb_label, text)) if self.vcb_label else text
        if not display:
            return
        pad_x = 6.0
        width, _height = self._text_size(display)
        box_w = width + pad_x * 2
        x = self.region.width - box_w - 12
        self._draw_text_box(display, x, 12, size=14)
