#!/bin/sh
# E-045 Part C: exact d_circ(R) at small R for project circuits whose window conditions fail (one process at a time).
cd "$(dirname "$0")/../../.."
P="uv run python -m search.experiments.e045.partC"
$P dmin ctl_p10 X 1 3 10 11
$P dmin fig12 Z 1 3 10 11
$P dmin fig12 X 1 3 10 11
$P dmin p18w X 1 2 11 12
$P dmin p18w Z 1 2 11 12
