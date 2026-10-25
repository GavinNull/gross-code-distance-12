#!/bin/zsh
# E-036 LER queue (3 workers): variant circuit basis scale
cd "$(dirname $0)/../../.."
jobs=(
"q1863 kunlun Z 1.0" "q1863 kunlun X 1.0" "q1863 search/experiments/e036/q1863_p8_spec.json Z 1.0" "q1863 search/experiments/e036/q1863_p8_spec.json X 1.0"
"bb18 kunlun Z 1.0" "bb18 kunlun X 1.0" "bb18 search/experiments/e036/bb18_p8_d3_spec.json Z 1.0" "bb18 search/experiments/e036/bb18_p8_d3_spec.json X 1.0"
"q1863 kunlun Z 0.1" "q1863 kunlun X 0.1" "q1863 search/experiments/e036/q1863_p8_spec.json Z 0.1" "q1863 search/experiments/e036/q1863_p8_spec.json X 0.1"
"bb18 kunlun Z 0.1" "bb18 kunlun X 0.1" "bb18 search/experiments/e036/bb18_p8_d3_spec.json Z 0.1" "bb18 search/experiments/e036/bb18_p8_d3_spec.json X 0.1"
)
printf '%s\n' "${jobs[@]}" | xargs -P 3 -I{} zsh -c 'set -- ${=1}; PYTHONPATH=.:tests uv run python -m search.experiments.e036.ler $1 $2 $3 --scale $4 --R 6 --shots 200000' _ {}
