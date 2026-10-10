#!/bin/bash
# E-023 P3: larger HT samples of the weight-4 subsets of W9-W11 logicals (decoder-specific failures). Usage: <model>
cd /Users/ephemeral/Desktop/qec-ai-search
M=${1:-sd6}
export PYTHONPATH=.
S="uv run python -m search.experiments.e023.splits --model $M --workers 3"
$S --prob bb108_ibm --tmin 4 --tmax 4 --wmin 9 --wmax 9 --cap 2000 --tag _D9a
$S --prob bb108_ibm --tmin 4 --tmax 4 --wmin 10 --wmax 10 --cap 2000 --tag _D10a
$S --prob bb108_ibm --tmin 4 --tmax 4 --wmin 11 --wmax 11 --cap 2000 --tag _D11a
$S --prob bb108_twocolour --tmin 4 --tmax 4 --wmin 10 --wmax 10 --cap 2000 --tag _D10a
$S --prob bb108_twocolour --tmin 4 --tmax 4 --wmin 11 --wmax 11 --cap 2000 --tag _D11a
