"""Transform/sweep math checks against the INSTALLED modules
(runs inside Blender: these modules use mathutils)."""

import math

from mathutils import Vector

FAILURES = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print("[%s] transform math %s %s" % (status, name, detail))
    if not condition:
        FAILURES.append(name)


def run(module):
    FAILURES.clear()
    transform_mod = module.core.transform
    sweep_mod = module.core.sweep

    # -- 2D polygon offset ----------------------------------------------
    square = [(0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (0.0, 1.0)]
    # Positive distance offsets LEFT of each directed segment =
    # interior for this CCW square; negative = outward.
    outward = transform_mod.offset_polygon_2d(square, -0.5, closed=True)
    check(
        "offset square outward",
        outward is not None
        and abs(outward[0][0] - (-0.5)) < 1e-9
        and abs(outward[0][1] - (-0.5)) < 1e-9,
        str(outward),
    )
    inward = transform_mod.offset_polygon_2d(square, 0.25, closed=True)
    check(
        "offset square inward",
        inward is not None
        and abs(inward[0][0] - 0.25) < 1e-9
        and abs(inward[0][1] - 0.25) < 1e-9,
        str(inward),
    )
    chain = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]
    chain_off = transform_mod.offset_polygon_2d(chain, 0.1, closed=False)
    check(
        "offset open chain",
        chain_off is not None
        and len(chain_off) == 3
        and abs(chain_off[0][1] - 0.1) < 1e-9,
        str(chain_off),
    )
    check(
        "signed area ccw positive",
        transform_mod.polygon_signed_area_2d(square) > 0,
    )

    # -- matrices ---------------------------------------------------------
    rot = transform_mod.rotation_matrix((1, 0, 0), (0, 0, 1), 90.0)
    moved = rot @ Vector((2, 0, 0))
    check("rotation 90 about center", (moved - Vector((1, 1, 0))).length < 1e-6, str(moved))
    scl = transform_mod.scale_matrix((0, 0, 0), (2.0, 3.0, 1.0))
    check("scale factors", (scl @ Vector((1, 1, 1))) == Vector((2, 3, 1)))
    mir = transform_mod.mirror_matrix((1, 0, 0), (1, 0, 0))
    check("mirror across x=1", (mir @ Vector((2, 0, 0))) == Vector((0, 0, 0)))

    # -- ray/line -----------------------------------------------------------
    dist = transform_mod.ray_line_distance(
        (0, 0, 5), (0, 0.3, -1), (0, 0, 0), (0, 0, 1)
    )
    check("ray line distance finite", dist is not None, str(dist))
    parallel = transform_mod.ray_line_distance(
        (0, 0, 5), (0, 0, -1), (0, 0, 0), (0, 0, 1)
    )
    check("ray line parallel none", parallel is None, str(parallel))

    # -- path ordering ------------------------------------------------------
    edges = [
        (Vector((1, 0, 0)), Vector((2, 0, 0))),
        (Vector((0, 0, 0)), Vector((1, 0, 0))),
        (Vector((2, 0, 0)), Vector((2, 1, 0))),
    ]
    ordered = sweep_mod.order_path(edges)
    check(
        "order open chain",
        ordered is not None
        and not ordered[1]
        and len(ordered[0]) == 4
        and ordered[0][0] == Vector((0, 0, 0)),
        str(ordered),
    )
    loop = [
        (Vector((0, 0, 0)), Vector((1, 0, 0))),
        (Vector((1, 0, 0)), Vector((1, 1, 0))),
        (Vector((1, 1, 0)), Vector((0, 1, 0))),
        (Vector((0, 1, 0)), Vector((0, 0, 0))),
    ]
    ordered_loop = sweep_mod.order_path(loop)
    check(
        "order closed loop",
        ordered_loop is not None and ordered_loop[1] and len(ordered_loop[0]) == 4,
        str(ordered_loop),
    )
    branched = loop + [(Vector((1, 0, 0)), Vector((1, -1, 0)))]
    check("order branched none", sweep_mod.order_path(branched) is None)

    # -- sweep ----------------------------------------------------------------
    profile = [
        Vector((0, 0, 0)),
        Vector((0.2, 0, 0)),
        Vector((0.2, 0.2, 0)),
        Vector((0, 0.2, 0)),
    ]
    path = [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((2, 0, 0))]
    swept = sweep_mod.sweep_profile(profile, Vector((0, 0, 1)), path, False)
    check("sweep straight rings", swept is not None and len(swept[0]) == 3, str(swept and len(swept[0])))
    if swept is not None:
        rings, quads = swept
        check("sweep ring size", all(len(r) == 4 for r in rings))
        check("sweep quad count", len(quads) == 8, str(len(quads)))
        check(
            "sweep end ring centered on path end",
            (sum(rings[-1], Vector()) / len(rings[-1]) - Vector((2, 0, 0))).length < 1e-6,
            str(rings[-1]),
        )
    circle_path = [
        Vector((math.cos(a), math.sin(a), 0.0))
        for a in [i * math.pi / 4 for i in range(8)]
    ]
    swept_closed = sweep_mod.sweep_profile(
        profile, Vector((0, 0, 1)), circle_path, True
    )
    check(
        "sweep closed rings",
        swept_closed is not None and len(swept_closed[0]) == 8,
        str(swept_closed and len(swept_closed[0])),
    )
    if swept_closed is not None:
        check("sweep closed quads", len(swept_closed[1]) == 32, str(len(swept_closed[1])))

    print("transform math: %s" % ("ALL PASS" if not FAILURES else "FAILURES %s" % FAILURES))
    return 1 if FAILURES else 0
