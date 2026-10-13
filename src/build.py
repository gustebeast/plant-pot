"""Perforated Plant Pot — main build script.

Run from the project folder:
  py -3.12 -m src.build              # build the inner (perforated) pot — the usual case
  py -3.12 -m src.build --part outer # build ONLY the outer cachepot
  py -3.12 -m src.build --part both  # build both
  py -3.12 -m src.build --mesh       # also write a 3MF mesh (slice from the STEP otherwise)
  py -3.12 -m src.build --list       # list available part names

Produces plant_inner_pot.step (and/or plant_outer_pot.step) next to this
project, and refreshes the model in the cadkit web viewer. No assembly.step is
written — the viewer is handed the parts directly.
"""

import argparse
import os
import pathlib
import sys
import time

import cadquery as cq

# Shared helpers from cadkit: show() (opens/refreshes the web viewer tab
# — never raises), export_step() (names the STEP product after its
# file), color() (cq.Color from hex / 0..255 / SVG names). See cadkit/README.md.
from cadkit.web import show
from cadkit.step_export import export_print
from cadkit.orientation import (PrintOrientation as PO,
                                require_declared, unconfirmed)
from cadkit.cq_colors import color

# All outputs anchor to this script's folder, not the cwd — so `py -3.12 -m
# src.build` run from any parent still lands its STEPs in the project folder.
OUT = pathlib.Path(__file__).resolve().parent.parent

# Mesh (3MF) tessellation tolerances — fine enough that the cone/cylinder walls
# and corner fillets stay smooth at this size (the flat hex faces are exact).
_MESH_TOL     = 0.05   # max linear deviation (mm)
_MESH_ANG_TOL = 0.2    # max angular deviation (rad)

# Assembly palette — sage inner (plant), terracotta outer (pot).
COLOR = {
    "inner_pot":     "#7CA982",
    "outer_pot":     "#8D6E63",
}

# `--part inner|outer|both` must be known BEFORE the geometry modules are
# imported: pot.py builds at import time, and a part that wasn't asked for
# shouldn't be built at all. Peek at argv here and hand it to pot.py as POT_PART
# (which also works on its own: `POT_PART=both py -3.12 -m src.build`).
# Default is the inner pot alone — the cachepot is rarely wanted.
_pre = argparse.ArgumentParser(add_help=False)
_pre.add_argument("--part", choices=("inner", "outer", "both"))
_part_arg = _pre.parse_known_args()[0].part
if _part_arg:
    os.environ["POT_PART"] = _part_arg
del _pre, _part_arg

from . import dimensions as d
from .helpers import heal, step
from . import pot as _pot_mod

# Under POT_NOBUILD (set inside pot.py before spawning multiprocessing
# workers), the two module-level builds in pot.py return None — skip the
# heal so the worker's import of build.py doesn't crash on None.val().
if os.environ.get("POT_NOBUILD") == "1":
    pot = outer_pot = None
else:
    pot       = heal(_pot_mod.pot, label="heal inner") if _pot_mod.pot is not None else None
    outer_pot = heal(_pot_mod.outer_pot, label="heal outer") if _pot_mod.outer_pot is not None else None

_SHAPE_NOTE = "rectangular" if d.IS_RECT else f"{d.NUM_FACES}-sided" if d.IS_POLY else "round"
if d.IS_RECT:
    _OD_NOTE = (f"{d.RECT_BASE[0]:g}x{d.RECT_BASE[1]:g} base - {d.RECT_TOP[0]:g}x{d.RECT_TOP[1]:g} top"
                if d.IS_TAPER else f"{d.RECT_TOP[0]:g}x{d.RECT_TOP[1]:g}")
else:
    _OD_NOTE = (f"Ø{d.POT_OD_BASE:.0f}-{d.POT_OD_TOP:.0f}" if d.IS_TAPER else f"Ø{d.POT_OD:.0f}")
_EXTENT_NOTE = "L x W" if d.IS_RECT else "across-corners" if d.IS_POLY else "across-diam"

_handles_note = (f"{d.HANDLE_COUNT} grab handles ({d.HANDLE_FINGERS} gable finger holes each)"
                 if d.HANDLE_COUNT else "no handles")
_ribs_note    = (f"{d.RIB_COUNT} internal ribs" if d.RIB_COUNT else "no internal ribs")
_floor_note   = ("ribbed floor" if (d.FLOOR_SPOKE_COUNT or d.FLOOR_RING_COUNT) else "plain floor")
_INNER_NOTE = (
    f"{_SHAPE_NOTE} {_OD_NOTE} × {d.POT_H:.0f} mm ({_EXTENT_NOTE}"
    f"{', tapered' if d.IS_TAPER else ''}), "
    f"{d.WALL_T:g} mm wall + {d.FLOOR_T:g} mm floor; "
    f"vertical-slit wall + radial-slit floor perforation, "
    f"{_handles_note}, {_ribs_note}, {_floor_note}. Print in PETG, no supports."
)
_OUTER_FLOOR_GAP = 3.0   # matches _build_outer_pot(); floor clearance in the assembly
_outer_h = d.PERF_TOP_Z + 5.0 + d.FLOOR_T + d.FLOOR_T + _OUTER_FLOOR_GAP   # mirrors _build_outer_pot()
_outer_od_base = d.POT_OD_BASE + 2.0 * d.WALL_T + 6.0
_outer_od_top  = ((d.POT_OD_BASE + (d.POT_OD_TOP - d.POT_OD_BASE) * _outer_h / d.POT_H)
                  + 2.0 * d.WALL_T + 6.0)
_OUTER_OD_NOTE = (f"Ø{_outer_od_base:.0f}-{_outer_od_top:.0f}" if d.IS_TAPER
                  else f"Ø{_outer_od_base:.0f}")
if d.IS_RECT:
    _o = 2.0 * d.WALL_T + 6.0
    _bx, _by = d.rect_half(0.0)
    _tx, _ty = d.rect_half(_outer_h)
    _OUTER_OD_NOTE = (f"{2*_bx+_o:.0f}x{2*_by+_o:.0f} base - {2*_tx+_o:.0f}x{2*_ty+_o:.0f} top"
                      if d.IS_TAPER else f"{2*_bx+_o:.0f}x{2*_by+_o:.0f}")
_OUTER_NOTE = (
    f"{_SHAPE_NOTE} outer cachepot {_OUTER_OD_NOTE} × {_outer_h:.0f} mm ({_EXTENT_NOTE}"
    f"{', tapered' if d.IS_TAPER else ''}), "
    f"{d.WALL_T:g} mm wall + {d.FLOOR_T:g} mm floor — sized to hold the inner pot with "
    f"3 mm clearance per side. Plain solid (no holes). Print in PETG."
)

# Map of part name → (workplane, output filename, optional note). A part that
# wasn't built this run (--part / POT_PART) has workplane None.
PARTS = {
    "inner": (pot,       "plant_inner_pot.step", _INNER_NOTE),
    "outer": (outer_pot, "plant_outer_pot.step", _OUTER_NOTE),
}

# ── PRINT ORIENTATION — every printed part's bed face, declared once
# (cadkit's contract: see cadkit/AGENTS.md and cadkit.orientation). Export
# reads THIS, so the STEPs land in the slicer already on the right face.
#
# Both pots were already declared, in prose, in README's "Print orientation"
# section: upright, open end up, on the flat 2 mm floor, no supports
# anywhere. Both are modelled that way too — floor at z = 0, growing up —
# so the declaration is `None`, "models as printed". CONFIRMED because the
# README states it as a print-validated decision with its reasoning (the
# gabled hex perforations are 45° precisely so this orientation needs no
# support); this is not a guess that needs settling.
PRINT_ORIENTATION = {
    "inner": PO(None, "upright, open end up, on the flat 2 mm floor "
                      "(README: Print orientation) — the gabled 45 deg hex "
                      "perforations are shaped for exactly this print, so it "
                      "needs no support"),
    "outer": PO(None, "upright on its flat floor, same as the inner pot "
                      "(README: Print orientation). Plain solid, no holes: "
                      "measured overhang-free in this orientation"),
}
require_declared(set(PARTS), PRINT_ORIENTATION)


def _export(name: str, mesh: bool = False) -> str:
    obj, filename, note = PARTS[name]
    path = str(OUT / filename)
    step(f"export {filename}",
         lambda: export_print(obj, PRINT_ORIENTATION[name], path))
    suffix = f"  ({note})" if note else ""
    print(f"Wrote {path}{suffix}", flush=True)
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
    print(f"Wrote {mesh_path}  (mesh for slicing — {dt:.1f}s, {mb:.1f} MB)", flush=True)
    return mesh_path


# ── Build counter ────────────────────────────────────────────────────────────
# Bumped on every full build and shown by the viewer beside the build's time, so a
# fresh build is seen to have landed. Stored in tools/build_counter.txt (gitignored);
# starts at 1 if missing.
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


def _show() -> None:
    """Hand the parts built this run to the web viewer (cadkit.web) — a list of
    (name, solid, colour), no assembly STEP. With both pots built, the inner is
    shown nested in the outer cachepot."""
    build_n = _bump_build_counter()
    parts = []
    if pot is not None:
        parts.append(("inner_pot", pot, color(COLOR["inner_pot"])))
    if outer_pot is not None:
        # Shift outer DOWN by (FLOOR_T + gap) so the inner-pot floor sits
        # `_OUTER_FLOOR_GAP` above the outer's cavity floor (matches the per-side
        # wall clearance). The exported STEP for the outer part is UN-shifted —
        # this shift only affects the combined view.
        _outer_z = -(d.FLOOR_T + _OUTER_FLOOR_GAP) if pot is not None else 0.0
        parts.append(("outer_pot", outer_pot.translate((0, 0, _outer_z)), color(COLOR["outer_pot"])))
    print(f"[build #{build_n}]", flush=True)
    step("web viewer", lambda: show(parts, root=OUT, title="Plant pot", extras={"build": build_n}))


def main() -> None:
    p = argparse.ArgumentParser(prog="src.build", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--part", choices=(*PARTS, "both"), help="Which pot to build (default: inner).")
    p.add_argument("--list", action="store_true", help="List part names and exit.")
    p.add_argument("--mesh", action="store_true", help="Also write a 3MF mesh (off by default; slice from the STEP).")
    args = p.parse_args()

    # 🚩 an UNCONFIRMED bed face is a guess nobody has checked — and the bed
    # face decides which faces are overhangs, so work done on top of a guess
    # can be silently wrong. Say so on every build (cadkit AGENTS.md).
    flagged = unconfirmed(PRINT_ORIENTATION)
    if flagged:
        print("UNCONFIRMED print orientation (confirm with the user BEFORE "
              "working on these parts): " + ", ".join(flagged), flush=True)

    if args.list:
        for name in PARTS:
            print(name)
        return

    for name, (obj, filename, _note) in PARTS.items():
        if obj is not None:
            _export(name, mesh=args.mesh)
            continue
        # Not built this run. A leftover STEP from an earlier, different pot
        # would sit next to the fresh one looking like its matching half —
        # remove it so the folder only ever holds parts from THIS build.
        stale = OUT / filename
        if stale.exists():
            stale.unlink()
            print(f"Removed stale {filename} (not built this run — it was from an earlier build)", flush=True)

    _show()


# Guard the top-level main() call so `multiprocessing` on Windows (spawn
# semantics) can safely re-import `src.build` inside worker subprocesses.
# Windows spawn re-executes `-m src.build`, so `__name__ == "__main__"` is
# TRUE in the worker too — the env var is the worker-vs-real-invocation
# signal. The parallel-intersect path in pot.py sets POT_NOBUILD=1 in
# `os.environ` before spawning, so workers skip both the geometry build
# (pot.py) and the export/assembly (this file).
if __name__ == "__main__" and os.environ.get("POT_NOBUILD") != "1":
    main()
