#!/bin/sh
# E-034: W = 11 certificate with the bounded parity-clause cache (pbdfs -F 1000000), used for kind X after the first
# attempt was stopped (VeriPB footprint 67 GB).  sh search/experiments/e034/run_u11_F.sh <kind>
set -u
cd "$(dirname "$0")/../../.."
U=results/E-034-veripb3-u11/u11
LU=results/E-031-xor-certificates/u11
k=$1
uv run python search/experiments/e034/certify3.py u11_${k}_W11_lists_F1M u11 $k 11 --out $U --stream --cachemax 1000000 \
  --blocks $LU/u11_${k}_w10.json $LU/u11_${k}_w11.json
