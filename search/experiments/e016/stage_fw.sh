#!/bin/bash
# E-016 阶段 C：固定权重（解码器先验 p=2e-3），BP-OSD + 分 sector Relay5，MLE 触发：Relay 失败必跑、仅 BP-OSD 失败 25%、其余 1%。
set -e
cd "$(dirname "$0")/../../.."
W=${WORKERS:-3}
run() { PYTHONPATH=. uv run python -m search.experiments.e016.run_fw --p 0.002 --decoders bposd,relay_s --sub 0.01 --pbo 0.25 --tlim 120 --batch 100 --workers $W "$@"; }
run --w 24 --n 3000
run --w 30 --n 2000
run --w 36 --n 1500
run --w 42 --n 1000
run --w 48 --n 600
run --w 56 --n 400
echo STAGEDONE
