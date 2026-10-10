#!/bin/bash
# E-023: ideal-decoder (MLE vs found complement) structural strata, no decoding. Usage: stage_ideal_m54.sh <model>
cd /Users/ephemeral/Desktop/qec-ai-search
M=${1:-sd6}
export PYTHONPATH=.
S="uv run python -m search.experiments.e023.splits --model $M --decoders= --workers 1"
$S --prob m54_paper --tmin 3 --tmax 4 --wmin 6 --wmax 6 --cap 100000 --tag _I6
$S --prob m54_paper --tmin 4 --tmax 4 --wmin 7 --wmax 7 --cap 100000 --tag _I7
$S --prob m54_paper --tmin 4 --tmax 4 --wmin 8 --wmax 8 --cap 100000 --tag _I8
$S --prob m54_repo --tmin 4 --tmax 4 --wmin 7 --wmax 7 --cap 100000 --tag _I7
$S --prob m54_repo --tmin 4 --tmax 4 --wmin 8 --wmax 8 --cap 100000 --tag _I8
