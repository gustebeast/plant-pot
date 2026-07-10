"""Perforated Plant Pot — main build script.

Run from the project folder:
  py -3.12 -m src.build              # build both the inner (perforated) pot and the outer cachepot
  py -3.12 -m src.build --mesh       # also write a 3MF mesh (slice from the STEP otherwise)
  py -3.12 -m src.build --list       # list available part names

Produces plant_inner_pot.step and plant_outer_pot.step next to this script,
plus a combined assembly.step, and opens/refreshes it in the shared FreeCAD
viewer.
"""

import argparse
import os
import pathlib
import sys
import time

import cadquery as cq

# Shared helpers from Archive/3D/freecad: show() (opens/refreshes the FreeCAD
# viewer hub — never raises), export_step() (names the STEP product after its
# file), color() (cq.Color from hex / 0..255 / SVG names). See cadkit/README.md.
from cadkit.freecad import show
from cadkit.step_export import export_step
from cadkit.cq_colors import color

# All outputs anchor to this script's folder, not the cwd — so `py -3.12 -m
# src.build` run from any parent still lands its STEPs in the project folder.
OUT = pathlib.Path(__file__).resolve().parent.parent

# Mesh (3MF) tessellation tolerances — fine enough that the cone/cylinder walls
# and corner fillets stay smooth at this size (the flat hex faces are exact).
_MESH_TOL     = 0.05   # max linear deviation (mm)
_MESH_ANG_TOL = 0.2    # max angular deviation (rad)

# Assembly palette — sage inner (plant), terracotta outer (pot), salmon counter.
COLOR = {
    "inner_pot":     "#7CA982",
    "outer_pot":     "#8D6E63",
    "build_counter": "#F0A878",
}

from . import dimensions as d
from .helpers import heal
from . import pot as _pot_mod

pot       = heal(_pot_mod.pot)
outer_pot = heal(_pot_mod.outer_pot)

_SHAPE_NOTE = f"{d.NUM_FACES}-sided" if d.IS_POLY else "round"
_OD_NOTE = (f"Ø{d.POT_OD_BASE:.0f}-{d.POT_OD_TOP:.0f}" if d.IS_TAPER else f"Ø{d.POT_OD:.0f}")

_handles_note = (f"{d.HANDLE_COUNT} grab handles ({d.HANDLE_FINGERS} hex finger holes each)"
                 if d.HANDLE_COUNT else "no handles")
_ribs_note    = (f"{d.RIB_COUNT} internal ribs" if d.RIB_COUNT else "no internal ribs")
_floor_note   = ("ribbed floor" if (d.FLOOR_SPOKE_COUNT or d.FLOOR_RING_COUNT) else "plain floor")
_INNER_NOTE = (
    f"{_SHAPE_NOTE} {_OD_NOTE} × {d.POT_H:.0f} mm (across-{'corners' if d.IS_POLY else 'diam'}"
    f"{', tapered' if d.IS_TAPER else ''}), "
    f"{d.WALL_T:g} mm wall + {d.FLOOR_T:g} mm floor; "
    f"vertical-slit wall + radial-slit floor perforation, "
    f"{_handles_note}, {_ribs_note}, {_floor_note}. Print in PETG, no supports."
)
_outer_h = d.PERF_TOP_Z + 5.0 + d.FLOOR_T   # mirrors _build_outer_pot()
_outer_od_base = d.POT_OD_BASE + 2.0 * d.WALL_T + 6.0
_outer_od_top  = ((d.POT_OD_BASE + (d.POT_OD_TOP - d.POT_OD_BASE) * _outer_h / d.POT_H)
                  + 2.0 * d.WALL_T + 6.0)
_OUTER_OD_NOTE = (f"Ø{_outer_od_base:.0f}-{_outer_od_top:.0f}" if d.IS_TAPER
                  else f"Ø{_outer_od_base:.0f}")
_OUTER_NOTE = (
    f"{_SHAPE_NOTE} outer cachepot {_OUTER_OD_NOTE} × {_outer_h:.0f} mm (across-"
    f"{'corners' if d.IS_POLY else 'diam'}{', tapered' if d.IS_TAPER else ''}), "
    f"{d.WALL_T:g} mm wall + {d.FLOOR_T:g} mm floor — sized to hold the inner pot with "
    f"3 mm clearance per side. Plain solid (no holes). Print in PETG."
)

# Map of part name → (workplane, output filename, optional note).
PARTS = {
    "inner": (pot,       "plant_inner_pot.step", _INNER_NOTE),
    "outer": (outer_pot, "plant_outer_pot.step", _OUTER_NOTE),
}


def _export(name: str, mesh: bool = False) -> str:
    obj, filename, note = PARTS[name]
    path = str(OUT / filename)
    export_step(obj, path)
    suffix = f"  ({note})" if note else ""
    print(f"Wrote {path}{suffix}")
    if mesh:
        _export_mesh(obj, path)
    return path


def _export_mesh(obj, step_path: str) -> str:
    """Write a 3MF mesh next to the STEP (opt-in via --mesh). It's far lighter
    than the dense B-rep STEP, but the OCCT 3MF writer rendered oddly in Bambu
    Studio in testing, so STEP is the default slicing path. We tessellate here
    so we control the resolution."""
    mesh_path = os.path.splitext(step_path)[0] + ".3mf"
    t0 = time.time()
    cq.exporters.export(obj, mesh_path, tolerance=_MESH_TOL, angularTolerance=_MESH_ANG_TOL)
    dt = time.time() - t0
    mb = os.path.getsize(mesh_path) / 1e6
    print(f"Wrote {mesh_path}  (mesh for slicing — {dt:.1f}s, {mb:.1f} MB)")
    return mesh_path


# ── Build counter ────────────────────────────────────────────────────────────
# A 3-D number floating above the assembly, bumped on every full build. Lets
# you see at a glance in the viewer that a fresh build landed. Stored in
# tools/build_counter.txt (gitignored); starts at 1 if missing.
_BUILD_COUNTER_FILE = OUT / "tools" / "build_counter.txt"


def _bump_build_counter() -> int:
    try:
        n = int(_BUILD_COUNTER_FILE.read_text().strip()) + 1
    except (OSError, ValueError):
        n = 1
    try:
        _BUILD_COUNTER_FILE.write_text(f"{n}\n")
    except OSError:
        pass
    return n


def _build_counter_model(n: int):
    """Upright extruded number, centred at X=0 and floating above the pot's
    rim. Returns None if the text engine isn't available — a font hiccup must
    not break the build."""
    try:
        return (
            cq.Workplane("XZ")
            .center(0, d.POT_H + 30)
            .text(str(n), 20, 4)
        )
    except Exception:
        return None


def _export_assembly() -> None:
    """Combined view model: the inner (perforated) pot nested in the outer
    cachepot, saved as assembly.step for the shared FreeCAD viewer — each part
    stays individually show/hide-able."""
    build_n = _bump_build_counter()
    asm = (cq.Assembly(name="plant_pot")
           .add(pot,       name="inner_pot", color=color(COLOR["inner_pot"]))
           .add(outer_pot, name="outer_pot", color=color(COLOR["outer_pot"])))
    counter = _build_counter_model(build_n)
    if counter is not None:
        asm.add(counter, name="build_counter", color=color(COLOR["build_counter"]))
    path = str(OUT / "assembly.step")
    asm.save(path)
    print(f"Wrote {path}  [build #{build_n}]", flush=True)
    show(path)


def main() -> None:
    p = argparse.ArgumentParser(prog="src.build", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--part", help="Build only this part.")
    p.add_argument("--list", action="store_true", help="List part names and exit.")
    p.add_argument("--mesh", action="store_true", help="Also write a 3MF mesh (off by default; slice from the STEP).")
    args = p.parse_args()

    if args.list:
        for name in PARTS:
            print(name)
        return

    if args.part:
        if args.part not in PARTS:
            print(f"unknown part: {args.part!r}. Use --list to see options.", file=sys.stderr)
            sys.exit(2)
        _export(args.part, mesh=args.mesh)
    else:
        for name in PARTS:
            _export(name, mesh=args.mesh)

    _export_assembly()


main()
