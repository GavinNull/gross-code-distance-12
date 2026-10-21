#!/bin/sh
# E-031 extra runs (separate file: run_all.sh is read incrementally by running shells, so it was not edited again)
#   sh search/experiments/e031/run_extra.sh validation2|counts
set -u
cd "$(dirname "$0")/../../.."
C="uv run python search/experiments/e031/certify.py"
A="uv run python search/experiments/e031/aux_checks.py"
R=results/E-031-xor-certificates
LOG=release/zenodo/data/logicals
BIN=$R/bin/pbdfs
case "$1" in
validation2)
  $A tamper $R/validation/bb72_Z_W4.opb $R/validation/bb72_Z_W4.pbp.gz $R/validation/tamper
  $C bb90_X_W8_drop0 bb90 X 8 --out $R/bb90 --blocks $LOG/bb90_weight8_logicals_X_memory.json --drop-block 0 --expect sat
  # planted on gross, count-only (a W=11 proof would be ~1e9 lines): must stop with a logical from the dropped orbit
  mkdir -p $R/counts
  uv run python search/experiments/e031/build.py gross Z 11 $R/counts/gross_Z_W11_drop0 --blocks $LOG/weight11_logicals_Z_memory.json --drop-block 0 > $R/counts/gross_Z_W11_drop0.build.log
  $BIN $R/counts/gross_Z_W11_drop0.inst -n 300000000 > $R/counts/gross_Z_W11_drop0.log 2>&1
  ;;
counts)
  # count-only (no proof): untrusted third implementation; measured node counts for the scaling estimate
  mkdir -p $R/counts
  for b in Z X; do
    uv run python search/experiments/e031/build.py gross $b 9 $R/counts/gross_${b}_W9 > /dev/null
    /usr/bin/time -p $BIN $R/counts/gross_${b}_W9.inst > $R/counts/gross_${b}_W9.log 2>&1
    uv run python search/experiments/e031/build.py gross $b 10 $R/counts/gross_${b}_W10 > /dev/null
    /usr/bin/time -p $BIN $R/counts/gross_${b}_W10.inst > $R/counts/gross_${b}_W10.log 2>&1
  done
  ;;
counts11)
  b=$2
  uv run python search/experiments/e031/build.py gross $b 11 $R/counts/gross_${b}_W11_lists --blocks $LOG/weight11_logicals_${b}_memory.json > /dev/null
  /usr/bin/time -p $BIN $R/counts/gross_${b}_W11_lists.inst > $R/counts/gross_${b}_W11_lists.log 2>&1
  ;;
esac
