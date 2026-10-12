"""The perforated plant pot.

Build order:
  1. solid shell      — outer cylinder bored to leave a thin wall + flat floor
  2. cut hex holes    — pointy-top honeycomb over the wall, skipping a solid
                        frame around each rib, each handle, and the drain channel
  3. cut grab handles — two handles, each a tangential row of pointy-top
                        hexagonal finger holes (one per finger) below the rim cap
  4. cut floor holes  — (optional) hex honeycomb through the floor membrane,
                        in the bays between the floor ribs
  5. add vertical ribs — full-height internal ribs (rim → floor)
  6. add floor ribs   — a waffle on the inside of the floor
  7. drain pipe       — (optional) a vertical 360° tube running floor → rim,
                        merged into the wall (its outer band overlaps it) and
                        recessed inside the OD; a small bore-through-the-floor
                        is cut so a hose threaded down the pipe's bore reaches
                        the outer cachepot's reservoir; the pipe wall is
                        hex-perforated on its inward (soil-facing) arc, down to
                        the floor
  8. (optional) drainage round-holes through the floor

Everything *removed* (wall hex + handles + floor hex) is collected and cut in
chunked batches; everything *added* (ribs) is unioned. Each hole cutter is a
flat radial slab thick enough in X to clear the curved wall over the full width
of the hole — see helpers.hex_prism. There are several thousand of these (the
perforation is fine), so a full build takes tens of minutes.
"""

import math
import os

import cadquery as cq

# Ask OCCT to run its boolean engine multi-threaded (off by default in cadquery).
# Geometry is unchanged — just spreads each cut across cores. Best-effort.
try:
    from OCP.BOPAlgo import BOPAlgo_Options
    BOPAlgo_Options.SetParallelMode_s(True)
except Exception:
    pass

from .dimensions import (
    POT_OD, POT_ID, POT_H, WALL_T, FLOOR_T,
    R_IN, R_OUT, R_MID,
    IS_POLY, NUM_FACES, FACE_ANGLES, APO_OUT, APO_IN, CORNER_FILLET,
    IS_TAPER, R_BASE, R_TOP, COS_HALF, APO_IN_BASE,
    rc_out_at, rc_in_at, apo_out_at, apo_in_at,
    IS_RECT, rect_half, face_apo_out, face_apo_in, face_half_w,
    SLIT_W, SLIT_H, SLIT_LIG, SLIT_COL_PITCH, SLIT_ROW_PITCH, SLIT_HALF_H, SLIT_HALF_W,
    PERF_Z_LO, PERF_Z_HI, PERF_TOP_Z,
    HANDLE_ANGLES, HANDLE_W, HANDLE_FINGERS, HANDLE_FINGER_H, HANDLE_FINGER_AF, HANDLE_FINGER_GAP,
    HANDLE_Z_LO, HANDLE_Z_HI, HANDLE_Z_MID, HANDLE_FRAME,
    RIB_ANGLES, RIB_W, RIB_PROJ, RIB_Z_LO, RIB_Z_HI,
    FLOOR_RIB_T, FLOOR_RIB_H, FLOOR_SPOKE_COUNT, FLOOR_SPOKE_R_IN, FLOOR_SPOKE_R_OUT,
    FLOOR_SPOKE_OFFSET, FLOOR_SPOKE_ANGLES, FLOOR_RING_RADII,
    FLOOR_PERF, FLOOR_PERF_FRAME, FLOOR_PERF_R_IN,
    DRAINAGE, DRAIN_HOLE_D, DRAIN_RING_R, DRAIN_RING_N,
    DRAIN_CHANNEL, DRAIN_CHANNEL_R_CH, DRAIN_CHANNEL_TUBE_OR, DRAIN_CHANNEL_FLOOR_BORE_R, DRAIN_CHANNEL_OD_RECESS,
    DRAIN_CHANNEL_R_AXIS, DRAIN_CHANNEL_R_AXIS_BASE, DRAIN_CHANNEL_R_AXIS_TOP,
    DRAIN_CHANNEL_ANGLE, DRAIN_CHANNEL_KEEPOUT_DEG,
    DRAIN_CHANNEL_PERF_SOLID_HALF_DEG,
    BOOL_OVERSHOOT, RADIAL_CUT_LO, RADIAL_CUT_HI,
)
from .helpers import cyl, tube, poly_prism, compound, gable_prism, slit_prism, step


# ── 1. Solid shell ───────────────────────────────────────────────────────────

def _poly_pts(circ_r: float):
    return [(circ_r * math.cos(math.pi / NUM_FACES + k * 2.0 * math.pi / NUM_FACES),
             circ_r * math.sin(math.pi / NUM_FACES + k * 2.0 * math.pi / NUM_FACES))
            for k in range(NUM_FACES)]


def _taper_section(base_r: float, top_r: float, z0: float, z1: float) -> cq.Workplane:
    """Straight-walled tapered solid from circumradius base_r at z0 to top_r at
    z1. Round → an analytic cone (cq.Solid.makeCone): this matters a lot, because
    a *lofted* circle-to-circle wall comes out as a BSpline surface and every one
    of the thousands of hex boolean cuts against it is enormously slower than
    against an analytic cone. Faceted → a ruled loft between the two polygons
    (planar faces, so cutting stays fast)."""
    if not IS_POLY:
        cone = cq.Solid.makeCone(base_r, top_r, z1 - z0,
                                 pnt=cq.Vector(0, 0, z0), dir=cq.Vector(0, 0, 1))
        return cq.Workplane("XY").newObject([cone])
    return (cq.Workplane("XY").workplane(offset=z0).polyline(_poly_pts(base_r)).close()
            .workplane(offset=z1 - z0).polyline(_poly_pts(top_r)).close()
            .loft(ruled=True))


def _rect_section(inset: float, z0: float, z1: float) -> cq.Workplane:
    """Rectangular (possibly tapered) solid from z0 to z1 whose faces sit
    ``inset`` inside the pot's outer wall at every height (negative = outside).
    A ruled loft between the two rectangles — planar faces, so it cuts fast."""
    def _pts(z):
        hx, hy = rect_half(z)
        hx, hy = hx - inset, hy - inset
        return [(hx, hy), (-hx, hy), (-hx, -hy), (hx, -hy)]
    return (cq.Workplane("XY").workplane(offset=z0).polyline(_pts(z0)).close()
            .workplane(offset=z1 - z0).polyline(_pts(z1)).close()
            .loft(ruled=True))


def _fillet_vertical_corners(wp: cq.Workplane, radius: float) -> cq.Workplane:
    """Fillet the (near-)vertical corner edges of a (possibly tapered) prism —
    selected as the edges whose endpoints span most of the height, so it works
    whether the corner edges are exactly vertical (straight wall) or slanted
    (tapered)."""
    if radius <= 0.0:
        return wp
    edges = [e for e in wp.val().Edges()
             if abs(e.endPoint().z - e.startPoint().z) > 0.5 * POT_H]
    return wp.newObject(edges).fillet(radius)


def _shell() -> cq.Workplane:
    """Outer wall solid, bored out above the floor — leaving a uniform wall and
    a flat bottom, open at the top. Round → cylinder/frustum; faceted → N-gon
    prism with filleted corners. The wall tapers at an even draft from the base
    OD to the top OD when those differ (IS_TAPER)."""
    bore_h = (POT_H - FLOOR_T) + BOOL_OVERSHOOT     # cavity from the floor top up through the rim
    inner_fillet = max(0.0, CORNER_FILLET - WALL_T)  # keep the wall ~uniform around the corner

    if IS_RECT:
        outer = _fillet_vertical_corners(_rect_section(0.0, 0.0, POT_H), CORNER_FILLET)
        bore  = _fillet_vertical_corners(
            _rect_section(WALL_T, FLOOR_T, POT_H + BOOL_OVERSHOOT), inner_fillet)
        return outer.cut(bore)

    if not IS_TAPER:
        # Straight wall — keep the original prism/cylinder construction.
        if not IS_POLY:
            return cyl(POT_OD, POT_H, z=0.0).cut(cyl(POT_ID, bore_h, z=FLOOR_T))
        outer = poly_prism(R_OUT, NUM_FACES, POT_H, z=0.0, fillet=CORNER_FILLET)
        bore  = poly_prism(R_IN, NUM_FACES, bore_h, z=FLOOR_T, fillet=inner_fillet)
        return outer.cut(bore)

    # Tapered wall — base→top at an even draft. The bore uses the same draft,
    # offset inward by the wall (so the perpendicular wall thickness stays
    # uniform with height).
    outer = _fillet_vertical_corners(_taper_section(R_BASE, R_TOP, 0.0, POT_H), CORNER_FILLET)
    bore  = _fillet_vertical_corners(
        _taper_section(rc_in_at(FLOOR_T), rc_in_at(POT_H + BOOL_OVERSHOOT), FLOOR_T, POT_H + BOOL_OVERSHOOT),
        inner_fillet)
    return outer.cut(bore)


# ── helpers ──────────────────────────────────────────────────────────────────

def _angular_dist_deg(a: float, b: float) -> float:
    """Smallest absolute angle between two bearings, in degrees."""
    d = (a - b) % 360.0
    return min(d, 360.0 - d)


def _cut_many(body: cq.Workplane, cutters: list[cq.Workplane], chunk: int = 0,
              label: str | None = None) -> cq.Workplane:
    """Cut a long list of tool solids out of ``body``. By default (chunk ≤ 0) it
    does this in ONE compound boolean against the clean body — which is ~13×
    faster than batching, because every batch re-cuts the *accumulating* holey
    solid (superlinear). One pass against the clean body has no accumulation, so
    cutting thousands of disjoint hex holes is fast and OCCT handles it fine.
    ``chunk`` > 0 forces batches (kept only as a fallback). clean=False: skip
    cadquery's per-cut ShapeUpgrade — the single final heal() (build.py) does it.
    """
    n = len(cutters)
    if chunk <= 0 or chunk >= n:
        if label:
            print(f"    {label}: cutting {n} holes in one pass...", flush=True)
        return body.cut(compound(cutters), clean=False)
    n_chunks = (n + chunk - 1) // chunk
    for ci, i in enumerate(range(0, n, chunk), start=1):
        body = body.cut(compound(cutters[i:i + chunk]), clean=False)
        if label:
            print(f"    {label}: chunk {ci}/{n_chunks}  ({min(i + chunk, n)}/{n} holes)", flush=True)
    return body


# ── 2. Wall vertical-slit perforation ───────────────────────────────────────

def _wall_slit_cutters() -> list[cq.Workplane]:
    """Staggered vertical slits over the perforation band. Each slit is a
    plain radial box (SLIT_W wide tangentially, SLIT_H tall), rows offset by
    half a column so no continuous vertical weakness line runs down the wall.
    Same keep-out rules as the hex path (ribs, handles, drain channel)."""
    if IS_POLY:
        return _wall_slit_cutters_poly()
    col_pitch = SLIT_COL_PITCH
    row_pitch = SLIT_ROW_PITCH

    span    = PERF_Z_HI - PERF_Z_LO
    usable  = span - 2.0 * SLIT_HALF_H
    n_rows  = max(1, int(usable // row_pitch) + 1)
    z_first = PERF_Z_LO + SLIT_HALF_H

    rib_keepout_deg    = math.degrees((RIB_W / 2.0 + SLIT_LIG + SLIT_HALF_W) / R_IN)
    handle_keepout_deg = math.degrees((HANDLE_W / 2.0 + HANDLE_FRAME) / R_OUT)
    handle_z_lo        = HANDLE_Z_LO - HANDLE_FRAME
    handle_z_hi        = HANDLE_Z_HI + HANDLE_FRAME
    chan_keepout_deg   = DRAIN_CHANNEL_KEEPOUT_DEG if DRAIN_CHANNEL else -1.0

    base = slit_prism(SLIT_W, SLIT_H, RADIAL_CUT_LO, RADIAL_CUT_HI)
    cutters: list[cq.Workplane] = []
    for ri in range(n_rows):
        z_c   = z_first + ri * row_pitch
        z_top, z_bot = z_c + SLIT_HALF_H, z_c - SLIT_HALF_H
        in_handle_band = (z_top > handle_z_lo) and (z_bot < handle_z_hi)
        # Size THIS row's n_cols by its own local circumference (the mid-wall
        # radius at this height) — so the tangential gap between slits meets
        # SLIT_LIG at every height, not just the base. A tapered pot gets
        # more slits per row as we rise, packed at the same ~SLIT_LIG spacing.
        r_ref_row  = rc_out_at(z_c) - WALL_T / 2.0
        n_cols     = max(6, round((2.0 * math.pi * r_ref_row) / col_pitch))
        d_theta    = 360.0 / n_cols
        shift = (d_theta / 2.0) if (ri % 2) else 0.0
        for ci in range(n_cols):
            theta = (ci * d_theta + shift) % 360.0
            if any(_angular_dist_deg(theta, ra) < rib_keepout_deg for ra in RIB_ANGLES):
                continue
            if in_handle_band and any(_angular_dist_deg(theta, ha) < handle_keepout_deg
                                      for ha in HANDLE_ANGLES):
                continue
            if DRAIN_CHANNEL and _angular_dist_deg(theta, DRAIN_CHANNEL_ANGLE) < chan_keepout_deg:
                continue
            cutters.append(base.translate((0.0, 0.0, z_c)).rotate((0, 0, 0), (0, 0, 1), theta))
    return cutters


def _wall_slit_cutters_poly() -> list[cq.Workplane]:
    """Polygon wall slit perforation: same staggered layout, but each flat
    face gets its own centred grid — clipped per-row to the local face width
    at that height (so slits stay off the rounded corners)."""
    col_pitch = SLIT_COL_PITCH
    row_pitch = SLIT_ROW_PITCH

    span    = PERF_Z_HI - PERF_Z_LO
    usable  = span - 2.0 * SLIT_HALF_H
    n_rows  = max(1, int(usable // row_pitch) + 1)
    z_first = PERF_Z_LO + SLIT_HALF_H

    corner_margin = CORNER_FILLET + SLIT_LIG + SLIT_HALF_W
    def t_max_at(phi, z):
        return face_half_w(phi, z) - corner_margin

    rib_keep    = RIB_W / 2.0 + SLIT_LIG + SLIT_HALF_W
    handle_keep = HANDLE_W / 2.0 + HANDLE_FRAME
    chan_keep   = DRAIN_CHANNEL_TUBE_OR + SLIT_LIG + SLIT_HALF_W
    handle_z_lo = HANDLE_Z_LO - HANDLE_FRAME
    handle_z_hi = HANDLE_Z_HI + HANDLE_FRAME

    cutters: list[cq.Workplane] = []
    for phi in FACE_ANGLES:
        # Per face: on a rectangle each face has its own width and wall distance.
        n_cols = max(0, int(max(t_max_at(phi, 0.0), t_max_at(phi, POT_H)) / col_pitch) + 1)
        base = slit_prism(SLIT_W, SLIT_H,
                          min(face_apo_in(phi, 0.0), face_apo_in(phi, POT_H)) - BOOL_OVERSHOOT,
                          max(face_apo_out(phi, 0.0), face_apo_out(phi, POT_H)) + BOOL_OVERSHOOT)
        has_handle = any(_angular_dist_deg(phi, ha) < 1.0 for ha in HANDLE_ANGLES)
        has_rib    = any(_angular_dist_deg(phi, ra) < 1.0 for ra in RIB_ANGLES)
        has_chan   = DRAIN_CHANNEL and _angular_dist_deg(phi, DRAIN_CHANNEL_ANGLE) < 1.0
        for ri in range(n_rows):
            z_c = z_first + ri * row_pitch
            in_handle_band = (z_c + SLIT_HALF_H > handle_z_lo) and (z_c - SLIT_HALF_H < handle_z_hi)
            shift = (col_pitch / 2.0) if (ri % 2) else 0.0
            row_t_max = t_max_at(phi, z_c)
            for ci in range(-n_cols, n_cols + 1):
                t = ci * col_pitch + shift
                if abs(t) > row_t_max:
                    continue
                if has_rib and abs(t) < rib_keep:
                    continue
                if has_chan and abs(t) < chan_keep:
                    continue
                if has_handle and in_handle_band and abs(t) < handle_keep:
                    continue
                cutters.append(base.translate((0.0, t, z_c)).rotate((0, 0, 0), (0, 0, 1), phi))
    return cutters


# ── 3. Grab handles ──────────────────────────────────────────────────────────

def _handle_cutters() -> list[cq.Workplane]:
    """Each handle = a tangential row of HANDLE_FINGERS gabled finger holes
    (across-flats HANDLE_FINGER_AF wide, HANDLE_FINGER_H tall, top and bottom
    capped by 45° peaks so the top overhang prints self-supporting). Built
    like the wall slit cutters (a radial slab per hole), offset tangentially,
    then orbited to each handle angle. The gable cap gives ~46° overhang on
    the flared wall (the 10° outward taper adds ~1° over the cutter's 45°) —
    within printable range in PETG. A regular hex would put the top vertex at
    60° from vertical, which the flare pushes past what PETG bridges cleanly."""
    # side_h = HANDLE_FINGER_H - HANDLE_FINGER_AF so total vertex-to-vertex
    # height stays HANDLE_FINGER_H (each 45° cap adds HANDLE_FINGER_AF/2).
    side_h  = max(0.1, HANDLE_FINGER_H - HANDLE_FINGER_AF)
    pitch   = HANDLE_FINGER_AF + HANDLE_FINGER_GAP
    n       = HANDLE_FINGERS
    offsets = [(i - (n - 1) / 2.0) * pitch for i in range(n)]      # centred tangential offsets
    # Round wall: a deep radial slab (so edge holes clear the curve). Flat face:
    # punch straight through the panel (no curvature to clear).
    def _finger(a):
        if IS_POLY:
            return gable_prism(HANDLE_FINGER_AF, side_h,
                               min(face_apo_in(a, 0.0), face_apo_in(a, POT_H)) - BOOL_OVERSHOOT,
                               max(face_apo_out(a, 0.0), face_apo_out(a, POT_H)) + BOOL_OVERSHOOT)
        return gable_prism(HANDLE_FINGER_AF, side_h, RADIAL_CUT_LO, RADIAL_CUT_HI)
    cutters: list[cq.Workplane] = []
    for a in HANDLE_ANGLES:
        finger = _finger(a)
        for off in offsets:
            cutters.append(finger.translate((0.0, off, HANDLE_Z_MID)).rotate((0, 0, 0), (0, 0, 1), a))
    return cutters


# ── 4. Floor perforation (optional) ─────────────────────────────────────────

def _floor_slit_cutters() -> list[cq.Workplane]:
    """Concentric rings of RADIALLY-oriented rectangular slits (SLIT_W wide
    tangentially, SLIT_H long radially, through the floor). Slits point
    outward at each angular position, so a ring's material stays continuous
    tangentially between slits — the disc's hoop stiffness (which resists
    centre-sag under a full load of wet soil) is preserved. Each ring's slit
    count is sized to its own local circumference so the tangential gap stays
    ≈ SLIT_LIG at every radius. Rings are stagger-rotated so no radial seam
    runs from centre to rim."""
    z_lo, z_hi = -BOOL_OVERSHOOT, FLOOR_T + BOOL_OVERSHOOT
    col_pitch  = SLIT_COL_PITCH
    row_pitch  = SLIT_ROW_PITCH
    clear      = FLOOR_PERF_FRAME + SLIT_HALF_H     # radial keep-out from ring rib / rim

    rc_in_base = APO_IN_BASE / COS_HALF
    r_outer_lim = (APO_IN_BASE if IS_POLY else rc_in_base) - clear
    if IS_RECT:
        # Rings run out into the long axis / corners; the per-face clip below
        # trims each one to the rectangle.
        r_outer_lim = math.hypot(*rect_half(0.0)) - WALL_T - clear
    # A slit centred at r spans [r - SLIT_HALF_H, r + SLIT_HALF_H] radially.
    # Keep the inner end past the centre by at least half a ligament, so
    # opposite-side slits don't overlap through the origin (OCCT boolean cost
    # explodes when many cutters overlap at a point).
    r_inner_lim = max(FLOOR_PERF_R_IN + SLIT_HALF_H, SLIT_HALF_H + SLIT_LIG / 2.0)

    n_rings = max(0, int((r_outer_lim - r_inner_lim) // row_pitch) + 1)

    spoke_step = 360.0 / FLOOR_SPOKE_COUNT if FLOOR_SPOKE_COUNT else 360.0
    face_normals = [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in FACE_ANGLES]
    apo_clips = [face_apo_in(a, 0.0) - clear for a in FACE_ANGLES]

    chan_x = chan_y = 0.0
    chan_clear = -1.0
    if DRAIN_CHANNEL:
        ang_ch = math.radians(DRAIN_CHANNEL_ANGLE)
        chan_x = DRAIN_CHANNEL_R_AXIS_BASE * math.cos(ang_ch)
        chan_y = DRAIN_CHANNEL_R_AXIS_BASE * math.sin(ang_ch)
        chan_clear = DRAIN_CHANNEL_TUBE_OR + clear

    # Base slit — rectangular prism through the floor, centred at origin, long
    # axis along +X (so after translate(r,0,0) it points radially outward from
    # the pot centre). rotate() around Z spins it to any bearing.
    base = (cq.Workplane("XY").workplane(offset=z_lo)
            .rect(SLIT_H, SLIT_W).extrude(z_hi - z_lo))

    cutters: list[cq.Workplane] = []
    for ri in range(n_rings):
        r = r_inner_lim + ri * row_pitch
        if r > r_outer_lim:
            break
        # Whole ring vanishes if it sits on top of a ring rib.
        if any(abs(r - rr) < clear for rr in FLOOR_RING_RADII):
            continue
        n_slits = max(4, round((2.0 * math.pi * r) / col_pitch))
        d_ang   = 360.0 / n_slits
        shift   = (d_ang / 2.0) if (ri % 2) else 0.0
        for ci in range(n_slits):
            ang = (ci * d_ang + shift) % 360.0
            cx  = r * math.cos(math.radians(ang))
            cy  = r * math.sin(math.radians(ang))
            if IS_POLY and any(cx * nx + cy * ny > lim
                               for (nx, ny), lim in zip(face_normals, apo_clips)):
                continue
            if FLOOR_SPOKE_COUNT and r > FLOOR_SPOKE_R_IN:
                m = (ang - FLOOR_SPOKE_OFFSET) % spoke_step
                d_spoke = min(m, spoke_step - m)
                if r * math.sin(math.radians(d_spoke)) < clear:
                    continue
            if chan_clear > 0 and math.hypot(cx - chan_x, cy - chan_y) < chan_clear:
                continue
            cutters.append(base.translate((r, 0.0, 0.0))
                               .rotate((0, 0, 0), (0, 0, 1), ang))
    return cutters


# ── 5. Full-height vertical ribs ────────────────────────────────────────────

def _vertical_ribs() -> list[cq.Workplane]:
    """Internal ribs running floor → rim. Each is a radial blade from
    (inner wall − RIB_PROJ) out into the wall, inset slightly from the OD so the
    union doesn't bulge the outside. On a tapered pot the inner wall slopes, so
    the blade is a tapered trapezoid that tracks it (otherwise it would either
    poke out at the base or fall short of the wall at the top). Two ribs sit
    behind the handle openings — that's the lift load path."""
    zlo, zhi = RIB_Z_LO, RIB_Z_HI
    if IS_RECT:
        # Each rib tracks ITS face (the X and Y faces sit at different distances
        # and may taper differently).
        blades = []
        for a in RIB_ANGLES:
            pts = [
                (face_apo_in(a, zlo) - RIB_PROJ, zlo),
                (face_apo_out(a, zlo) - 0.5,     zlo),
                (face_apo_out(a, zhi) - 0.5,     zhi),
                (face_apo_in(a, zhi) - RIB_PROJ, zhi),
            ]
            blade = cq.Workplane("XZ").polyline(pts).close().extrude(RIB_W / 2.0, both=True)
            blades.append(blade.rotate((0, 0, 0), (0, 0, 1), a))
        return blades
    if not IS_TAPER:
        r_lo  = (APO_IN if IS_POLY else R_IN) - RIB_PROJ
        r_hi  = (APO_OUT if IS_POLY else R_OUT) - 0.5     # inset from the wall so the union doesn't bulge it
        blade = (
            cq.Workplane("XY").workplane(offset=zlo)
            .center((r_lo + r_hi) / 2.0, 0.0)
            .box(r_hi - r_lo, RIB_W, zhi - zlo, centered=(True, True, False))
        )
    else:
        # Trapezoid in the X(radial)–Z(height) plane, given thickness RIB_W in Y.
        pts = [
            (apo_in_at(zlo) - RIB_PROJ, zlo),
            (apo_out_at(zlo) - 0.5,     zlo),
            (apo_out_at(zhi) - 0.5,     zhi),
            (apo_in_at(zhi) - RIB_PROJ, zhi),
        ]
        blade = cq.Workplane("XZ").polyline(pts).close().extrude(RIB_W / 2.0, both=True)
    return [blade.rotate((0, 0, 0), (0, 0, 1), a) for a in RIB_ANGLES]


# ── 6. Floor stiffening ribs (soil side) ────────────────────────────────────

def _floor_ribs() -> cq.Workplane:
    """A waffle on top of the 2 mm floor: FLOOR_SPOKE_COUNT radial blades plus
    the concentric ring blades in FLOOR_RING_RADII. Sits inside the pot so the
    floor itself still prints as one clean disc on the bed."""
    parts: list[cq.Workplane] = []

    r_in = FLOOR_SPOKE_R_IN                                 # innermost ring out to the wall
    z_top = FLOOR_T + FLOOR_RIB_H                            # top of the floor ribs

    def _inner_wall_r(ang_deg: float, z: float) -> float:
        """Inner-wall distance from centre along this bearing, at height z. For a
        polygon a corner spoke must reach further than a face spoke (the corner
        is further out): apothem / cos(angle off the nearest face normal). On a
        tapered pot the wall also moves out with z."""
        if not IS_POLY:
            return rc_in_at(z)
        if IS_RECT:
            hx, hy = rect_half(z)
            c, s_ = abs(math.cos(math.radians(ang_deg))), abs(math.sin(math.radians(ang_deg)))
            return min((hx - WALL_T) / c if c > 1e-9 else math.inf,
                       (hy - WALL_T) / s_ if s_ > 1e-9 else math.inf)
        d = min(_angular_dist_deg(ang_deg, f) for f in FACE_ANGLES)
        return apo_in_at(z) / math.cos(math.radians(d))

    # A spoke that lands on the drain channel would run into the pipe's floor
    # bore; that one stops just short of the bore instead (still a brace, no
    # obstruction to the hose). The bore is at the *base* axis (it's cut through
    # the floor), so truncate to that — not the top axis, which on a tapered pot
    # sits further out and would let the spoke reach into the hole.
    r_out_chan = (max(r_in + FLOOR_RIB_T, DRAIN_CHANNEL_R_AXIS_BASE - DRAIN_CHANNEL_FLOOR_BORE_R)
                  if DRAIN_CHANNEL else None)
    for ang in FLOOR_SPOKE_ANGLES:
        is_chan = DRAIN_CHANNEL and _angular_dist_deg(ang, DRAIN_CHANNEL_ANGLE) < 1.0
        if is_chan:
            # Truncated stub short of the bore — never reaches the wall, so a
            # plain vertical box is fine.
            spoke = (
                cq.Workplane("XY").workplane(offset=FLOOR_T)
                .center((r_in + r_out_chan) / 2.0, 0.0)
                .box(r_out_chan - r_in, FLOOR_RIB_T, FLOOR_RIB_H, centered=(True, True, False))
            )
        elif IS_TAPER:
            # The wall slopes outward over the rib's height, so the spoke's outer
            # edge must slope to stay embedded in it (a vertical box gaps off the
            # wall above the floor). Reach ~half a wall into it at each height.
            ro_b = _inner_wall_r(ang, FLOOR_T) + WALL_T / 2.0
            ro_t = _inner_wall_r(ang, z_top)  + WALL_T / 2.0
            pts = [(r_in, FLOOR_T), (ro_b, FLOOR_T), (ro_t, z_top), (r_in, z_top)]
            spoke = cq.Workplane("XZ").polyline(pts).close().extrude(FLOOR_RIB_T / 2.0, both=True)
        else:
            ro = _inner_wall_r(ang, FLOOR_T)
            spoke = (
                cq.Workplane("XY").workplane(offset=FLOOR_T)
                .center((r_in + ro) / 2.0, 0.0)
                .box(ro - r_in, FLOOR_RIB_T, FLOOR_RIB_H, centered=(True, True, False))
            )
        parts.append(spoke.rotate((0, 0, 0), (0, 0, 1), ang))

    for rr in FLOOR_RING_RADII:
        parts.append(tube(2.0 * rr + FLOOR_RIB_T, 2.0 * rr - FLOOR_RIB_T, FLOOR_RIB_H, z=FLOOR_T))

    return compound(parts)


# ── 7. Optional drainage round-holes ────────────────────────────────────────

def _drain_cutters() -> list[cq.Workplane]:
    """A centre hole plus a ring of round holes through the floor, placed in
    the gaps between the floor ribs."""
    z0 = -BOOL_OVERSHOOT
    h  = FLOOR_T + 2.0 * BOOL_OVERSHOOT
    cutters = [cyl(DRAIN_HOLE_D, h, z=z0)]                  # centre
    half_gap = FLOOR_SPOKE_OFFSET + 360.0 / FLOOR_SPOKE_COUNT / 2.0   # midway between adjacent spokes
    for i in range(DRAIN_RING_N):
        theta = math.radians(half_gap + i * 360.0 / DRAIN_RING_N)
        cutters.append(
            cyl(DRAIN_HOLE_D, h, z=z0).translate(
                (DRAIN_RING_R * math.cos(theta), DRAIN_RING_R * math.sin(theta), 0.0)
            )
        )
    return cutters


# ── 7. Drain-hose channel / pipe (optional) ─────────────────────────────────

def _pipe_envelope() -> cq.Workplane | None:
    """Solid the drain pipe is clipped to on a ROUND pot: the pot's outer surface
    pulled in by half a wall. The pipe's gap-filling box is flat on its outward
    side, so on a small pot its two outer corners poke out through the curved
    wall; clipped to this, everything the pipe adds ends inside the wall's
    thickness (so it still merges into the wall, and shares no surface with it).
    None on a polygon — the wall is flat there and the box sits flush."""
    if IS_POLY:
        return None
    inset = WALL_T / 2.0
    if IS_TAPER:
        cone = cq.Solid.makeCone(R_BASE - inset, R_TOP - inset, POT_H,
                                 pnt=cq.Vector(0, 0, 0), dir=cq.Vector(0, 0, 1))
        return cq.Workplane("XY").newObject([cone])
    return cyl(POT_OD - 2.0 * inset, POT_H, z=0.0)


def _drain_channel_floor_bore_and_pipe() -> tuple[cq.Workplane, cq.Workplane, cq.Workplane]:
    """Returns (floor_bore, pipe, bore) for the drain channel:
      bore       — the pipe's whole hose channel (radius R_CH, floor → rim,
                   following the pipe's slant) as a cutter: the caller cuts it
                   AFTER the floor ribs are on, so a ring rib or spoke that
                   crosses the pipe doesn't stand inside the channel.
      floor_bore — a short vertical cylinder of radius DRAIN_CHANNEL_FLOOR_BORE_R
                   at the groove axis, z ∈ [-overshoot, FLOOR_T + overshoot]:
                   the hole through the floor so the hose can reach the
                   reservoir below.
      pipe       — a full 360° annular tube (radii [R_CH, TUBE_OR]) at the
                   groove axis, z ∈ [0, POT_H]; its bore is the hose channel,
                   and a band of its outer surface overlaps the existing wall
                   (so the whole thing stays one connected solid).
    The caller does ``body.cut(floor_bore).union(pipe)`` (cut first, so the
    pipe's inner band cleanly refills the floor hole's outer ring) and then
    perforates the pipe wall."""
    r_ch     = DRAIN_CHANNEL_R_CH
    tube_or  = DRAIN_CHANNEL_TUBE_OR
    bore_r   = DRAIN_CHANNEL_FLOOR_BORE_R
    a        = DRAIN_CHANNEL_ANGLE
    R_base   = DRAIN_CHANNEL_R_AXIS_BASE   # axis distance from centre at the floor
    R_top    = DRAIN_CHANNEL_R_AXIS_TOP    # ...and at the rim

    # The floor bore sits at the base end of the (possibly slanted) pipe axis.
    floor_bore = (cyl(2.0 * bore_r, FLOOR_T + 2.0 * BOOL_OVERSHOOT, z=-BOOL_OVERSHOOT)
                  .translate((R_base, 0.0, 0.0))
                  .rotate((0, 0, 0), (0, 0, 1), a))

    # Rectangular fill from the drain axis (midpoint of the pipe) out to the
    # outer wall face, tangential width = pipe bore ID (2·R_CH). Fills the
    # tight corners where the round pipe meets the flat/curved wall so the
    # slicer doesn't see razor-thin geometry. The bore is cut LAST to restore
    # the hose channel that the fill would otherwise block — the "hose channel
    # remains a full-height cylinder of radius R_CH" invariant is preserved.
    fill_x_in  = 0.0                                     # drain axis (pipe midpoint)
    fill_x_out = tube_or + DRAIN_CHANNEL_OD_RECESS       # coplanar with the outer wall face

    if not IS_TAPER:
        # Straight wall — plain tube + plain box fill, minus the bore.
        pipe_tube = tube(2.0 * tube_or, 2.0 * r_ch, POT_H, z=0.0)
        fill = (cq.Workplane("XY")
                .center((fill_x_in + fill_x_out) / 2.0, 0.0)
                .rect(fill_x_out - fill_x_in, 2.0 * r_ch)
                .extrude(POT_H))
        bore = cyl(2.0 * r_ch, POT_H + 2.0 * BOOL_OVERSHOOT, z=-BOOL_OVERSHOOT)
        place = lambda wp: wp.translate((R_base, 0.0, 0.0)).rotate((0, 0, 0), (0, 0, 1), a)
        pipe = place(pipe_tube.union(fill, clean=False).cut(bore, clean=False))
        env = _pipe_envelope()
        if env is not None:
            pipe = pipe.intersect(env, clean=False)
        return floor_bore, pipe, place(bore)

    # Tapered wall — oblique tube + oblique fill + oblique bore cut, all
    # following the slanted axis from R_base at the floor to R_top at the rim.
    def axis_x(z):
        return R_base + (R_top - R_base) * (z / POT_H)
    def oblique_cyl(radius, z0, z1):
        x0, x1 = axis_x(z0), axis_x(z1)
        return (cq.Workplane("XY").workplane(offset=z0).center(x0, 0.0).circle(radius)
                .workplane(offset=z1 - z0).center(x1 - x0, 0.0).circle(radius)
                .loft(ruled=True))
    def oblique_fill(z0, z1):
        x0, x1 = axis_x(z0), axis_x(z1)
        def _rect(cx):
            return [(cx + fill_x_in, -r_ch), (cx + fill_x_out, -r_ch),
                    (cx + fill_x_out,  r_ch), (cx + fill_x_in,  r_ch)]
        return (cq.Workplane("XY").workplane(offset=z0).polyline(_rect(x0)).close()
                .workplane(offset=z1 - z0).polyline(_rect(x1)).close()
                .loft(ruled=True))
    bore = oblique_cyl(r_ch, -BOOL_OVERSHOOT, POT_H + BOOL_OVERSHOOT)
    pipe = (oblique_cyl(tube_or, 0.0, POT_H)
            .union(oblique_fill(0.0, POT_H), clean=False)
            .cut(bore, clean=False))
    pipe = pipe.rotate((0, 0, 0), (0, 0, 1), a)
    env = _pipe_envelope()
    if env is not None:
        pipe = pipe.intersect(env, clean=False)
    return floor_bore, pipe, bore.rotate((0, 0, 0), (0, 0, 1), a)


def _channel_pipe_slit_cutters() -> list[cq.Workplane]:
    """Vertical-slit perforation for the drain-channel pipe wall — same
    SLIT_W / SLIT_H / SLIT_LIG geometry as the main wall, but oriented
    *radially from the groove axis* (the pipe is a thin cylindrical wall
    around that axis, not around the pot centre, so the main-wall cutters
    can't perforate it cleanly).

    Only the *inward-facing* arc of the pipe is perforated (a hole on the
    outward side would just open the bore to the inter-pot gap, not the soil;
    the outward arc is also where the pipe merges into the wall, so leaving it
    solid keeps that joint clean). The vertical range goes down to the floor
    (z = FLOOR_T) — water needs a path in/out at the bottom of the soil column
    — and up to POT_H (above the soil line, just cosmetic)."""
    if not DRAIN_CHANNEL:
        return []

    r_ch    = DRAIN_CHANNEL_R_CH
    tube_or = DRAIN_CHANNEL_TUBE_OR
    R_base  = DRAIN_CHANNEL_R_AXIS_BASE
    R_top   = DRAIN_CHANNEL_R_AXIS_TOP
    def axis_x(z):                                          # groove-axis distance from centre at height z
        return R_base + (R_top - R_base) * (z / POT_H)
    r_mid   = (r_ch + tube_or) / 2.0                         # pipe mid-wall radius (about the groove axis)

    half_h     = SLIT_HALF_H
    solid_half = DRAIN_CHANNEL_PERF_SOLID_HALF_DEG           # outward arc that stays solid (centred on phi_local = 0)

    # Just TWO slits at the very bottom of the pipe — that's where water
    # pools at the base of the soil column and drains through the floor bore.
    # Everything above stays solid: the pipe is a rigid stiffener, and any
    # slits higher up would just leak soil into an inter-pot gap that nothing
    # can reach. Set z so the slit's BOTTOM edge sits at FLOOR_T (flush with
    # the floor bore, no gap).
    n_rows      = 1
    n_cols_pipe = 2
    z_first     = FLOOR_T + half_h
    row_pitch   = 0.0
    # Two slits, symmetric across the inward direction (phi_local = 180°),
    # centred in the perforable arc so they're each a quarter of the way in
    # from either end of the arc.
    perforable_arc = 360.0 - 2.0 * solid_half
    d_phi = perforable_arc / n_cols_pipe
    phi_first = solid_half + d_phi / 2.0    # first slit centre (measured from outward = 0°)

    # If a floor spoke butts into the pipe (it lands on DRAIN_CHANNEL_ANGLE and
    # _floor_ribs() truncated it to do so), keep the patch of pipe wall where it
    # attaches solid — the spoke arrives on the inward side (phi_local ≈ 180°),
    # right at the floor — so drop the slits there. (The user wants the spoke
    # flush against solid material, not running into a hole.)
    if FLOOR_SPOKE_COUNT:
        _spoke_step = 360.0 / FLOOR_SPOKE_COUNT
        spoke_on_channel = any(_angular_dist_deg(i * _spoke_step, DRAIN_CHANNEL_ANGLE) < 1.0
                               for i in range(FLOOR_SPOKE_COUNT))
    else:
        spoke_on_channel = False        # no spokes (light mode) → nothing butts into the pipe
    z_clear   = FLOOR_T + FLOOR_RIB_H + half_h          # rows whose slits could reach the spoke

    # Radial range of the cutter (from the groove axis): from just inside the
    # pipe bore to just outside the pipe OD, so the flat cutter punches through
    # the whole wall thickness.
    radial_lo = r_ch - 1.0
    radial_hi = tube_or + 1.0
    base = slit_prism(SLIT_W, SLIT_H, radial_lo, radial_hi)

    # phi_local is measured from the +x (outward, toward-OD) direction in the
    # pipe's pre-rotation frame; the inward (soil) side is around phi_local = 180°.
    cutters: list[cq.Workplane] = []
    for ri in range(n_rows):
        z_c = z_first + ri * row_pitch
        for ci in range(n_cols_pipe):
            phi_local = phi_first + ci * d_phi
            # Leave solid where the floor spoke butts into the pipe (inward side,
            # near the floor). Fixed 15° tolerance — enough for the spoke's
            # physical width, independent of d_phi (which is huge when there
            # are only a couple of slits per row).
            if spoke_on_channel and z_c < z_clear and _angular_dist_deg(phi_local, 180.0) < 15.0:
                continue
            cutters.append(
                base
                .translate((0.0, 0.0, z_c))
                .rotate((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), phi_local)   # orient radial from the groove axis
                .translate((axis_x(z_c), 0.0, 0.0))                     # to the (slanted) groove axis at this height
                .rotate((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), DRAIN_CHANNEL_ANGLE)
            )
    return cutters


# ── Parallel cone-intersect (opt-in via POT_PARALLEL_INTERSECT=N) ───────────

def _parallel_cone_intersect(add_wp: cq.Workplane, proxy_wp: cq.Workplane,
                             n_slices: int) -> cq.Workplane:
    """Split proxy + additive into ``n_slices`` horizontal bands, intersect
    each band in a separate subprocess, then fuse the results back into one
    solid. OCCT's boolean engine only lightly parallelizes internally, so
    splitting the domain across processes typically wins big on a many-core
    box (near-linear speedup up to ~cpu_count // 2, then Amdahl kicks in).

    Slice cuts and the final fuse both use OCCT itself — so the wall/floor
    slit imprints that straddle a slice boundary get cleanly re-joined. z
    bands are evenly spaced; if the fuse ever leaves visible hairlines at a
    boundary, snapping the boundaries into slit-row ligament gaps would fix
    it, but the fuse handles the coincident faces cleanly in practice."""
    import multiprocessing
    import shutil
    import tempfile
    import time as _time
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from OCP.BRep import BRep_Builder
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Fuse
    from OCP.BRepTools import BRepTools
    from OCP.TopoDS import TopoDS_Shape
    from OCP.TopTools import TopTools_ListOfShape

    from ._intersect_worker import intersect_worker

    add_s   = add_wp.val().wrapped
    proxy_s = proxy_wp.val().wrapped

    # Slice cutter: a big box spanning the whole XY extent, from z0 to z1.
    # Reach: 4 × outer OD each way is plenty of margin for any pot in this
    # workspace. BOOL_OVERSHOOT on the outermost z faces ensures the top and
    # bottom slice fully cover their respective end-caps.
    reach = 4.0 * max(2.0 * R_TOP, 2.0 * R_BASE)

    def _slice(shape: TopoDS_Shape, z0: float, z1: float) -> TopoDS_Shape:
        box = (cq.Workplane("XY").workplane(offset=z0)
               .rect(reach, reach)
               .extrude(z1 - z0)).val().wrapped
        algo = BRepAlgoAPI_Common(shape, box)
        algo.Build()
        return algo.Shape()

    z_lo, z_hi = -BOOL_OVERSHOOT, POT_H + BOOL_OVERSHOOT
    z_edges = [z_lo + i * (z_hi - z_lo) / n_slices for i in range(n_slices + 1)]

    tmp = tempfile.mkdtemp(prefix="pot_parallel_")
    try:
        specs: list[tuple[str, str, str]] = []
        for i in range(n_slices):
            p_path = f"{tmp}/proxy_{i}.brep"
            a_path = f"{tmp}/add_{i}.brep"
            o_path = f"{tmp}/out_{i}.brep"
            BRepTools.Write_s(_slice(proxy_s, z_edges[i], z_edges[i + 1]), p_path)
            BRepTools.Write_s(_slice(add_s,   z_edges[i], z_edges[i + 1]), a_path)
            specs.append((p_path, a_path, o_path))
        print(f"    dispatched {n_slices} slice-intersects to subprocesses...", flush=True)
        _t_dispatch = _time.time()

        # Windows uses 'spawn'; each worker re-executes `python -m src.build`
        # to find the pickled callable, which re-imports build.py → pot.py
        # → triggers a full rebuild in every worker. Setting POT_NOBUILD=1
        # in the environment for the spawn makes workers skip the module-
        # level build AND the module-level heal/main in build.py; the parent
        # already built `pot` earlier, so it's unaffected. We restore the
        # var in the parent afterwards so build.py's later main() (which
        # runs AFTER pot.py finishes importing) still exports the STEPs.
        # Hard wall-clock deadline for the parallel intersect. If any single
        # subprocess exceeds SLICE_TIMEOUT (or the whole pool exceeds
        # TOTAL_TIMEOUT), cancel and raise — turns a silent multi-hour hang
        # into an actionable error. Values are generous vs. observed times
        # (~10-60s per slice, ~15-60s total) so they only fire on real hangs.
        SLICE_TIMEOUT  = 300.0   # per-slice
        TOTAL_TIMEOUT  = 600.0   # whole pool
        _prev_nobuild = os.environ.get("POT_NOBUILD")
        os.environ["POT_NOBUILD"] = "1"
        try:
            ctx = multiprocessing.get_context("spawn")
            with ProcessPoolExecutor(max_workers=n_slices, mp_context=ctx) as pool:
                futures = {pool.submit(intersect_worker, p, a, o): idx
                           for idx, (p, a, o) in enumerate(specs)}
                n_done = 0
                try:
                    for fut in as_completed(futures, timeout=TOTAL_TIMEOUT):
                        idx = futures[fut]
                        remain = TOTAL_TIMEOUT - (_time.time() - _t_dispatch)
                        fut.result(timeout=max(1.0, min(SLICE_TIMEOUT, remain)))  # re-raise on worker exception / TimeoutError on hang
                        n_done += 1
                        dt = _time.time() - _t_dispatch
                        print(f"    slice {idx + 1}/{n_slices} done  ({n_done}/{n_slices} complete at {dt:.1f}s)", flush=True)
                except Exception as exc:
                    # Timeout or worker crash — cancel and abort cleanly.
                    for fut in futures:
                        fut.cancel()
                    pool.shutdown(wait=False, cancel_futures=True)
                    raise RuntimeError(f"parallel cone-intersect failed after {_time.time() - _t_dispatch:.1f}s "
                                       f"({n_done}/{n_slices} slices complete): {exc}") from exc
        finally:
            if _prev_nobuild is None:
                os.environ.pop("POT_NOBUILD", None)
            else:
                os.environ["POT_NOBUILD"] = _prev_nobuild
        print(f"    all slices done in {_time.time() - _t_dispatch:.1f}s; fusing...", flush=True)

        # Read all N slice results, fuse in one compound-fuse pass.
        b = BRep_Builder()
        results: list[TopoDS_Shape] = []
        for _, _, o_path in specs:
            s = TopoDS_Shape()
            BRepTools.Read_s(s, o_path, b)
            results.append(s)

        args  = TopTools_ListOfShape()
        tools = TopTools_ListOfShape()
        args.Append(results[0])
        for r in results[1:]:
            tools.Append(r)
        fuse = BRepAlgoAPI_Fuse()
        fuse.SetArguments(args)
        fuse.SetTools(tools)
        fuse.Build()
        fused = fuse.Shape()

        # Wrap back into a cadquery Workplane. compound → Compound, else Solid.
        from OCP.TopAbs import TopAbs_COMPOUND
        wrapped = cq.Compound(fused) if fused.ShapeType() == TopAbs_COMPOUND else cq.Solid(fused)
        return cq.Workplane("XY").newObject([wrapped])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── Assembly ─────────────────────────────────────────────────────────────────

def _build_pot() -> cq.Workplane:
    _step = step

    # A tapered ROUND wall is an analytic cone. Cutting the perforation straight
    # into it — and unioning ribs onto the result — is pathologically slow: not
    # because cone booleans are slow, but because each hex hole leaves messy
    # conic edge curves and the solid's complexity snowballs over the thousands
    # of sequential operations. So for the cone we split the work:
    #   • perforate a plain solid *cylinder* (clean cylinder-plane edges, fast);
    #   • assemble everything additive (cone shell + drain pipe + ribs) on the
    #     *simple* cone, with no holes yet;
    #   • carve the perforation into the whole assembly with ONE intersection.
    # The cone sits entirely inside the cylinder, ribs/pipe live in the
    # perforation keep-outs, so the intersection keeps them intact.
    # (A faceted taper has planar faces — clean edges — so it cuts in place fine,
    # like the straight polygon, and takes the normal path below.)
    if IS_TAPER and not IS_POLY:
        return _build_cone_pot(_step)

    body = _step("shell", _shell)
    body = _step("wall-perf", lambda: _cut_many(body, _wall_slit_cutters(), label="wall-slits"))
    if HANDLE_ANGLES:
        body = _step("handles", lambda: body.cut(compound(_handle_cutters()), clean=False))
    if FLOOR_PERF:
        body = _step("floor-perf", lambda: _cut_many(body, _floor_slit_cutters(), label="floor-slits"))

    if RIB_ANGLES:
        body = _step("vert-ribs", lambda: body.union(compound(_vertical_ribs()), clean=False))
    if FLOOR_SPOKE_ANGLES or FLOOR_RING_RADII:
        body = _step("floor-ribs", lambda: body.union(_floor_ribs(), clean=False))

    if DRAIN_CHANNEL:
        # Ribs are already unioned above, so cutting the bore here clears the
        # floor and any rib crossing it; the pipe then merges on top.
        # The hose channel (`bore`) is cut LAST and runs through the floor too,
        # so it also makes the hole to the reservoir and clears any floor rib
        # standing in the pipe. (The separate vertical floor bore is NOT cut as
        # well: it is the same radius at the same spot, and two near-coincident
        # cylinders leave OCCT an invalid sliver.)
        _floor_bore, pipe, bore = _drain_channel_floor_bore_and_pipe()
        body = _step("drain-merge", lambda: body.union(pipe, clean=False).cut(bore, clean=False))
        body = _step("pipe-perf", lambda: _cut_many(body, _channel_pipe_slit_cutters(), label="pipe-perf"))

    if DRAINAGE:
        body = body.cut(compound(_drain_cutters()))
    return body


def _build_cone_pot(_step) -> cq.Workplane:
    """Tapered-round assembly: perforate a cylinder proxy, build the additive
    parts on the plain cone, then carve with one intersection (see _build_pot)."""
    # 1. Perforate a solid cylinder proxy (fast — clean edges).
    proxy = cyl(2.0 * (R_TOP + 1.0), POT_H, z=0.0)
    proxy = _step("proxy wall-perf", lambda: _cut_many(proxy, _wall_slit_cutters(), label="wall-slits"))
    if HANDLE_ANGLES:
        proxy = _step("proxy handles", lambda: proxy.cut(compound(_handle_cutters()), clean=False))
    if FLOOR_PERF:
        proxy = _step("proxy floor-perf", lambda: _cut_many(proxy, _floor_slit_cutters(), label="floor-slits"))

    # 2. Assemble the additive parts on the plain cone shell (no holes → fast).
    #    Pipe stays SOLID here — perforating it before the cone-intersect
    #    creates tiny face fragments that make OCCT's intersection pathological
    #    (60+ minutes and no progress). We cut the pipe slits AFTER the
    #    intersect instead, as a cheap separate cut.
    add = _shell()
    if DRAIN_CHANNEL:
        _floor_bore, pipe, pipe_bore = _drain_channel_floor_bore_and_pipe()
        add = add.union(pipe, clean=False)
    def _add_ribs(a):
        if RIB_ANGLES:
            a = a.union(compound(_vertical_ribs()), clean=False)
        if FLOOR_SPOKE_ANGLES or FLOOR_RING_RADII:
            a = a.union(_floor_ribs(), clean=False)
        if DRAIN_CHANNEL:
            # Open the hose channel through the floor and any floor rib that
            # crosses the pipe. Done here, on the un-perforated solid, where it
            # is cheap; it replaces the old separate floor-bore cut (same radius
            # at the same spot — cutting both left an invalid sliver).
            a = a.cut(pipe_bore, clean=False)
        return a
    add = _step("additive (cone+pipe+ribs)", lambda: _add_ribs(add))

    # 3. One intersection carves the wall + floor perforation into the whole assembly.
    #    Opt-in: POT_PARALLEL_INTERSECT=N slices the domain into N horizontal
    #    bands and intersects each in its own subprocess (OCCT booleans only
    #    lightly parallelize internally — ~2 cores' worth — so splitting the
    #    domain scales much better on a many-core box). N=1 or unset = serial.
    _parallel_n = int(os.environ.get("POT_PARALLEL_INTERSECT", "0"))
    if _parallel_n >= 2:
        body = _step(f"cone-intersect ×{_parallel_n} slices",
                     lambda: _parallel_cone_intersect(add, proxy, _parallel_n))
    else:
        body = _step("cone-intersect", lambda: add.intersect(proxy, clean=False))

    # 4. Perforate the pipe wall (deferred from step 2 — see above).
    if DRAIN_CHANNEL:
        body = _step("pipe-perf", lambda: _cut_many(body, _channel_pipe_slit_cutters(), label="pipe-slits"))

    if DRAINAGE:
        body = body.cut(compound(_drain_cutters()))
    return body


def _build_outer_pot() -> cq.Workplane:
    """Plain solid cachepot the inner pot drops into — no holes, ribs, handles
    or drain pipe. Per-side offset from the inner's outer surface is WALL_T (the
    outer's wall thickness) + 3 mm (clearance gap). Total OD increase is
    therefore 2·WALL_T + 6 mm. Height is set to cover the perforation band: the
    cavity reaches from the outer's interior floor up to PERF_TOP_Z + 5 mm
    safety margin, so the inner rests on the outer's floor and its highest holes
    are still ~5 mm below the outer's rim."""
    OUTER_PERF_COVER = 5.0                                  # safety margin above top of highest hole
    OUTER_FLOOR_GAP  = 3.0                                  # clearance between inner-pot floor and outer-pot cavity floor (matches side-wall clearance)
    # The outer is drawn shifted DOWN by (FLOOR_T + OUTER_FLOOR_GAP) in the
    # assembly so the two pots don't share a floor plane; bump the outer's
    # height by the same amount so the top of the perforation band is still
    # covered by OUTER_PERF_COVER after the shift.
    h_out  = PERF_TOP_Z + OUTER_PERF_COVER + FLOOR_T + FLOOR_T + OUTER_FLOOR_GAP
    OFFSET = WALL_T + 3.0                                   # per-side offset from inner pot outer
    bore_h = h_out - FLOOR_T + BOOL_OVERSHOOT
    inner_fillet = max(0.0, CORNER_FILLET - WALL_T)

    # Outer pot's outer circumradius: inner's R at that height + OFFSET.
    R_out_base = R_BASE + OFFSET
    R_out_top  = (R_BASE + (R_TOP - R_BASE) * h_out / POT_H) + OFFSET
    R_in_base  = R_out_base - WALL_T                        # cavity (bore) circumradius
    R_in_top   = R_out_top  - WALL_T

    if IS_RECT:
        (bx, by), (tx, ty) = rect_half(0.0), rect_half(h_out)
        print(f"  [outer pot] base {2*(bx+OFFSET):.1f} x {2*(by+OFFSET):.1f} mm, "
              f"top {2*(tx+OFFSET):.1f} x {2*(ty+OFFSET):.1f} mm, height {h_out:.1f} mm", flush=True)
        outer = _fillet_vertical_corners(_rect_section(-OFFSET, 0.0, h_out), CORNER_FILLET)
        bore  = _fillet_vertical_corners(
            _rect_section(-(OFFSET - WALL_T), FLOOR_T, h_out + BOOL_OVERSHOOT), inner_fillet)
        return outer.cut(bore, clean=False)

    print(f"  [outer pot] OD base {2*R_out_base:.1f} mm, OD top {2*R_out_top:.1f} mm, height {h_out:.1f} mm", flush=True)

    if not IS_TAPER:
        if not IS_POLY:
            outer = cyl(2 * R_out_base, h_out, z=0.0)
            bore  = cyl(2 * R_in_base, bore_h, z=FLOOR_T)
        else:
            outer = poly_prism(R_out_base, NUM_FACES, h_out, z=0.0, fillet=CORNER_FILLET)
            bore  = poly_prism(R_in_base, NUM_FACES, bore_h, z=FLOOR_T, fillet=inner_fillet)
        return outer.cut(bore, clean=False)

    # Tapered — both walls follow the inner pot's draft, offset by OFFSET (outer)
    # and OFFSET − WALL_T (inner bore).
    outer = _fillet_vertical_corners(_taper_section(R_out_base, R_out_top, 0.0, h_out), CORNER_FILLET)
    slope = (R_in_top - R_in_base) / h_out                  # bore radius vs z
    bore = _fillet_vertical_corners(
        _taper_section(R_in_base + slope * FLOOR_T,
                       R_in_base + slope * (h_out + BOOL_OVERSHOOT),
                       FLOOR_T, h_out + BOOL_OVERSHOOT),
        inner_fillet)
    return outer.cut(bore, clean=False)


# Skip the (slow) build when only the helper functions are wanted (timing / tests).
# POT_PART=inner|outer|both picks what gets built (src.build sets it from
# --part); a pot that isn't built is left as None. Default: the inner pot only.
_PART = os.environ.get("POT_PART", "inner")
assert _PART in ("both", "inner", "outer"), f"POT_PART must be both/inner/outer, got {_PART!r}"
if os.environ.get("POT_NOBUILD") == "1":
    pot = None
    outer_pot = None
else:
    pot       = _build_pot() if _PART in ("both", "inner") else None
    outer_pot = _build_outer_pot() if _PART in ("both", "outer") else None
