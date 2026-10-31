#!/bin/zsh
# E-041 LER queue: one worker per call; argument = queue index (0 or 1)
cd "$(dirname $0)/../../.."
W9=search/experiments/e041/bb18_w9_d4_spec.json
N8=search/experiments/e038/bb18_n8_d4_spec.json
q0=("$W9 Z 1.0 klmix" "$W9 X 1.0 klmix" "$W9 Z 0.1 klmix" "$W9 X 0.1 klmix" "kunlun Z 1.0 kl" "kunlun X 1.0 kl" "kunlun Z 0.1 kl" "kunlun X 0.1 kl")
q1=("$W9 Z 1.0 kl" "$W9 X 1.0 kl" "$W9 Z 0.1 kl" "$W9 X 0.1 kl" "$N8 Z 1.0 kl" "$N8 X 1.0 kl" "$N8 Z 0.1 kl" "$N8 X 0.1 kl")
if [ "$1" = 0 ]; then Q=("${q0[@]}"); else Q=("${q1[@]}"); fi
for j in "${Q[@]}"; do
  set -- ${=j}
  PYTHONPATH=.:tests uv run python -m search.experiments.e041.ler $1 $2 $3 $4
done
