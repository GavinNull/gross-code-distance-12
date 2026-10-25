#!/bin/zsh
# BP iteration sensitivity: same samples (same seed), 100 vs 10^4 iterations
cd "$(dirname $0)/../../.."
for v in "bb18 kunlun" "bb18 bb18_p8_d3" "q1863 kunlun" "q1863 q1863_p8"; do
  for it in 100 10000; do
    uv run python -m search.experiments.e036_audit.a5_ler ${=v} Z --scale 1.0 --shots 1500 --seed 99 --iters $it
    uv run python -m search.experiments.e036_audit.a5_ler ${=v} Z --scale 0.1 --shots 20000 --seed 98 --iters $it
  done
done
