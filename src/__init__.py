"""Perforated Plant Pot — cadquery model split into focused modules.

  dimensions  — top-level dimensional/material/print constants
  helpers     — geometric helper functions (cyl, tube, hex/slot cutters, heal)
  pot         — constructs the pot body
  build       — main script: builds the part and writes the STEP file

Run from the repo root:
  py -3.12 -m src.build
"""
