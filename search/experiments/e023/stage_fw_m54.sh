#!/bin/bash
# E-023: fixed-weight MC for the [[54]] pair. Usage: stage_fw_m54.sh <model> [scale]
cd /Users/ephemeral/Desktop/qec-ai-search
M=${1:-sd6}
S=${2:-1}
export PYTHONPATH=.
P=m54_paper,m54_repo
run() { uv run python -m search.experiments.e023.fixedweight --prob $P --model $M --w $1 --n $(( $2 * S / 1 )) --batch 200 --workers 3; }
run 2,3,4 2000
run 1 600
run 5,6 1400
run 8,10 800
run 13,16 400
