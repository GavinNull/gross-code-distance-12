#!/bin/bash
# E-023 P3: BB108 full-region fixed-weight MC (moderate w, where decoders fail). Usage: stage_fw_bb108.sh <model>
cd /Users/ephemeral/Desktop/qec-ai-search
M=${1:-sd6}
export PYTHONPATH=.
P=bb108_ibm,bb108_twocolour
run() { uv run python -m search.experiments.e023.fixedweight --prob $P --model $M --w $1 --n $2 --batch $3 --workers 3; }
run 6,10 1500 500
run 14,18 1500 300
run 24 1000 200
run 30 600 150
run 36 400 100
