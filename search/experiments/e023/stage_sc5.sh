#!/bin/bash
# E-023 positive control: rotated surface code d=5, good vs bad CNOT order (d_circ 5 vs 3), MWPM. Usage: stage_sc5.sh <model>
cd /Users/ephemeral/Desktop/qec-ai-search
M=${1:-sd6}
export PYTHONPATH=.
S="uv run python -m search.experiments.e023.splits --model $M --workers 1"
$S --prob sc5_bad --decoders=pymatching --tmin 1 --tmax 3 --wmin 3 --wmax 5 --cap 100000 --tag _W
$S --prob sc5_good --decoders=pymatching --tmin 1 --tmax 3 --wmin 5 --wmax 6 --cap 100000 --tag _W
$S --prob sc5_bad --decoders= --tmin 2 --tmax 3 --wmin 3 --wmax 5 --cap 100000 --tag _I
$S --prob sc5_good --decoders= --tmin 3 --tmax 3 --wmin 5 --wmax 6 --cap 100000 --tag _I
uv run python -m search.experiments.e023.fixedweight --prob sc5_good,sc5_bad --model $M --w 1:12 --n 20000 --batch 5000 --decoders pymatching --workers 3
uv run python -m search.experiments.e023.fixedweight --prob sc5_good,sc5_bad --model $M --direct 0.003,0.002 --n 40000 --batch 10000 --decoders pymatching --workers 3
