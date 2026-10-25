#!/bin/zsh
# E-038 LER queue (1 worker): circuit basis scale
cd "$(dirname $0)/../../.."
for j in "kunlun Z 1.0" "search/experiments/e038/bb18_n8_d4_spec.json Z 1.0" "kunlun X 1.0" "search/experiments/e038/bb18_n8_d4_spec.json X 1.0" \
         "kunlun Z 0.1" "search/experiments/e038/bb18_n8_d4_spec.json Z 0.1" "kunlun X 0.1" "search/experiments/e038/bb18_n8_d4_spec.json X 0.1"; do
  set -- ${=j}
  PYTHONPATH=.:tests uv run python -m search.experiments.e038.ler $1 $2 $3
done
