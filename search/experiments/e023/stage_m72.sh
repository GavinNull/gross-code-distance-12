#!/bin/bash
# E-023 P2: [[144,12,12]] f_y morphing sw11 (d_circ 6) vs sw01 (7). Usage: stage_m72.sh <model>
cd /Users/ephemeral/Desktop/qec-ai-search
M=${1:-sd6}
export PYTHONPATH=.
for pr in m72_sw11 m72_sw01; do
  [ -f results/E-023-ler-benefit/lowweight/$pr.json ] || {
    uv run python -m search.experiments.e023.lowweight --prob $pr --trials 9000 --chunks 6 --wmax 8 --seed 23003 --workers 3
    uv run python -c "from search.experiments.e023.lowweight import closure_main; closure_main(['--prob','$pr'])"; }
done
S="uv run python -m search.experiments.e023.splits --model $M --decoders= --workers 1"
$S --prob m72_sw11 --tmin 3 --tmax 4 --wmin 6 --wmax 6 --cap 200000 --tag _I6
$S --prob m72_sw11 --tmin 4 --tmax 4 --wmin 7 --wmax 7 --cap 200000 --tag _I7
$S --prob m72_sw11 --tmin 4 --tmax 4 --wmin 8 --wmax 8 --cap 200000 --tag _I8
$S --prob m72_sw01 --tmin 4 --tmax 4 --wmin 7 --wmax 7 --cap 200000 --tag _I7
$S --prob m72_sw01 --tmin 4 --tmax 4 --wmin 8 --wmax 8 --cap 200000 --tag _I8
