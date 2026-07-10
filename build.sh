#!/usr/bin/env bash
# Requires Python 3.12 with cadquery installed:
#   py -3.12 -m pip install cadquery
set -e
# Builds both pots + a combined assembly.step and opens/refreshes them in the
# shared FreeCAD viewer (handled inside src.build).
py -3.12 -m src.build
