#!/bin/sh
# E-031 part 2 (u11 extended code, E-032).  sh search/experiments/e031/run_u11.sh <step> <kind>
set -u
cd "$(dirname "$0")/../../.."
C="uv run python search/experiments/e031/certify.py"
R=results/E-031-xor-certificates
U=$R/u11
BIN=$R/bin/pbdfs
B="uv run python search/experiments/e031/build.py"
k=$2
case "$1" in
export) uv run python search/experiments/e031/u11.py export $k $U ;;
models)
  $B u11 $k 10 $U/models_${k}_W10 > /dev/null; uv run python search/experiments/e031/aux_checks.py models $U/models_${k}_W10 $U/u11_${k}_w10.json
  $B u11 $k 11 $U/models_${k}_W11 > /dev/null; uv run python search/experiments/e031/aux_checks.py models $U/models_${k}_W11 $U/u11_${k}_w10.json $U/u11_${k}_w11.json ;;
count)   # count-only (no proof) cost estimate
  mkdir -p $U/counts
  $B u11 $k 9 $U/counts/u11_${k}_W9 > /dev/null; /usr/bin/time -p $BIN $U/counts/u11_${k}_W9.inst > $U/counts/u11_${k}_W9.log 2>&1
  $B u11 $k 10 $U/counts/u11_${k}_W10 --blocks $U/u11_${k}_w10.json > /dev/null; /usr/bin/time -p $BIN $U/counts/u11_${k}_W10.inst > $U/counts/u11_${k}_W10.log 2>&1 ;;
count11)
  $B u11 $k 11 $U/counts/u11_${k}_W11 --blocks $U/u11_${k}_w10.json $U/u11_${k}_w11.json > /dev/null; /usr/bin/time -p $BIN $U/counts/u11_${k}_W11.inst > $U/counts/u11_${k}_W11.log 2>&1 ;;
planted)
  $B u11 $k 11 $U/counts/u11_${k}_W11_drop0 --blocks $U/u11_${k}_w10.json $U/u11_${k}_w11.json --drop-block 200 > $U/counts/u11_${k}_W11_drop0.build.log
  $BIN $U/counts/u11_${k}_W11_drop0.inst -n 400000000 > $U/counts/u11_${k}_W11_drop0.log 2>&1
  $B u11 $k 10 $U/counts/u11_${k}_W10_drop0 --blocks $U/u11_${k}_w10.json --drop-block 0 > $U/counts/u11_${k}_W10_drop0.build.log
  $BIN $U/counts/u11_${k}_W10_drop0.inst -n 400000000 > $U/counts/u11_${k}_W10_drop0.log 2>&1 ;;
cert9)  $C u11_${k}_W9 u11 $k 9 --out $U ;;
cert10) $C u11_${k}_W10_list u11 $k 10 --out $U --blocks $U/u11_${k}_w10.json ;;
cert11) $C u11_${k}_W11_lists u11 $k 11 --out $U --blocks $U/u11_${k}_w10.json $U/u11_${k}_w11.json ;;
esac
