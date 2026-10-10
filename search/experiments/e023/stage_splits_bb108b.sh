#!/bin/bash
# E-023 P3: decoder-specific weight-4/5 failures from higher-weight logicals (W9-W11). Usage: stage_splits_bb108b.sh <model>
cd /Users/ephemeral/Desktop/qec-ai-search
M=${1:-sd6}
export PYTHONPATH=.
S="uv run python -m search.experiments.e023.splits --model $M --workers 3"
$S --prob bb108_ibm --tmin 4 --tmax 4 --wmin 9 --wmax 9 --cap 300 --tag _D9a
$S --prob bb108_ibm --tmin 4 --tmax 4 --wmin 10 --wmax 10 --cap 300 --tag _D10a
$S --prob bb108_ibm --tmin 4 --tmax 4 --wmin 11 --wmax 11 --cap 300 --tag _D11a
$S --prob bb108_twocolour --tmin 4 --tmax 4 --wmin 11 --wmax 11 --cap 300 --tag _D11a
$S --prob bb108_twocolour --tmin 5 --tmax 5 --wmin 11 --wmax 11 --cap 300 --tag _D11b
