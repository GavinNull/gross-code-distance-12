#!/bin/bash
# E-023 P3: BB108 bulk fixed-weight MC. Usage: stage_bulk_bb108.sh <model> [scale%]
cd /Users/ephemeral/Desktop/qec-ai-search
M=${1:-sd6}; S=${2:-50}
export PYTHONPATH=.
P=bb108_ibm,bb108_twocolour
run() { uv run python -m search.experiments.e023.fixedweight --region bulk --prob $P --model $M --w $1 --n $(( $2 * S / 100 )) --batch $3 --workers 3; }
run 2 8000 1000
run 3 6000 750
run 4 4000 500
run 5,6 3000 300
run 8 2000 250
run 10,12 1200 200
run 15,19 600 100
