"""Geometry regression check.

Compares the bbox / volume / center-of-mass of every .step file in the
repo root against the committed baseline (`tools/baseline.tsv`). Catches
accidental geometry changes during refactors.

Usage:
  py -3.12 -m src.build              # rebuild
  py -3.12 tools/check_geometry.py   # diff vs baseline

To bless a deliberate geometry change as the new baseline:
  py -3.12 tools/check_geometry.py --update-baseline
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import cadquery as cq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baseline.tsv")

HEADER = "file\tvolume\txmin\txmax\tymin\tymax\tzmin\tzmax\tcx\tcy\tcz"


def measure(path: str) -> str:
    shape = cq.importers.importStep(path).val()
    vol = shape.Volume()
    bb = shape.BoundingBox()
    c = shape.Center()
    name = os.path.basename(path)
    return (f"{name}\t{vol:.6f}\t{bb.xmin:.6f}\t{bb.xmax:.6f}\t"
            f"{bb.ymin:.6f}\t{bb.ymax:.6f}\t"
            f"{bb.zmin:.6f}\t{bb.zmax:.6f}\t"
            f"{c.x:.6f}\t{c.y:.6f}\t{c.z:.6f}")


def collect() -> list[str]:
    # The outer cachepot's dimensions depend on the env-set inner-pot config
    # (POT_OD/H/etc.) and isn't a fixed reference, so it's not baselined.
    files = sorted(f for f in glob.glob(os.path.join(ROOT, "*.step"))
                   if os.path.basename(f) != "plant_outer_pot.step")
    if not files:
        sys.stderr.write("No .step files in repo root. Run `py -3.12 -m src.build` first.\n")
        sys.exit(2)
    return [HEADER] + [measure(f) for f in files]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--update-baseline", action="store_true",
                   help="Overwrite tools/baseline.tsv with current measurements")
    args = p.parse_args()

    rows = collect()
    current = "\n".join(rows) + "\n"

    if args.update_baseline:
        with open(BASELINE, "w", encoding="utf-8") as f:
            f.write(current)
        print(f"Wrote {BASELINE} ({len(rows) - 1} parts)")
        return 0

    if not os.path.exists(BASELINE):
        sys.stderr.write(f"No baseline at {BASELINE}. "
                         "Run with --update-baseline to create one.\n")
        return 2

    with open(BASELINE, "r", encoding="utf-8") as f:
        baseline = f.read()

    if current == baseline:
        print(f"OK — {len(rows) - 1} parts match baseline")
        return 0

    base_lines = baseline.splitlines()
    cur_lines = current.splitlines()
    base_by_name = {ln.split("\t")[0]: ln for ln in base_lines[1:]}
    cur_by_name = {ln.split("\t")[0]: ln for ln in cur_lines[1:]}
    keys = sorted(set(base_by_name) | set(cur_by_name))
    diffs = 0
    for k in keys:
        b = base_by_name.get(k)
        c = cur_by_name.get(k)
        if b == c:
            continue
        diffs += 1
        if b is None:
            print(f"NEW   {k}")
            print(f"  cur:  {c}")
        elif c is None:
            print(f"GONE  {k}")
            print(f"  base: {b}")
        else:
            print(f"DIFF  {k}")
            print(f"  base: {b}")
            print(f"  cur:  {c}")
    print(f"\n{diffs} part(s) differ from baseline.")
    print("If the change is intentional, run with --update-baseline.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
