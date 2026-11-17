"""Persistent viewport overlay (P6): drawn while SU Mode is on,
independent of the active tool. Guides, section planes, drawing
axes, dimensions / text notes, the edit-context box, back edges,
hidden edges, axis-colored edges, and tag-colored bounds.
Fully background-guarded and exception-guarded: a draw failure
must never break the viewport.
"""

import bmesh
import bpy
from mathutils import Vector

try:
    import blf
    import gpu
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    from gpu_extras.batch import batch_for_shader

    _GPU_AVAILABLE = True
except ImportError:
    _GPU_AVAILABLE = False

from ..core.geometry import EDGE_FLAGS_LAYER, FLAG_HIDDEN
from ..core.state import get_session
from ..core.units import DEFAULT_UNIT, format_length
from ..data import annotations as annotations_mod
from ..data import sections as sections_mod
from ..data import tags as tags_mod
from .overlay import find_cjk_font

GUIDE_COLOR = (1.0, 0.0, 1.0, 0.85)
GUIDE_POINT_COLOR = (1.0, 0.8, 0.0, 1.0)
SECTION_ACTIVE_COLOR = (1.0, 0.55, 0.0, 0.9)
SECTION_IDLE_COLOR = (0.5, 0.5, 0.5, 0.7)
BACK_EDGE_COLOR = (0.4, 0.4, 0.4, 0.6)
HIDDEN_EDGE_COLOR = (0.3, 0.3, 0.3, 0.9)
CONTEXT_BOX_COLOR = (0.4, 0.4, 0.4, 0.8)
AXIS_COLORS = (
    (1.0, 0.2, 0.2, 1.0),
    (0.2, 0.8, 0.2, 1.0),
    (0.2, 0.4, 1.0, 1.0),
)
DIMENSION_COLOR = (0.1, 0.1, 0.1, 1.0)
MAX_EDGE_SEGMENTS = 20000


def _default_unit():
    try:
        addon_key = __package__.rsplit(".", 1)[0]
        addon = bpy.context.preferences.addons.get(addon_key)
        if addon is not None:
            return addon.preferences.default_unit
    except Exception:
        pass
    return DEFAULT_UNIT


def _dashed_segments(a, b, dash=0.08):
    length = (b - a).length
    if length < 1e-9:
        return []
    count = max(1, int(length / dash))
    segments = []
    for i in range(count):
        if i % 2 == 0:
            t0 = i / count
            t1 = min(1.0, (i + 0.7) / count)
            segments.append((a + (b - a) * t0, a + (b - a) * t1))
    return segments


def _draw_lines(segments, color, dashed=False, depth_test="LESS"):
    if not segments:
        return
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    gpu.state.depth_test_set(depth_test)
    try:
        points = []
        for a, b in segments:
            pieces = _dashed_segments(a, b) if dashed else [(a, b)]
            for p, q in pieces:
                points.append(tuple(p))
                points.append(tuple(q))
        if not points:
            return
        batch = batch_for_shader(shader, "LINES", {"pos": points})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
    finally:
        gpu.state.depth_test_set("LESS")
        gpu.state.blend_set("NONE")


def _draw_filled_quad(corners, color):
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    try:
        fill = [
            tuple(corners[0]), tuple(corners[1]), tuple(corners[2]),
            tuple(corners[0]), tuple(corners[2]), tuple(corners[3]),
        ]
        batch = batch_for_shader(shader, "TRIS", {"pos": fill})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
    finally:
        gpu.state.blend_set("NONE")


class _ViewportOverlay:
    def __init__(self):
        self.handler_3d = None
        self.handler_2d = None
        self.font_id = 0
        self._error_reported = False
        self._texts = []  # (world co, text) collected in the 3D pass
        self._edge_cache = {}  # obj name -> (signature, edges, hidden, axis)
        self._draw_count = 0

    @property
    def active(self):
        return self.handler_3d is not None

    def attach(self):
        if bpy.app.background or not _GPU_AVAILABLE or self.active:
            return
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
        self._edge_cache.clear()

    # -- 3D pass -----------------------------------------------------------

    def _draw_3d(self):
        try:
            self._draw_3d_inner()
        except Exception as exc:
            if not self._error_reported:
                self._error_reported = True
                print("SketchUp viewport overlay error: %r" % (exc,))

    def _draw_3d_inner(self):
        context = bpy.context
        scene = context.scene
        if scene is None:
            return
        space = context.space_data
        rv3d = getattr(space, "region_3d", None) if space else None
        if rv3d is None:
            return
        session = get_session()
        self._texts = []
        self._draw_count += 1
        self._draw_guides(session, rv3d)
        self._draw_sections(scene)
        self._draw_axes(session, rv3d)
        self._draw_annotations(scene)
        self._draw_context_box(session)
        self._draw_mesh_edges(scene, session)
        if scene.get("su_color_by_tag", False):
            self._draw_tag_bounds(scene)

    def _draw_guides(self, session, rv3d):
        guides = session.guides
        reach = max(rv3d.view_distance * 5.0, 10.0)
        segments = []
        for point, direction in guides.lines:
            center = Vector(point)
            direction = Vector(direction)
            segments.append((center - direction * reach, center + direction * reach))
        _draw_lines(segments, GUIDE_COLOR, dashed=True)
        crosses = []
        size = max(rv3d.view_distance * 0.01, 0.02)
        for point in guides.points:
            center = Vector(point)
            for axis in range(3):
                offset = Vector((0, 0, 0))
                offset[axis] = size
                crosses.append((center - offset, center + offset))
        _draw_lines(crosses, GUIDE_POINT_COLOR)

    def _draw_sections(self, scene):
        planes = sections_mod.list_sections(scene)
        if not planes:
            return
        size = max(min(sections_mod._scene_bounds(scene) * 0.5, 50.0), 1.0)
        active = sections_mod.get_active_section(scene)
        for plane in planes:
            origin, normal = sections_mod.plane_frame(plane)
            helper = Vector((1, 0, 0)) if abs(normal.x) < 0.9 else Vector((0, 1, 0))
            u = normal.cross(helper).normalized()
            v = normal.cross(u)
            corners = [
                origin + (+u + v) * size,
                origin + (-u + v) * size,
                origin + (-u - v) * size,
                origin + (+u - v) * size,
            ]
            color = SECTION_ACTIVE_COLOR if plane is active else SECTION_IDLE_COLOR
            _draw_filled_quad(corners, (color[0], color[1], color[2], 0.06))
            _draw_lines(
                [(corners[i], corners[(i + 1) % 4]) for i in range(4)],
                color,
            )

    def _draw_axes(self, session, rv3d):
        axes = session.axes
        origin = Vector(axes.origin)
        length = max(rv3d.view_distance * 0.12, 0.5)
        for index, direction in enumerate((axes.x, axes.y, axes.z)):
            end = origin + Vector(direction) * length
            _draw_lines([(origin, end)], AXIS_COLORS[index])
            self._texts.append((end, "XYZ"[index]))

    def _draw_annotations(self, scene):
        unit = _default_unit()
        for entry in annotations_mod.get_annotations(scene):
            if entry.get("type") == "dimension":
                p1 = annotations_mod.resolve_point(scene, entry, "ref1")
                p2 = annotations_mod.resolve_point(scene, entry, "ref2")
                offset = Vector(entry["offset"])
                layout = annotations_mod.dimension_geometry(p1, p2, offset)
                if layout is None:
                    continue
                _draw_lines(
                    [
                        (layout["dim_a"], layout["dim_b"]),
                        layout["ext1"],
                        layout["ext2"],
                    ],
                    DIMENSION_COLOR,
                )
                # Arrowheads: short ticks at both ends.
                direction = layout["direction"]
                tick = min(0.1, layout["length"] * 0.1)
                perp = Vector(direction).orthogonal()
                for end, sign in ((layout["dim_a"], 1), (layout["dim_b"], -1)):
                    tip = end + direction * sign * tick
                    _draw_lines(
                        [(end + perp * tick * 0.5, tip),
                         (end - perp * tick * 0.5, tip)],
                        DIMENSION_COLOR,
                    )
                self._texts.append(
                    (
                        layout["text_point"],
                        format_length(layout["length"], unit, precision=1),
                    )
                )
            elif entry.get("type") == "text":
                point = Vector(entry["point"])
                anchor = point + Vector(entry["anchor_offset"])
                _draw_lines([(point, anchor)], DIMENSION_COLOR)
                self._texts.append((anchor, entry.get("text", "")))

    def _draw_context_box(self, session):
        stack = session.context_stack
        if len(stack) <= 1:
            return
        obj = bpy.data.objects.get(stack[-1])
        if obj is None or obj.type != "MESH":
            return
        corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        pairs = [
            (0, 1), (1, 3), (3, 2), (2, 0),
            (4, 5), (5, 7), (7, 6), (6, 4),
            (0, 4), (1, 5), (2, 6), (3, 7),
        ]
        _draw_lines(
            [(corners[a], corners[b]) for a, b in pairs],
            CONTEXT_BOX_COLOR,
            dashed=True,
        )

    # -- mesh edges (back / hidden / by-axis) -------------------------------

    def _mesh_edges(self, obj):
        """(all, hidden, axis-colored) world-space edge segments,
        cached by a mesh signature and refreshed periodically."""
        mesh = obj.data
        signature = (
            len(mesh.vertices),
            len(mesh.edges),
            len(mesh.polygons),
            obj.mode,
            self._draw_count // 60,
        )
        cached = self._edge_cache.get(obj.name)
        if cached is not None and cached[0] == signature:
            return cached[1], cached[2], cached[3]
        matrix = obj.matrix_world
        edges = []
        hidden = []
        axis = []
        axes = get_session().axes
        axis_dirs = [Vector(axes.x), Vector(axes.y), Vector(axes.z)]
        live = None
        bm = None
        try:
            if obj.mode == "EDIT":
                live = bmesh.from_edit_mesh(mesh)
                bm = live
            else:
                bm = bmesh.new()
                bm.from_mesh(mesh)
            layer = bm.edges.layers.int.get(EDGE_FLAGS_LAYER)
            for edge in bm.edges:
                a = matrix @ edge.verts[0].co
                b = matrix @ edge.verts[1].co
                edges.append((a, b))
                if layer is not None and (edge[layer] & FLAG_HIDDEN):
                    hidden.append((a, b))
                direction = b - a
                if direction.length > 1e-9:
                    direction.normalize()
                    for index, axis_dir in enumerate(axis_dirs):
                        if abs(direction.dot(axis_dir)) > 0.9999:
                            axis.append(((a, b), index))
                            break
        except Exception:
            pass
        finally:
            if live is None and bm is not None:
                bm.free()
        if len(edges) > MAX_EDGE_SEGMENTS:
            edges = edges[:MAX_EDGE_SEGMENTS]
        self._edge_cache[obj.name] = (signature, edges, hidden, axis)
        return edges, hidden, axis

    def _draw_mesh_edges(self, scene, session):
        show_back = session.show_back_edges
        show_hidden = session.show_hidden_geometry
        show_axis = scene.get("su_color_by_axis", False)
        if not (show_back or show_hidden or show_axis):
            return
        for obj in scene.objects:
            if obj.type != "MESH" or obj.hide_viewport:
                continue
            try:
                if obj.hide_get():
                    continue
            except Exception:
                pass
            edges, hidden, axis = self._mesh_edges(obj)
            if show_back and edges:
                _draw_lines(edges, BACK_EDGE_COLOR, dashed=True, depth_test="GREATER")
            if show_hidden and hidden:
                _draw_lines(hidden, HIDDEN_EDGE_COLOR, dashed=True)
            if show_axis and axis:
                for index in range(3):
                    segments = [seg for seg, axis_index in axis if axis_index == index]
                    _draw_lines(segments, AXIS_COLORS[index])

    def _draw_tag_bounds(self, scene):
        tags_mod.ensure_defaults(scene)
        for obj in scene.objects:
            if obj.type != "MESH" or obj.hide_viewport:
                continue
            color = tags_mod.tag_color(scene, tags_mod.object_tag(obj))
            corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
            pairs = [
                (0, 1), (1, 3), (3, 2), (2, 0),
                (4, 5), (5, 7), (7, 6), (6, 4),
                (0, 4), (1, 5), (2, 6), (3, 7),
            ]
            _draw_lines(
                [(corners[a], corners[b]) for a, b in pairs],
                (color[0], color[1], color[2], 0.6),
            )

    # -- 2D pass -----------------------------------------------------------

    def _draw_2d(self):
        try:
            self._draw_2d_inner()
        except Exception as exc:
            if not self._error_reported:
                self._error_reported = True
                print("SketchUp viewport overlay error: %r" % (exc,))

    def _draw_2d_inner(self):
        if not self._texts:
            return
        context = bpy.context
        region = context.region
        space = context.space_data
        rv3d = getattr(space, "region_3d", None) if space else None
        if region is None or rv3d is None:
            return
        for world_co, text in self._texts:
            if not text:
                continue
            xy = location_3d_to_region_2d(region, rv3d, Vector(world_co))
            if xy is None:
                continue
            self._draw_label(xy.x, xy.y, text)

    def _draw_label(self, x, y, text):
        font_id = self.font_id
        try:
            blf.size(font_id, 13)
            width, height = blf.dimensions(font_id, text)
            shader = gpu.shader.from_builtin("UNIFORM_COLOR")
            gpu.state.blend_set("ALPHA")
            try:
                pad = 4.0
                fill = [
                    (x - pad, y - pad, 0.0),
                    (x + width + pad, y - pad, 0.0),
                    (x + width + pad, y + height + pad, 0.0),
                    (x - pad, y - pad, 0.0),
                    (x + width + pad, y + height + pad, 0.0),
                    (x - pad, y + height + pad, 0.0),
                ]
                batch = batch_for_shader(shader, "TRIS", {"pos": fill})
                shader.bind()
                shader.uniform_float("color", (1.0, 1.0, 1.0, 0.85))
                batch.draw(shader)
            finally:
                gpu.state.blend_set("NONE")
            blf.position(font_id, x, y, 0)
            blf.color(font_id, 0.1, 0.1, 0.1, 1.0)
            blf.draw(font_id, text)
        except Exception:
            pass


OVERLAY = _ViewportOverlay()


def attach():
    OVERLAY.attach()


def detach():
    OVERLAY.detach()
