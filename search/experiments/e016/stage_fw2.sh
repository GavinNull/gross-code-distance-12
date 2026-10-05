#!/bin/bash
# E-016 阶段 C2 + D：低权重层（p=1e-3 外推的关键区）+ 在全部固定权重样本上补跑联合 Relay5。
set -e
cd "$(dirname "$0")/../../.."
W=${WORKERS:-3}
run() { PYTHONPATH=. uv run python -m search.experiments.e016.run_fw --p 0.002 --decoders bposd,relay_s --sub 0.01 --pbo 0.25 --tlim 120 --batch 200 --workers $W "$@"; }
run --w 18 --n 12000
run --w 12 --n 4000
PYTHONPATH=. uv run python -m search.experiments.e016.rejoint --prior 0.002 --sub 0.05 --wmax 48 --workers $W
echo STAGE2DONE
