#!/bin/bash
# E-023: SI1000 (CX-native) runs: ideal strata for m54 / BB108, decoded BB108 leading strata, m54 bulk MC (50%).
cd /Users/ephemeral/Desktop/qec-ai-search
export PYTHONPATH=.
search/experiments/e023/stage_ideal_m54.sh si1000
search/experiments/e023/stage_bb108.sh si1000
I="uv run python -m search.experiments.e023.splits --model si1000 --decoders= --workers 1"
$I --prob bb108_twocolour --tmin 5 --tmax 5 --wmin 11 --wmax 11 --cap 200000 --tag _I11
$I --prob bb108_ibm --tmin 5 --tmax 5 --wmin 11 --wmax 11 --cap 200000 --tag _I11
S="uv run python -m search.experiments.e023.splits --model si1000 --workers 3"
$S --prob bb108_ibm --tmin 4 --tmax 4 --wmin 8 --wmax 8 --cap 600 --tag _D8b
$S --prob bb108_ibm --tmin 5 --tmax 5 --wmin 9 --wmax 9 --cap 400 --tag _D9
$S --prob bb108_ibm --tmin 5 --tmax 5 --wmin 10 --wmax 10 --cap 400 --tag _D10
$S --prob bb108_ibm --tmin 4 --tmax 4 --wmin 9 --wmax 9 --cap 1000 --tag _D9a
$S --prob bb108_twocolour --tmin 5 --tmax 5 --wmin 10 --wmax 10 --cap 600 --tag _D10b
$S --prob bb108_twocolour --tmin 4 --tmax 4 --wmin 10 --wmax 10 --cap 1000 --tag _D10a
search/experiments/e023/stage_bulk.sh m54_paper,m54_repo si1000 50
