"""Top-level dimensions, material parameters, and print clearances.

These are the constants the pot model draws from. Anything part-specific
that doesn't need to be shared lives next to the geometry it drives in
``pot.py``.

Coordinate frame: the pot stands on the XY plane (z = 0 = the print bed).
The floor occupies z ∈ [0, FLOOR_T]; the wall rises from z = 0 to z = POT_H.
The cavity (where soil goes) is the bore above the floor, open at the top.

The brief: a perforated PETG planter — a cylinder with a flat bottom, stiff
enough to be filled with wet soil and picked up, perforated to save material,
printed in (ideally clear) PETG and meant to drop inside a watertight outer
cachepot for bottom-watering. Started as Ø250 × 250 mm / 2 mm walls; the wall is
now 2 perimeters wide (1.6 mm at the 0.8 mm nozzle used for transparency), the
floor stays 2 mm, and POT_OD / POT_H are dialled to whatever pot is being built
(currently Ø115 × 140 mm — outer extents, wall included). The model is largely
size-parametric: change POT_OD / POT_H (and LINE_WIDTH for the nozzle) and
re-run; the perforation re-tiles, the bands/handles/cut windows recompute, and
the *structural support scales with size* — the handle finger count drops to fit
a small circumference, the vertical-rib count and the floor-rib waffle grow with
diameter (so a small pot isn't carrying a big pot's reinforcement). Very small
sizes (where even one finger or the solid bands won't fit) trip an assert rather
than build silently-wrong. A `config:` line at module load prints the chosen
finger / rib / floor-rib counts.

Two material facts shape every choice below:

1. Transparent PETG bridges and overhangs poorly — long horizontal spans
   sag and frost over. So every hole is a *pointy-top hexagon*: its roof is
   two edges meeting at a vertex, each 60° off vertical (30° off horizontal).
   That's not a *low*-angle overhang, but it's bounded and short — at the
   small hole sizes here the unsupported span is a couple of mm, which PETG
   bridges cleanly with no support — and it's far better than a round or
   stadium hole, whose crown goes flat-horizontal (a true bridge that sags).
   (A staggered hexagonal grid is also the most material-efficient perforation
   for a given web width — the ligament network triangulates load in every
   direction, with no weak horizontal plane the way a grid of round or square
   holes has.)
2. A perforated thin shell full of wet soil that gets carried around needs a
   continuous load path from rim to floor and a floor that won't creep. Hence:
   a solid top rim band with grab handles cut into it, a solid base band, a
   set of full-height solid ribs (one behind each handle, more on bigger pots),
   and a waffle of stiffening ribs on the inside of the floor.
"""

import math
import os

# ── Print line width (drives the "thin solid feature" sizes) ────────────────
# Set this to your slicer's extrusion width — ~0.42 mm for a 0.4 mm nozzle,
# ~0.8 mm for a 0.8 mm nozzle (the bigger nozzle is worth it here for
# transparency: fewer perimeters per wall ⇒ fewer bead-to-bead boundaries ⇒
# less internal light scatter). The wall, the ribs and the perforation web are
# sized as integer multiples of this so they print as clean full-width
# perimeters (no gap-fill, no stretched beads). Strength is not a factor — the
# loads here are tiny — so 2 perimeters everywhere is plenty.
LINE_WIDTH = 0.8

# ── Cross-section: round or regular N-gon ───────────────────────────────────
# NUM_FACES picks the cross-section: 0 (or 1/2) = round; an integer ≥ 3 = a
# regular polygon (square = 4, hexagon = 6, octagon = 8, …). A circle is just
# the N→∞ limit, so all the polygon machinery degrades to the round case and
# the round path is left exactly as it was. The polygon's *vertices* sit on the
# POT_OD circle (POT_OD = across-corners — see the OD note below), and it's
# oriented with a flat face centred toward 0° so a handle/rib lands on a flat
# face. Corners are rounded by CORNER_FILLET (nicer to hold, relieves the
# inside-corner stress riser, and keeps the perforation off the curved corner).
# Override at build time without editing: `POT_NUM_FACES=8 py -3.12 -m src.build`.
NUM_FACES = int(os.environ.get("POT_NUM_FACES", "0"))

# ── Rectangular cross-section (a 4-sided pot with unequal sides) ─────────────
# POT_RECT_TOP="LxW" (outer, mm: L along X, W along Y) switches to a rectangle;
# POT_RECT_BASE="LxW" gives the base (defaults to the top = straight walls), so
# the two axes may taper by different amounts (a trough-shaped planter box).
#   `POT_RECT_TOP=192x208 POT_RECT_BASE=177x188 POT_H=240 py -3.12 -m src.build --part inner`
# It rides on the polygon machinery as a 4-gon whose X faces (0°/180°) and Y
# faces (90°/270°) have their own apothems — see face_apo_out() below. The
# scalar "regular polygon" sizes (POT_OD, R_OUT, APO_*) then describe the
# INSCRIBED SQUARE (the short axis), which is what the sizing heuristics want.
def _parse_rect(v: str) -> tuple[float, float]:
    a, b = v.lower().replace("×", "x").split("x")
    return float(a), float(b)

IS_RECT = "POT_RECT_TOP" in os.environ
if IS_RECT:
    NUM_FACES = 4
    RECT_TOP  = _parse_rect(os.environ["POT_RECT_TOP"])
    RECT_BASE = _parse_rect(os.environ.get("POT_RECT_BASE", os.environ["POT_RECT_TOP"]))

# ── Overall pot ──────────────────────────────────────────────────────────────
# Outer size is given at the BASE and the TOP separately so the wall can taper
# (most pots are narrower at the bottom). The wall then grows at a single, even
# draft angle from base to top — a straight cone (round) or a straight-sided
# tapered prism (polygon). Set the two equal (the default) for a straight wall.
# POT_OD is the "outer extent": a diameter for a circle, the across-CORNERS
# diameter for a polygon. The TOP is the widest part (the opening), so it's what
# has to clear the cachepot.
#   Env overrides for quick variants:
#   `POT_NUM_FACES=8 POT_OD_TOP=140 POT_OD_BASE=120 py -3.12 -m src.build`
#   (POT_OD sets both at once; POT_OD_TOP / POT_OD_BASE override each end.)
_OD          = float(os.environ.get("POT_OD", "115.0"))
POT_OD_TOP   = float(os.environ.get("POT_OD_TOP", str(_OD)))   # opening (widest) — must clear the cachepot
POT_OD_BASE  = float(os.environ.get("POT_OD_BASE", str(_OD)))  # base (usually narrower)
if IS_RECT:
    # Across-corners size of the inscribed square at each end (short side · √2).
    POT_OD_TOP  = min(RECT_TOP)  * math.sqrt(2.0)
    POT_OD_BASE = min(RECT_BASE) * math.sqrt(2.0)
POT_OD       = POT_OD_TOP                                       # nominal outer extent = the top
del _OD

# Tiny-pot mode: under ~60 mm OD the load is trivial (a Ø40 × 100 pot of damp
# pumice is ~75 g) and the shell is naturally stiff against ovalising, so the
# whole reinforcement skeleton (handles, full-height ribs, floor waffle) is
# wasted material — drop it and keep just the perforated cup + rim cap. Override
# with POT_NO_RIBS=0/1 (default auto).
_LIGHT = bool(int(os.environ.get("POT_NO_RIBS", "1" if max(POT_OD_BASE, POT_OD_TOP) < 60.0 else "0")))
WALL_T   = 2 * LINE_WIDTH   # wall thickness = 2 perimeters, measured perpendicular
                            # to the wall. Set by printability + stiffness, not
                            # strength (the wall's loads are tiny).
POT_ID   = POT_OD - 2 * WALL_T          # bore (cavity) diameter at the top (round case)
POT_H    = float(os.environ.get("POT_H", "140.0"))   # overall height (= height of the outer wall; outer extent)
FLOOR_T  = float(os.environ.get("POT_FLOOR_T", "2.0"))   # flat-bottom thickness; floor is
                   # z ∈ [0, FLOOR_T]. 2 mm default (thicker than the wall — the floor carries
                   # the full load and a crack there dumps the pot); bump it on a big pot where
                   # the floor span bows (stiffness scales with thickness³, and it resists creep).

IS_POLY  = NUM_FACES >= 3      # round vs polygon switch (everything below branches on this)
COS_HALF = math.cos(math.pi / NUM_FACES) if IS_POLY else 1.0   # apothem / circumradius ratio (1 for a circle)

R_TOP    = POT_OD_TOP  / 2.0   # outer circumradius at the top  (z = POT_H)
R_BASE   = POT_OD_BASE / 2.0   # outer circumradius at the base (z = 0)
IS_TAPER = abs(R_TOP - R_BASE) > 1e-6 or (IS_RECT and RECT_TOP != RECT_BASE)

# Outer circumradius / apothem as functions of height (the even-draft taper).
# A circle is COS_HALF = 1, so apothem == circumradius.
def rc_out_at(z: float) -> float:   # outer circumradius at height z
    return R_BASE + (R_TOP - R_BASE) * (z / POT_H)
def apo_out_at(z: float) -> float:  # outer wall distance along a face normal
    return rc_out_at(z) * COS_HALF
def apo_in_at(z: float) -> float:   # inner wall distance along a face normal (uniform wall)
    return apo_out_at(z) - WALL_T
def rc_in_at(z: float) -> float:    # inner circumradius at height z
    return apo_in_at(z) / COS_HALF

# Reference (TOP, i.e. widest) radii — what the straight-wall code and the
# feature-sizing grids use. For a straight pot these equal the old constants, so
# the round straight path is unchanged.
R_OUT   = R_TOP                       # outer circumradius (vertices sit here at the top)
APO_OUT = apo_out_at(POT_H)           # outer apothem at the top
APO_IN  = apo_in_at(POT_H)            # inner apothem at the top
R_IN    = rc_in_at(POT_H)             # inner circumradius at the top
R_MID   = (R_OUT + R_IN) / 2.0        # mid-wall radius (used to size the hex grid)
APO_IN_BASE = apo_in_at(0.0)          # inner apothem at the base — the floor lives here
CORNER_FILLET = max(2.0, round(1.5 * WALL_T, 1)) if IS_POLY else 0.0   # rounded vertical corners (~2.4 mm)


def _ang_dist_deg(a: float, b: float) -> float:
    """Smallest absolute angle between two bearings, in degrees."""
    d = (a - b) % 360.0
    return min(d, 360.0 - d)


# Outward-normal bearing of each polygon face; face 0 points at 0°.
FACE_ANGLES = [i * 360.0 / NUM_FACES for i in range(NUM_FACES)] if IS_POLY else []


def rect_half(z: float) -> tuple[float, float]:
    """Outer half-extents (x, y) of a rectangular pot at height z."""
    f = z / POT_H
    return ((RECT_BASE[0] + (RECT_TOP[0] - RECT_BASE[0]) * f) / 2.0,
            (RECT_BASE[1] + (RECT_TOP[1] - RECT_BASE[1]) * f) / 2.0)


def _is_x_face(phi: float) -> bool:
    return _ang_dist_deg(phi, 0.0) < 45.0 or _ang_dist_deg(phi, 180.0) < 45.0


def face_apo_out(phi: float, z: float) -> float:
    """Outer-wall distance from the axis along the face normal at bearing
    ``phi``. Same for every face of a regular polygon; per-axis on a rectangle."""
    if not IS_RECT:
        return apo_out_at(z)
    hx, hy = rect_half(z)
    return hx if _is_x_face(phi) else hy


def face_apo_in(phi: float, z: float) -> float:
    return face_apo_out(phi, z) - WALL_T


def face_half_w(phi: float, z: float) -> float:
    """Half the outer width of the flat face at bearing ``phi`` (corner to corner)."""
    if not IS_RECT:
        return rc_out_at(z) * math.sin(math.pi / NUM_FACES)
    hx, hy = rect_half(z)
    return hy if _is_x_face(phi) else hx


def _snap_to_face(angle: float) -> float:
    """Nearest face-normal bearing to ``angle`` (identity for the round case)."""
    if not IS_POLY:
        return angle % 360.0
    return min(FACE_ANGLES, key=lambda f: _ang_dist_deg(angle, f))

# ── Solid bands (un-perforated reinforcement) ───────────────────────────────
# There is no separate "rim cap" band anymore — HANDLE_TOP_MARGIN (below)
# doubles as the top solid grip band; the finger holes sit right up against
# the pot's rim, so the solid material above them IS the ring you grip.
BASE_BAND_H = FLOOR_T + 2 * LINE_WIDTH   # solid wall ring at the base, z ∈ [0, BASE_BAND_H] (= floor + one ligament).
                     # Just the floor plus one ligament — the perforation runs
                     # almost to the floor for max drainage. (It used to be 18 mm
                     # to spread wall/floor bending stress, but that load is
                     # trivial — especially with the light pumice fill — and a
                     # few solid layers at the bed is plenty against warp.)

# Handle geometry — hoisted here so PERF_Z_HI can reference the handle bottom
# (below).  See the full HANDLE_ANGLES / HANDLE_FINGERS block further down.
HANDLE_FINGER_H   = 20.0        # finger-hole height (pointy-top vertex to vertex)
HANDLE_TOP_MARGIN =  8.0        # distance from finger-hole top to the pot top
                                # (the soil max-fill line sits at the finger-hole BOTTOM;
                                # perforation above that line is wasted — no soil to drain)

# Vertical band the perforation lives in — capped at the finger-hole bottom,
# which is the max soil-fill line. Above that the wall is empty air, so slits
# would drain nothing.
PERF_Z_LO    = BASE_BAND_H                                        # perforation starts just above the base band
PERF_Z_HI    = POT_H - HANDLE_TOP_MARGIN - HANDLE_FINGER_H        # ...ends at the finger-hole BOTTOM (= HANDLE_Z_LO)
HANDLE_FRAME = 10.0  # width of the solid frame kept around each handle (perforation keep-out)

# ── Vertical-slit wall perforation ──────────────────────────────────────────
# Drainage-focused wall perforation: staggered vertical slits instead of a hex
# honeycomb. Vertical slits preserve HOOP strength (a pot full of wet soil is
# loaded in hoop tension; horizontal slots would sever it, vertical ones leave
# each ring intact between slits, losing only SLIT_W / SLIT_COL_PITCH of
# cross-section). Rows are staggered by half a column so no continuous vertical
# weakness line runs down the wall. Much cheaper booleans than the hex field:
# a plain rectangular box (vs. the gabled hex cell), and ~3-5× fewer cutters
# for similar open area — the cone-intersect drops from tens of minutes to a
# few seconds. Roots grow through anything ≥ ~0.5 mm eventually, so the
# root-block property comes from slit *width*, not shape.
SLIT_W        = float(os.environ.get("POT_SLIT_W", "0.8"))     # tangential slit width (printable floor ≈ 1 × LINE_WIDTH — the slit is a single skipped-perimeter gap)
SLIT_H        = float(os.environ.get("POT_SLIT_H", "4.8"))     # slit height (6 × LINE_WIDTH)
SLIT_LIG      = float(os.environ.get("POT_SLIT_LIG", "4.8"))   # web between slits — same in both directions (6 × LINE_WIDTH); ~half the slit density of the tighter 2.4 setting
SLIT_COL_PITCH = SLIT_W + SLIT_LIG
SLIT_ROW_PITCH = SLIT_H + SLIT_LIG
SLIT_HALF_H    = SLIT_H / 2.0
SLIT_HALF_W    = SLIT_W / 2.0

# Top z of the topmost wall hole — mirrors the bottom-anchored row layout in
# _wall_slit_cutters(). Used to size the outer cachepot so its wall fully
# covers the perforation band (irrespective of where the rim cap sits).
_perf_usable = PERF_Z_HI - PERF_Z_LO - SLIT_H
_perf_n_rows = max(1, int(_perf_usable // SLIT_ROW_PITCH) + 1)
PERF_TOP_Z   = PERF_Z_LO + SLIT_H + (_perf_n_rows - 1) * SLIT_ROW_PITCH
del _perf_usable, _perf_n_rows

# ── Grab handles ─────────────────────────────────────────────────────────────
# Two handles, opposite each other — each a tangential row of pointy-top
# hexagonal finger holes (one per finger) rather than one big stadium opening:
# a stadium's rounded crown goes flat-horizontal at the top (a true bridge that
# sags in PETG), whereas a hex roof tops out at 60° off vertical — a real
# overhang at this size, so the roof underside prints a bit rough, but no
# support and no failure. Bonus: the solid pillars between the finger holes add
# cross-layer material right in the handle band, where the lift load runs in
# tension. (For a genuinely clean roof, reshape these as a gable — vertical
# sides + a 45° peak — for a ≤45° overhang at any size.)
#
# The count starts at the largest *even* value ≤ HANDLE_FINGERS_MAX, then drops
# by two on a small-diameter pot until a cluster (plus its solid frames) spans
# no more than HANDLE_MAX_ARC_DEG of the circumference — leaving room between the
# two handles for the ribs and some perforated wall. It stays even on purpose:
# a rib runs behind each handle along its centreline, and with an even count the
# centreline falls in the gap *between* the two innermost fingers, not through a
# finger hole (an odd count would block the middle hole). If even two fingers
# won't fit, the `HANDLE_W < 2*R_OUT` assert trips.
HANDLE_COUNT        = 0 if _LIGHT else 2
# Evenly spaced (0, 180, …); on a polygon each is snapped to the nearest flat
# face so a handle never straddles a corner. For even face counts the opposite
# handle lands on the opposite face exactly; for odd counts it lands on the
# nearest face (roughly, not exactly, opposite).
HANDLE_ANGLES       = [_snap_to_face(i * 360.0 / HANDLE_COUNT) for i in range(HANDLE_COUNT)] if HANDLE_COUNT else []
HANDLE_FINGERS_MAX  =  4
# HANDLE_FINGER_H is defined earlier (hoisted so PERF_Z_HI can reference it).
HANDLE_FINGER_AF    = HANDLE_FINGER_H * math.sqrt(3.0) / 2.0   # ≈ 17.3 — across-flats width (regular hex)
HANDLE_FINGER_GAP   =  6.0   # solid pillar between adjacent finger holes
HANDLE_MAX_ARC_DEG  = 100.0  # a handle cluster + its two frames may span at most this much of the wall

def _handle_chord(n: int) -> float:
    """Total tangential span (chord) of an n-finger cluster."""
    return n * HANDLE_FINGER_AF + (n - 1) * HANDLE_FINGER_GAP

def _handle_arc_deg(n: int) -> float:
    """Angular span of an n-finger cluster *plus* its solid frames, in degrees."""
    half = min(_handle_chord(n) / 2.0, R_OUT - 1e-9)              # guard the asin domain on tiny pots
    return 2.0 * math.degrees(math.asin(half / R_OUT)) + 2.0 * math.degrees(HANDLE_FRAME / R_OUT)

# On a polygon the cluster has to fit on one flat face (between the rounded
# corners), which is tighter than the circular-arc limit on a many-sided/small
# pot — so the count drops to whichever constraint bites first.
_FACE_FIT = (2.0 * R_OUT * math.sin(math.pi / NUM_FACES) - 2.0 * CORNER_FILLET) if IS_POLY else float("inf")

if HANDLE_COUNT == 0:
    HANDLE_FINGERS = 0
else:
    HANDLE_FINGERS = max(2, HANDLE_FINGERS_MAX - HANDLE_FINGERS_MAX % 2)   # largest even ≤ MAX (≥ 2)
    while HANDLE_FINGERS > 2 and (_handle_arc_deg(HANDLE_FINGERS) > HANDLE_MAX_ARC_DEG
                                  or _handle_chord(HANDLE_FINGERS) > _FACE_FIT):
        HANDLE_FINGERS -= 2
del _FACE_FIT

HANDLE_W      = _handle_chord(HANDLE_FINGERS) if HANDLE_FINGERS else 0.0   # total grip span (chord)
# Finger holes sit HANDLE_TOP_MARGIN mm below the pot's rim — the solid band
# above the holes is the grip hoop itself (no separate rim cap). Every mm of
# margin is a mm less soil depth.
HANDLE_Z_HI   = POT_H - HANDLE_TOP_MARGIN         # top vertex of the finger holes (HANDLE_TOP_MARGIN hoisted above)
HANDLE_Z_MID  = HANDLE_Z_HI - HANDLE_FINGER_H / 2.0
HANDLE_Z_LO   = HANDLE_Z_MID - HANDLE_FINGER_H / 2.0

# ── Full-height vertical ribs ───────────────────────────────────────────────
# Internal ribs running floor → rim, evenly spaced and always including the
# handle angles — so each handle has a rib behind it taking the lift load
# straight down from the grip. The smallest pot gets just HANDLE_COUNT of them
# (one per handle); a rib is added per handle each time the diameter passes a
# RIB_SCALE_OD threshold (the extra ones land in the open zones and brace a big,
# thin, floppy shell against ovalising / denting when empty). RIB_COUNT stays a
# multiple of HANDLE_COUNT so the even spacing lands on the handle angles.
# On a polygon the folded corners are themselves full-height stiffeners (a
# square/octagon resists ovalising far better than a tube), so we only need a
# rib behind each handle — the lift load path from the grip to the floor. On a
# round pot there are no corners, so ribs scale up with diameter to brace the
# shell.
RIB_SCALE_OD = (170.0, 400.0)   # round-pot diameters (mm) at which one more rib-per-handle is added
if _LIGHT or HANDLE_COUNT == 0:
    RIB_COUNT, RIB_ANGLES = 0, []               # tiny pot: no full-height ribs
elif IS_POLY:
    RIB_ANGLES = list(HANDLE_ANGLES)            # one rib behind each handle face
    RIB_COUNT  = len(RIB_ANGLES)
else:
    RIB_COUNT  = HANDLE_COUNT * (1 + sum(1 for _t in RIB_SCALE_OD if POT_OD >= _t))
    RIB_ANGLES = [i * 360.0 / RIB_COUNT for i in range(RIB_COUNT)]   # evenly spaced; includes the handle angles
RIB_W      = WALL_T                           # tangential width — same as the wall (a printable solid bead; loads are tiny)
RIB_PROJ   = max(4.0, min(8.0, R_IN * 0.06))  # inward projection from the wall; scales with size (≈4 mm small, ≈7 mm at Ø250)
RIB_Z_LO   = FLOOR_T          # sits on top of the floor
RIB_Z_HI   = POT_H            # runs all the way up into the rim cap

# ── Floor stiffening ribs (inside / soil side of the floor) ─────────────────
# A waffle of ribs on top of the 2 mm floor. Put on the *inside* on purpose:
# the floor then prints as one clean solid disc straight on the bed and the
# ribs grow up off it as thin walls — no bridging anywhere. (Ribs on the
# underside would force the floor to bridge the gaps between them.) Cost is a
# few mm of soil depth and some grams; payoff is a floor that won't bow under
# a full load of wet soil. Height scales with the floor radius — a small pot's
# floor barely needs ribs, so it gets short ones (~5 mm) and doesn't waste soil
# depth; a big pot gets ~10 mm. Thickness = WALL_T (a printable solid bead).
FLOOR_RIB_T        = WALL_T                             # rib thickness — same as the wall (loads are tiny)
# Rib height scales with the (base) floor size; override on a big pot that needs
# a stiffer waffle. (POT_FLOOR_RIB_H / POT_FLOOR_SPOKES / POT_FLOOR_RINGS env vars.)
FLOOR_RIB_H        = (float(os.environ["POT_FLOOR_RIB_H"]) if "POT_FLOOR_RIB_H" in os.environ
                      else max(5.0, min(12.0, APO_IN_BASE * 0.08)))
# Small-floor mode: a pot can be too big for tiny-pot mode (its TOP is over
# 60 mm, so it still wants handles and wall ribs) yet stand on a base only a
# few cm across — e.g. Ø45 → Ø85. A floor that small doesn't bow, and the
# waffle's keep-outs (plus the drain pipe's) would leave no room for a single
# drainage slit, so by default it gets no floor ribs. POT_FLOOR_SPOKES /
# POT_FLOOR_RINGS still force them.
SMALL_FLOOR_R = 30.0                              # base inner radius (mm) under which the floor waffle is dropped
_SMALL_FLOOR  = APO_IN_BASE < SMALL_FLOOR_R
if _LIGHT:
    FLOOR_SPOKE_COUNT = 0       # tiny pot: no floor waffle at all (the membrane doesn't bow at this size)
elif "POT_FLOOR_SPOKES" in os.environ:
    FLOOR_SPOKE_COUNT = int(os.environ["POT_FLOOR_SPOKES"])
elif _SMALL_FLOOR:
    FLOOR_SPOKE_COUNT = 0       # small floor: no waffle (see SMALL_FLOOR_R)
elif IS_POLY:
    # One spoke per face by default (each wall rib / corner gets a spoke). A
    # bigger pot wants more — set POT_FLOOR_SPOKES to a multiple of NUM_FACES so
    # they land on the faces AND the corners (e.g. 8 on a square = faces+corners).
    FLOOR_SPOKE_COUNT = NUM_FACES
else:
    _FLOOR_SPOKE_TARGET = max(4, round(POT_OD / 40.0))     # roughly one spoke per 40 mm of diameter
    FLOOR_SPOKE_COUNT  = RIB_COUNT * max(1, round(_FLOOR_SPOKE_TARGET / RIB_COUNT))   # ...rounded to a multiple of RIB_COUNT so every wall rib has a floor spoke continuing it inward (continuous lift-load path from grip → wall rib → floor spoke → centre)
    del _FLOOR_SPOKE_TARGET
FLOOR_SPOKE_ANGLES = [i * 360.0 / FLOOR_SPOKE_COUNT for i in range(FLOOR_SPOKE_COUNT)] if FLOOR_SPOKE_COUNT else []
# The floor sits at the (narrow) base, so its waffle is sized to the base inner
# apothem. Each spoke runs out to the inner *wall* along its own bearing — a
# face spoke reaches the apothem, a corner spoke reaches further (the corner is
# further from centre); _floor_ribs() computes that per spoke. Ring ribs stay
# inside the base inscribed circle so they never poke through a flat face.
FLOOR_SPOKE_R_OUT  = APO_IN_BASE
if _LIGHT:
    FLOOR_RING_COUNT = 0
else:
    FLOOR_RING_COUNT = (int(os.environ["POT_FLOOR_RINGS"]) if "POT_FLOOR_RINGS" in os.environ
                        else 0 if _SMALL_FLOOR
                        else max(1, round(APO_IN_BASE / 60.0)))   # concentric ring ribs; scales with the floor radius
FLOOR_RING_RADII   = [APO_IN_BASE * (i + 1) / (FLOOR_RING_COUNT + 1) for i in range(FLOOR_RING_COUNT)]   # evenly spread; inside the base inscribed circle
# Spokes run from the innermost ring rib out to the wall — *not* into the centre.
# The old central stubs didn't converge (nothing tied them together), so they
# braced little; dropping them lets the centre be perforated for drainage
# instead, with the ring as the innermost hoop. (The light pumice load barely
# deflects the centre membrane — see the strength notes.)
FLOOR_SPOKE_R_IN   = (min(FLOOR_RING_RADII) - FLOOR_RIB_T) if FLOOR_RING_RADII else 0.0   # start at (and bond to) the innermost ring
FLOOR_PERF_R_IN    = 0.0                                   # floor holes fill all the way to the centre

# The floor membrane *between* the ribs carries almost no load (the ribs do
# the work), so it's slit-perforated too — extra material saved, doubles as
# drainage. Floor slits are RADIAL rectangles (SLIT_H long along the radius,
# SLIT_W wide tangentially) arranged in concentric rings — radial orientation
# preserves the disc's hoop stiffness. Slits pass fine soil, so use a liner /
# landscape fabric if planting straight into the pot. The floor prints flat on
# the bed — no bridging — just a little less bed contact (use a brim).
FLOOR_PERF          = True
# Solid gap kept between a floor hole and any rib / the rim / the drain pipe.
# 5 mm on a normal floor; scaled down with the base (to half a ligament at the
# least) so a small floor isn't all keep-out — at Ø45 a fixed 5 mm left ZERO
# slits. Unchanged for a base inner radius of 50 mm and up. POT_FLOOR_FRAME overrides.
FLOOR_PERF_FRAME    = (float(os.environ["POT_FLOOR_FRAME"]) if "POT_FLOOR_FRAME" in os.environ
                       else max(SLIT_LIG / 2.0, min(5.0, APO_IN_BASE * 0.1)))

# ── Drainage (a few clean round holes) ──────────────────────────────────────
# Largely redundant once FLOOR_PERF is on (the hex floor already drains).
# Kept for the soil-retaining alternative: set FLOOR_PERF = False and
# DRAINAGE = True for a mostly-solid floor with a centre hole plus a ring of
# holes between the floor ribs.
DRAINAGE       = False
DRAIN_HOLE_D   = 8.0
DRAIN_RING_R   = R_IN * 0.53           # roughly mid-floor (DRAINAGE is off by default; nudge if it clashes with a ring rib)
DRAIN_RING_N   = 6

# ── Drain-hose channel ──────────────────────────────────────────────────────
# A vertical *pipe* (the "closure tube") running floor → rim at one angular
# position (auto-placed midway between two ribs — clear of handles and ribs),
# for threading a drain hose down between this inner pot and an outer cachepot
# (bottom-watering: soak in water, then drain). The pipe's bore cradles the
# hose; the pipe is embedded in / replaces the wall there and its outer face is
# recessed slightly inside the pot's OD, so the inter-pot gap can stay uniformly
# tiny everywhere else — no wasted reservoir water, no wasted soil (the pipe
# eats ~1–2 % of the cavity). The pipe wall is hex-perforated (same cell size as
# the rest of the wall, wrapping it 360°), all the way down to the floor, so
# water flows in/out of the soil right at the bottom of the column.
#
# Geometry: the pipe is a full 360° annular tube (bore radius R_CH, wall WALL_T)
# whose outer face sits OD_RECESS inside the nominal OD, so it *merges into* the
# existing wall (a band of the pipe's outer surface overlaps it — keeping it one
# connected solid, no wide void cut that would orphan it) and isn't tangent to
# the OD (a tangent line confuses STEP importers / OCCT normal propagation). The
# only cut is a small bore-through-the-floor (radius FLOOR_BORE_R, slightly >
# R_CH so it isn't coincident with the bore) so the hose can pass to the
# reservoir below. Wall/floor perforation gets a DRAIN_CHANNEL_KEEPOUT_DEG
# keep-out around the channel; the pipe wall carries the perforation there.
DRAIN_CHANNEL              = bool(int(os.environ.get("POT_DRAIN", "1")))   # disable with POT_DRAIN=0
DRAIN_CHANNEL_HOSE_D       = 12.0    # configurable for the hose you pick
DRAIN_CHANNEL_CLEARANCE    =  1.0    # radial clearance between hose and pipe bore
DRAIN_CHANNEL_R_CH         = DRAIN_CHANNEL_HOSE_D / 2.0 + DRAIN_CHANNEL_CLEARANCE   # pipe bore radius (cradles the hose)
DRAIN_CHANNEL_TUBE_OR      = DRAIN_CHANNEL_R_CH + WALL_T                            # pipe outer radius (about the groove axis)
DRAIN_CHANNEL_OD_RECESS    =  0.5    # the pipe's outer face sits this far inside the wall (so it merges into the wall, not tangent to it)
# The groove axis sits in from the wall by the pipe radius + recess, measured
# perpendicular to the wall. On a tapered pot the wall moves outward with height,
# so the pipe follows it — a straight oblique tube whose axis runs from R_AXIS_BASE
# at the floor to R_AXIS_TOP at the rim (keeping the same recess, and the merge
# into the wall, at every height). The floor bore sits at the base end.
# (Computed just below, once DRAIN_CHANNEL_ANGLE is known — on a rectangle the
# wall distance depends on which face the channel sits on.)
DRAIN_CHANNEL_FLOOR_BORE_R = DRAIN_CHANNEL_R_CH                                       # bore-through-floor = pipe bore (matched so no ledge inside the pipe base)
if not DRAIN_CHANNEL or RIB_COUNT == 0:
    DRAIN_CHANNEL_ANGLE    = 0.0                              # unused if no drain channel; safe default
elif IS_POLY:
    # Put the channel on the flat face farthest from every handle/rib.
    DRAIN_CHANNEL_ANGLE    = max(FACE_ANGLES, key=lambda f: min(_ang_dist_deg(f, a) for a in RIB_ANGLES))
else:
    DRAIN_CHANNEL_ANGLE    = 180.0 / RIB_COUNT               # midway between the first two ribs (always clear of handles and ribs)
DRAIN_CHANNEL_R_AXIS_TOP   = face_apo_out(DRAIN_CHANNEL_ANGLE, POT_H) - DRAIN_CHANNEL_TUBE_OR - DRAIN_CHANNEL_OD_RECESS
DRAIN_CHANNEL_R_AXIS_BASE  = face_apo_out(DRAIN_CHANNEL_ANGLE, 0.0)   - DRAIN_CHANNEL_TUBE_OR - DRAIN_CHANNEL_OD_RECESS
DRAIN_CHANNEL_R_AXIS       = DRAIN_CHANNEL_R_AXIS_TOP    # reference (top); the pipe slants between base & top
# Keep-out is widest where the axis is closest in (the base on a flared pot).
DRAIN_CHANNEL_KEEPOUT_DEG  = math.degrees(math.asin(min(0.95, (DRAIN_CHANNEL_TUBE_OR + 1.0) / DRAIN_CHANNEL_R_AXIS_BASE))) + 3.0
# The pipe wall is perforated only on its *inward* (soil-facing) side — a hole
# on the outward side would just connect the bore to the tiny inter-pot gap.
# This is the half-angle of the SOLID arc around the outward (toward-OD)
# direction; that arc is also where the pipe merges into the wall, so keeping it
# solid leaves a clean joint. (≥ the merge half-angle plus a margin.)
DRAIN_CHANNEL_PERF_SOLID_HALF_DEG = 45.0

# Floor spokes start at 0° — same as the first wall rib (RIB_ANGLES[0]) — and
# since FLOOR_SPOKE_COUNT is a multiple of RIB_COUNT, every wall rib gets a floor
# spoke continuing it straight inward. If a spoke happens to land on the drain
# channel angle, _floor_ribs() truncates that one short of the pipe bore so it
# doesn't block the hose (it still braces the floor toward that corner).
FLOOR_SPOKE_OFFSET = 0.0

# ── Boolean / cut helpers ───────────────────────────────────────────────────
BOOL_OVERSHOOT = 1.0    # extend cut/union solids past the target face for clean booleans
# Radial window a wall-hole cutter spans. A cutter is a flat slab, so on a
# curved wall it must reach from the *outer* wall at the hole's centre down to
# the *inner* wall at the hole's tangential edge. The widest hole is the handle
# finger row (half-chord = HANDLE_W/2), so size RADIAL_CUT_LO to the inner wall
# there (with margin); RADIAL_CUT_HI just clears the OD. (Never deep enough to
# touch the opposite wall — the cavity in between is air.) On a tapered wall the
# same slab serves every height as long as it spans the *base* inner wall (the
# narrowest) up past the *top* outer wall (the widest) — so a hole gets cut
# wherever the wall happens to be at that height.
if IS_TAPER:
    RADIAL_CUT_LO = rc_in_at(0.0) - 3.0          # reach the narrowest (base) inner wall
    RADIAL_CUT_HI = R_TOP + 3.0                  # clear the widest (top) outer wall
else:
    RADIAL_CUT_LO = math.sqrt(max(0.0, R_IN ** 2 - (HANDLE_W / 2.0) ** 2)) - 2.0
    RADIAL_CUT_HI = R_OUT + 3.0
RADIAL_CUT_DEPTH = RADIAL_CUT_HI - RADIAL_CUT_LO

# ── Sanity checks (fail fast on a bad edit / too-small a size) ───────────────
assert POT_ID > 0, "wall too thick for this diameter"
assert SLIT_LIG > 0, "slits would overlap"
assert PERF_Z_HI > PERF_Z_LO + SLIT_ROW_PITCH, "no room for a perforation band — pot too short"
assert PERF_Z_HI <= HANDLE_Z_LO + 1e-6, "perforation extends above the finger-hole bottom (soil max-fill line)"
assert HANDLE_COUNT >= 0
assert HANDLE_FINGER_GAP > 0, "finger holes would merge"
if HANDLE_COUNT > 0:
    assert HANDLE_FINGERS >= 2 and HANDLE_FINGERS % 2 == 0, "handle finger count must be even (the centreline rib must clear the holes)"
    assert HANDLE_Z_HI < POT_H, "handle would break through the pot rim"
    if IS_POLY:
        _flat_w = 2.0 * R_OUT * math.sin(math.pi / NUM_FACES)   # outer flat-face width
        assert HANDLE_W < _flat_w - 2.0 * CORNER_FILLET, "handle fingers are wider than a flat face — fewer/smaller fingers or more faces or bigger POT_OD"
        del _flat_w
    else:
        assert HANDLE_W < 2 * R_OUT, "even two handle fingers are wider than the pot — increase POT_OD"
    assert RIB_COUNT >= HANDLE_COUNT and RIB_COUNT % HANDLE_COUNT == 0, "RIB_COUNT must be a positive multiple of HANDLE_COUNT (a rib must sit behind each handle)"
assert POT_OD_BASE > 2.0 * WALL_T and APO_IN_BASE > 0, "base too small for the wall thickness — increase POT_OD_BASE"
assert FLOOR_SPOKE_R_IN < APO_IN_BASE, "floor centre clearance exceeds the (base) floor radius"
assert all(0.0 < r < APO_IN_BASE for r in FLOOR_RING_RADII), "a floor ring rib lies outside the (base) inscribed wall"
if not IS_POLY and not IS_TAPER:
    assert math.isclose(R_MID, (POT_OD - WALL_T) / 2.0)
if DRAIN_CHANNEL:
    assert all(_ang_dist_deg(DRAIN_CHANNEL_ANGLE, ha) > DRAIN_CHANNEL_KEEPOUT_DEG + 5.0 for ha in HANDLE_ANGLES), \
        "drain channel overlaps a handle keep-out — pick a different DRAIN_CHANNEL_ANGLE"
    assert all(_ang_dist_deg(DRAIN_CHANNEL_ANGLE, ra) > DRAIN_CHANNEL_KEEPOUT_DEG for ra in RIB_ANGLES), \
        "drain channel overlaps a vertical rib — pick a different DRAIN_CHANNEL_ANGLE"
    assert DRAIN_CHANNEL_R_AXIS_BASE > 0, "channel pipe sticks out past the base wall — hose too big for the base diameter"
    assert DRAIN_CHANNEL_R_AXIS_BASE - DRAIN_CHANNEL_R_CH > 0, "channel pipe bore reaches past the pot centre at the base — hose too big for the base diameter"
    assert DRAIN_CHANNEL_R_AXIS_TOP + DRAIN_CHANNEL_TUBE_OR > face_apo_in(DRAIN_CHANNEL_ANGLE, POT_H), "channel pipe wouldn't reach the wall to merge with it — geometry off"

# ── Config summary ──────────────────────────────────────────────────────────
_chan_str = (f" | drain channel @ {DRAIN_CHANNEL_ANGLE:.0f}deg for "
             f"hose {DRAIN_CHANNEL_HOSE_D:g} mm") if DRAIN_CHANNEL else ""
_shape_str = ("rectangular" if IS_RECT else
              f"{NUM_FACES}-gon (corner r {CORNER_FILLET:g})" if IS_POLY else "round")
if IS_RECT:
    _od_str = (f"{RECT_BASE[0]:g}x{RECT_BASE[1]:g} -> {RECT_TOP[0]:g}x{RECT_TOP[1]:g}" if IS_TAPER
               else f"{RECT_TOP[0]:g}x{RECT_TOP[1]:g}")
else:
    _od_str = (f"OD {POT_OD_BASE:.0f}->{POT_OD_TOP:.0f}" if IS_TAPER else f"OD {POT_OD:.0f}")
_handles_str = (f"{HANDLE_COUNT} handles x {HANDLE_FINGERS} fingers" if HANDLE_COUNT else "no handles")
_ribs_str    = (f"{RIB_COUNT} vertical ribs ({RIB_PROJ:.1f} mm deep)" if RIB_COUNT else "no vertical ribs")
_floor_str   = (f"floor: {FLOOR_SPOKE_COUNT} spokes + {FLOOR_RING_COUNT} ring(s), {FLOOR_RIB_H:.1f} mm tall"
                if (FLOOR_SPOKE_COUNT or FLOOR_RING_COUNT) else "no floor waffle")
print(f"config: {_shape_str} pot {_od_str} x H {POT_H:.0f} mm, wall {WALL_T:g} mm, floor {FLOOR_T:g} mm | "
      f"{_handles_str} | {_ribs_str} | {_floor_str}{_chan_str}")
del _chan_str, _shape_str, _od_str, _handles_str, _ribs_str, _floor_str
