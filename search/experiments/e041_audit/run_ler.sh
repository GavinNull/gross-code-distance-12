#!/bin/zsh
# c5 LER queue, one worker per call: argument = queue index 0..2.  Seeds 20261101 + offsets (fresh).
cd "$(dirname $0)/../../.."
q0=("kunlun Z 1.0 kl 100000 20261101" "kunlun X 1.0 kl 100000 20261102" "kunlun Z 0.1 kl 400000 20261103" "kunlun X 0.1 kl 400000 20261104")
q1=("w9 Z 1.0 kl 100000 20261111" "w9 X 1.0 kl 100000 20261112" "w9 Z 0.1 kl 400000 20261113" "w9 X 0.1 kl 400000 20261114")
q2=("w9 Z 1.0 mix 100000 20261121" "w9 X 1.0 mix 100000 20261122" "w9 Z 0.1 mix 400000 20261123" "w9 X 0.1 mix 400000 20261124")
case $1 in 0) Q=("${q0[@]}");; 1) Q=("${q1[@]}");; 2) Q=("${q2[@]}");; esac
for j in "${Q[@]}"; do
  set -- ${=j}
  PYTHONPATH=.:tests uv run python -m search.experiments.e041_audit.c5_ler $1 $2 $3 $4 $5 $6
done
