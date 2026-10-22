#!/bin/sh
# E-034 u11 list completeness.  sh search/experiments/e034/run_u11.sh <step> <kind>
# Lists: E-031's conversion of the E-032 lists (results/E-031-xor-certificates/u11/u11_<kind>_w1{0,1}.json).
set -u
cd "$(dirname "$0")/../../.."
C="uv run python search/experiments/e034/certify3.py"
B="uv run python search/experiments/e031/build.py"
U=results/E-034-veripb3-u11/u11
LU=results/E-031-xor-certificates/u11
BIN=results/E-034-veripb3-u11/bin/pbdfs
k=$2
mkdir -p $U/counts
case "$1" in
count10)
  $B u11 $k 10 $U/counts/u11_${k}_W10 --blocks $LU/u11_${k}_w10.json > $U/counts/u11_${k}_W10.build.log
  /usr/bin/time -p $BIN $U/counts/u11_${k}_W10.inst > $U/counts/u11_${k}_W10.log 2>&1 ;;
count11)
  $B u11 $k 11 $U/counts/u11_${k}_W11 --blocks $LU/u11_${k}_w10.json $LU/u11_${k}_w11.json > $U/counts/u11_${k}_W11.build.log
  /usr/bin/time -p $BIN $U/counts/u11_${k}_W11.inst > $U/counts/u11_${k}_W11.log 2>&1 ;;
planted11)  # blocking test: drop the orbit of block #200 (a weight-11 logical) from the 144+7344 blocks; count only,
  # the search must stop with a logical of that orbit (node limit 4e8)
  $B u11 $k 11 $U/counts/u11_${k}_W11_drop200 --blocks $LU/u11_${k}_w10.json $LU/u11_${k}_w11.json --drop-block 200 > $U/counts/u11_${k}_W11_drop200.build.log
  /usr/bin/time -p $BIN $U/counts/u11_${k}_W11_drop200.inst -n 400000000 > $U/counts/u11_${k}_W11_drop200.log 2>&1 ;;
cert10) $C u11_${k}_W10_list u11 $k 10 --out $U --stream --blocks $LU/u11_${k}_w10.json ;;
cert11) $C u11_${k}_W11_lists u11 $k 11 --out $U --stream --blocks $LU/u11_${k}_w10.json $LU/u11_${k}_w11.json ;;
esac
