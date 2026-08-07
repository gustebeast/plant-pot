"""Geometric helper functions used by pot.py / build.py.

Pure functions — no module-level state. Dimensions are passed in or pulled
from src.dimensions.
"""

from __future__ import annotations

import math
import cadquery as cq

from .dimensions import BOOL_OVERSHOOT


def cyl(d: float, h: float, z: float = 0.0) -> cq.Workplane:
    """Solid cylinder: diameter d, height h, base face at z."""
    return cq.Workplane("XY").workplane(offset=z).circle(d / 2.0).extrude(h)


def tube(od: float, idia: float, h: float, z: float = 0.0) -> cq.Workplane:
    """Annular cylinder (pipe): outer Ø od, inner Ø idia, height h, base at z."""
    return cyl(od, h, z=z).cut(cyl(idia, h + 2 * BOOL_OVERSHOOT, z=z - BOOL_OVERSHOOT))


def poly_prism(circ_r: float, n: int, h: float, z: float = 0.0,
               fillet: float = 0.0) -> cq.Workplane:
    """Regular n-gon prism: vertices on a circle of radius ``circ_r``, oriented
    with a flat *face* centred toward +X (so vertices sit at ±180/n, 540/n, …).
    Extruded h tall with its base at z. If ``fillet`` > 0 the n vertical corner
    edges are rounded by that radius. The flat-face-toward-+X orientation lines
    the faces up with the handle/rib bearings (0°, 180°, …)."""
    pts = []
    for k in range(n):
        a = math.pi / n + k * 2.0 * math.pi / n      # vertex angles → flat face at 0°
        pts.append((circ_r * math.cos(a), circ_r * math.sin(a)))
    wp = cq.Workplane("XY").workplane(offset=z).polyline(pts).close().extrude(h)
    if fillet > 0.0:
        wp = wp.edges("|Z").fillet(fillet)
    return wp


def compound(parts: list[cq.Workplane]) -> cq.Workplane:
    """Bundle a list of Workplanes into a single Workplane wrapping an
    OCCT compound — no boolean evaluation, so this stays cheap even for
    hundreds of members. A single ``a.cut(compound([...]))`` /
    ``a.union(compound([...]))`` then resolves them all in one BOP pass,
    which OCCT does far faster (and more robustly) than folding hundreds
    of pairwise booleans."""
    solids = []
    for p in parts:
        solids.extend(p.vals())
    return cq.Workplane("XY").newObject([cq.Compound.makeCompound(solids)])


# ── Radial hole cutters ─────────────────────────────────────────────────────
# Both cutters below are built as a flat 2D profile in the YZ plane, extruded
# along +X, then translated out to the wall radius and rotated to the desired
# bearing around the cylinder. They are deliberately *flat* (not swept around
# the cylinder): over the width of any one hole the Ø250 wall barely curves,
# so a flat radial slab — extruded thick enough in X to clear the curved wall
# at the hole's outermost extent — punches a clean hole. See RADIAL_CUT_* in
# dimensions.py for how the X-depth is chosen.


def hex_prism(circ_r: float, x_lo: float, x_hi: float) -> cq.Workplane:
    """Pointy-top hexagonal prism: a regular hexagon (circumradius circ_r,
    one vertex pointing +Z, the opposite vertex −Z, vertical flats on the
    ±Y sides) extruded radially so it spans x ∈ [x_lo, x_hi].

    Built about the origin in z; translate by the desired z afterwards,
    then rotate about Z to place it around the cylinder. The +Z/−Z vertices
    keep the hole supportless: each roof edge sits 30° off horizontal (= a 60°
    overhang) — steeper than ideal but bounded, and a non-issue over a small
    hole's couple-of-mm span (unlike a round hole's flat-horizontal crown)."""
    pts = []
    for k in range(6):
        a = math.radians(90.0 + 60.0 * k)            # first vertex at +Z
        pts.append((circ_r * math.cos(a), circ_r * math.sin(a)))   # (localX→Y, localY→Z)
    return (
        cq.Workplane("YZ")
        .polyline(pts).close()
        .extrude(x_hi - x_lo)
        .translate((x_lo, 0.0, 0.0))
    )


def _gable_pts(af: float, side_h: float) -> list[tuple[float, float]]:
    """Vertices of a pointy-top *gabled* hexagon: vertical side walls of length
    ``side_h`` at ±af/2, capped top and bottom by 45° peaks (height af/2 each).
    Returned as (across-flats axis, pointy axis) so the roof points along ±
    the second coordinate. Total extent: af wide × (side_h + af) tall."""
    h = side_h / 2.0
    a = af / 2.0
    return [(a, h), (0.0, h + a), (-a, h), (-a, -h), (0.0, -(h + a)), (a, -h)]


def gable_prism(af: float, side_h: float, x_lo: float, x_hi: float) -> cq.Workplane:
    """Gabled-hexagon prism in the YZ plane (across-flats along Y, pointy 45°
    caps along ±Z), extruded radially over x ∈ [x_lo, x_hi]. The 45° top cap
    keeps the hole's top edge at a printable overhang — a regular hex's
    30°-off-horizontal roof is too steep on a flared wall. Translate in z and
    rotate about Z to place around the wall."""
    return (
        cq.Workplane("YZ")
        .polyline(_gable_pts(af, side_h)).close()
        .extrude(x_hi - x_lo)
        .translate((x_lo, 0.0, 0.0))
    )


def slit_prism(width: float, height: float, x_lo: float, x_hi: float) -> cq.Workplane:
    """Rectangular vertical-slit prism: tangential ``width`` along Y, vertical
    ``height`` along Z, extruded radially over x ∈ [x_lo, x_hi]. Built centred
    on the origin in Y/Z; translate by the desired z, then rotate about Z to
    place around the wall. Used for the drainage-focused wall perforation —
    dramatically cheaper to boolean than a hex cell (a plain box, and one
    slit replaces several hexes tangentially)."""
    return (
        cq.Workplane("YZ")
        .rect(width, height)
        .extrude(x_hi - x_lo)
        .translate((x_lo, 0.0, 0.0))
    )


def slot_prism(length: float, height: float, x_lo: float, x_hi: float) -> cq.Workplane:
    """Stadium/obround prism: a slot ``length`` long (tangential, along Y),
    ``height`` tall (along Z), with semicircular ends, extruded radially so
    it spans x ∈ [x_lo, x_hi]. Built centred on the origin in Y and Z;
    translate by the desired z, then rotate about Z to place it."""
    return (
        cq.Workplane("YZ")
        .slot2D(length, height, 0)
        .extrude(x_hi - x_lo)
        .translate((x_lo, 0.0, 0.0))
    )


def heal(wp: cq.Workplane) -> cq.Workplane:
    """OCCT ShapeFix + ShapeUpgrade pass before STEP export: cleans up
    minor face/edge tolerance debris that long boolean pipelines leave
    behind (and that strict STEP importers complain about), and merges
    same-domain adjacent faces/edges. Also collapses a one-solid Compound
    down to a plain Solid."""
    from OCP.ShapeFix import ShapeFix_Shape  # type: ignore[import]
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain  # type: ignore[import]
    from OCP.TopAbs import TopAbs_COMPOUND

    shape = wp.val().wrapped
    fixer = ShapeFix_Shape(shape)
    fixer.SetPrecision(1e-4)
    fixer.SetMaxTolerance(1e-3)
    fixer.Perform()
    fixed = fixer.Shape()
    unifier = ShapeUpgrade_UnifySameDomain(fixed, True, True, True)
    unifier.Build()
    unified = unifier.Shape()
    if unified.ShapeType() == TopAbs_COMPOUND:
        wrapped = cq.Compound(unified)
    else:
        wrapped = cq.Solid(unified)
    return cq.Workplane("XY").add(wrapped)
