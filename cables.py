# -*- coding: utf-8 -*-
"""CABLES, drawn as OCTAGONAL prisms rather than cylinders.

`oct_cable(pts, d)` is the one entry point: a cable through a polyline, section
an octagon ACROSS-FLATS = `d`, ends left exactly where they are (they are
connector contacts), interior corners filled with no elbow solid at all.

WHY NOT CYLINDERS AND BALL ELBOWS, which is what every one of these models
started with. A sphere meeting two cylinders along a shared circle is the
tangent case OCCT handles worst, and a cable is dozens of them in one fuse.
Measured on a 24 V head (36 points, one loop): the cylinders alone fused
whole, but with the elbow spheres every tolerance came back with 0.19-0.31 of
the cable, or in loose pieces. Worse, the failure is SILENT -- the fuse
returns ONE valid solid with material missing out of the middle (645 of
1776 mm3, once), so nothing raises and only the volume says so. Every boolean
an overlap gate runs against a curved face also costs more than one against
planes, and a model's cables are most of its part pairs.

So: one octagonal prism per segment, ACROSS-FLATS = the cable's diameter, so
the real round cable always fits INSIDE the model and any error lands on the
side of clearance (the corners stand 8 % proud). Bends get no elbow: each
segment runs past an interior corner by half its width, and the overlapping
ends fill the outside of the bend with flat faces. Nothing in the fuse is
tangent to anything.

The prisms are rolled 22.5 degrees so a FLAT, not a corner, faces each
principal direction: stacked lanes then sit flat against each other and
against the floor of a trough.

THE FUSE IS CHECKED BY VOLUME against the section times the path length,
because of the silent loss above. A cable that cannot be fused whole at any
tolerance RAISES rather than returning a cable with holes in it.
"""

from __future__ import annotations

import math as _math

import cadquery as cq

_OCT_R = 1.0 / _math.cos(_math.pi / 8)          # circumradius per unit half-across-flats


def oct_area(d: float) -> float:
    """Section area of a regular octagon, across-flats `d`."""
    return 2.0 * d * d * (_math.sqrt(2.0) - 1.0)


def oct_prism(s0, u, length: float, d: float):
    """One octagonal prism from point `s0` along unit vector `u`, across-flats `d`."""
    ref = cq.Vector(0, 0, 1) if abs(u.z) < 0.9 else cq.Vector(1, 0, 0)
    x = ref.cross(u).normalized()
    plane = cq.Plane(origin=s0, xDir=x, normal=u)
    return (cq.Workplane(plane).transformed(rotate=(0, 0, 22.5))
            .polygon(8, 2 * (d / 2) * _OCT_R).extrude(length).val())


def oct_cable(pts, d: float) -> cq.Workplane:
    """A cable through `pts` (a polyline of (x, y, z)), octagonal section,
    across-flats `d`. See the module docstring for why it is not round."""
    segs = []
    for a, b in zip(pts, pts[1:]):
        va, vb = cq.Vector(*a), cq.Vector(*b)
        if (vb - va).Length > 1e-6:
            segs.append((va, vb))
    if not segs:
        return cq.Workplane("XY")
    r = d / 2.0
    parts = []
    for i, (va, vb) in enumerate(segs):
        u = (vb - va).normalized()
        s0 = va - u * r if i > 0 else va
        s1 = vb + u * r if i < len(segs) - 1 else vb
        parts.append(oct_prism(s0, u, (s1 - s0).Length, d))
    if len(parts) == 1:
        return cq.Workplane("XY").add(parts[0])
    want = oct_area(d) * sum((vb - va).Length for va, vb in segs)
    for tol in (None, 1e-5, 1e-4):
        try:
            fused = parts[0].fuse(*parts[1:], tol=tol) if tol else parts[0].fuse(*parts[1:])
        except Exception:
            continue
        if fused.Solids() and fused.Volume() >= 0.9 * want:
            return cq.Workplane("XY").add(fused.clean())
    raise RuntimeError("oct_cable: no fuse tolerance returned a whole cable "
                       "(%d segments, wanted >= %.1f mm3)" % (len(segs), want))


def helix_pts(cx: float, cy: float, z0: float, z1: float, turns: float,
              r: float, per_turn: int = 8):
    """A helix as a POLYLINE, for feeding to `oct_cable`.

    A swept round profile along a helical wire is one solid and so does not risk
    the fuse above -- but it puts a curved cable in the middle of an octagonal
    run, and the two then meet in exactly the tangent boolean this module exists
    to avoid. Approximating the helix in segments keeps one section for the whole
    cable.

    THE POLYLINE CIRCUMSCRIBES the true helix: its vertices sit at
    r / cos(pi/per_turn), so the chord midpoints land exactly on r and no part of
    the path ever falls INSIDE it. Inscribing instead would have drawn the coil
    up to r*(1 - cos(pi/per_turn)) short of where the cable really runs -- 0.7 mm
    at 8 per turn on a 9 mm coil -- and understating a swept envelope is the one
    error this model cannot afford. Circumscribed, the error lands on the side of
    clearance, exactly as the octagonal section itself does.

    `per_turn` is a face-count knob, and a coarse one is fine BECAUSE of the
    above: a 7-turn coil costs ~900 faces at 6, ~1200 at 8, ~2000 at 16, against
    about 5 for a swept round profile. 8 is the default; raise it only where the
    coil's SHAPE (not its envelope) is what matters.
    """
    n = max(int(round(turns * per_turn)), 1)
    rc = r / _math.cos(_math.pi / per_turn)
    out = []
    for i in range(n + 1):
        f = i / float(n)
        a = 2.0 * _math.pi * turns * f
        out.append((cx + rc * _math.cos(a), cy + rc * _math.sin(a), z0 + (z1 - z0) * f))
    return out
