#!/bin/bash
# E-023 P3: BB108 structural cores decoded by BP-OSD / Relay5 (HT subsamples). Usage: stage_splits_bb108.sh <model>
cd /Users/ephemeral/Desktop/qec-ai-search
M=${1:-sd6}
export PYTHONPATH=.
S="uv run python -m search.experiments.e023.splits --model $M --workers 3"
$S --prob bb108_ibm --tmin 3 --tmax 3 --wmin 8 --wmax 8 --cap 300 --tag _D8a
$S --prob bb108_ibm --tmin 4 --tmax 4 --wmin 8 --wmax 8 --cap 600 --tag _D8b
$S --prob bb108_ibm --tmin 5 --tmax 5 --wmin 9 --wmax 9 --cap 400 --tag _D9
$S --prob bb108_ibm --tmin 5 --tmax 5 --wmin 10 --wmax 10 --cap 400 --tag _D10
$S --prob bb108_twocolour --tmin 4 --tmax 4 --wmin 10 --wmax 10 --cap 300 --tag _D10a
$S --prob bb108_twocolour --tmin 5 --tmax 5 --wmin 10 --wmax 10 --cap 600 --tag _D10b
