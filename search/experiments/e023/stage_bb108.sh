#!/bin/bash
# E-023 P3: BB108 IBM (<=8) vs two-colour (10). E-016 logicals imported; ideal strata; bulk MC. Usage: stage_bb108.sh <model>
cd /Users/ephemeral/Desktop/qec-ai-search
M=${1:-sd6}
export PYTHONPATH=.
[ -f results/E-023-ler-benefit/lowweight/bb108_ibm.json ] || uv run python -m search.experiments.e023.import_e016
S="uv run python -m search.experiments.e023.splits --model $M --decoders= --workers 1"
$S --prob bb108_ibm --tmin 4 --tmax 5 --wmin 8 --wmax 8 --cap 200000 --tag _I8
$S --prob bb108_ibm --tmin 5 --tmax 5 --wmin 9 --wmax 9 --cap 200000 --tag _I9
$S --prob bb108_ibm --tmin 5 --tmax 5 --wmin 10 --wmax 10 --cap 200000 --tag _I10
$S --prob bb108_twocolour --tmin 5 --tmax 5 --wmin 10 --wmax 10 --cap 200000 --tag _I10
