#!/bin/bash
# E-023: fixed-weight MC restricted to time-bulk columns. Usage: stage_bulk.sh <probs> <model> [scale%]
cd /Users/ephemeral/Desktop/qec-ai-search
P=$1; M=${2:-sd6}; S=${3:-100}
export PYTHONPATH=.
run() { uv run python -m search.experiments.e023.fixedweight --region bulk --prob $P --model $M --w $1 --n $(( $2 * S / 100 )) --batch $3 --workers 3; }
run 2 6000 1000
run 3 4000 500
run 4 2000 250
run 5,6 1400 200
run 8 800 200
run 10 600 150
run 13 300 150
