#!/usr/bin/env bash
# Requires Python 3.12 with cadquery installed:
#   py -3.12 -m pip install cadquery
set -e
# Builds the inner pot (pass `--part outer|both` for the cachepot) and refreshes
# the cadkit web viewer (handled inside src.build).
py -3.12 -m src.build "$@"
