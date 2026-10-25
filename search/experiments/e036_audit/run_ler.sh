#!/bin/zsh
# audit LER spot check: one process, sequential
cd "$(dirname $0)/../../.."
for sc in 1.0 0.1; do for v in "bb18 kunlun" "bb18 bb18_p8_d3" "q1863 kunlun" "q1863 q1863_p8"; do for b in Z X; do
  uv run python -m search.experiments.e036_audit.a5_ler ${=v} $b --scale $sc --shots 100000
done; done; done
