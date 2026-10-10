#!/bin/bash
# E-023: structural cores for the [[54]] pair. Usage: stage_splits_m54.sh <model> [cap]
cd /Users/ephemeral/Desktop/qec-ai-search
M=${1:-sd6}
C=${2:-300}
export PYTHONPATH=.
uv run python -m search.experiments.e023.splits --prob m54_paper --model $M --tmin 2 --tmax 3 --wmin 6 --wmax 6 --cap $C --tag _W6
uv run python -m search.experiments.e023.splits --prob m54_repo --model $M --tmin 3 --tmax 4 --wmin 7 --wmax 7 --cap $C --tag _W7
uv run python -m search.experiments.e023.splits --prob m54_paper --model $M --tmin 3 --tmax 3 --wmin 7 --wmax 7 --cap $C --tag _W7
uv run python -m search.experiments.e023.splits --prob m54_repo --model $M --tmin 4 --tmax 4 --wmin 8 --wmax 8 --cap $C --tag _W8
