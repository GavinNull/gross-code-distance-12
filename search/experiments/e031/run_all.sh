#!/bin/sh
# E-031 full run list (each line is independent; results appended to results/E-031-xor-certificates/<group>/runs.jsonl)
#   sh search/experiments/e031/run_all.sh [group]
set -u
cd "$(dirname "$0")/../../.."
C="uv run python search/experiments/e031/certify.py"
A="uv run python search/experiments/e031/aux_checks.py"
R=results/E-031-xor-certificates
LOG=release/zenodo/data/logicals
g=${1:-all}
if [ "$g" = validation2 ]; then
  O=$R/validation
  $C ibmgross_X_W7 ibm:gross X 7 --out $O
  $C ibmgross_X_W8 ibm:gross X 8 --out $O --expect sat
  $A tamper $O/bb72_Z_W4.opb $O/bb72_Z_W4.pbp.gz $O/tamper
  $C bb90_X_W8_drop0 bb90 X 8 --out $R/bb90 --blocks $LOG/bb90_weight8_logicals_X_memory.json --drop-block 0 --expect sat
fi
if [ "$g" = all ] || [ "$g" = validation ]; then
  O=$R/validation
  # known d_ext = 5 (E-015): IBM BB72 extended codes
  $C bb72_Z_W4 ibm:bb72 Z 4 --out $O --keep
  $C bb72_X_W4 ibm:bb72 X 4 --out $O
  $C bb72_Z_W4_nosym ibm:bb72 Z 4 --out $O --no-sym
  $C bb72_Z_W5 ibm:bb72 Z 5 --out $O --expect sat
  $C bb72_X_W5 ibm:bb72 X 5 --out $O --expect sat
  # planted: complete weight-5 list (untrusted enumeration), all blocked -> UNSAT; one orbit missing -> SAT
  $A enumerate ibm:bb72 Z 5 $O/bb72_Z_w5_list.json
  $C bb72_Z_W5_blockall ibm:bb72 Z 5 --out $O --blocks $O/bb72_Z_w5_list.json
  $C bb72_Z_W5_drop0 ibm:bb72 Z 5 --out $O --blocks $O/bb72_Z_w5_list.json --drop-block 0 --expect sat
  # tampering
  $A tamper $O/bb72_Z_W4.opb $O/bb72_Z_W4.pbp.gz $O/tamper
  # IBM gross: E-015 ibm_lower found W8 UNSAT for its kind "X" (= our basis Z: H = HZ, X-check orders) and a
  # weight-8 logical for its kind "Z" (= our basis X).  (The first run list used --expect sat for our Z by a
  # labelling slip; that run, ibmgross_Z_W8, is a VeriPB-verified UNSAT in agreement with E-015.)
  $C ibmgross_Z_W7 ibm:gross Z 7 --out $O
  $C ibmgross_Z_W8 ibm:gross Z 8 --out $O
  $C ibmgross_X_W7 ibm:gross X 7 --out $O
  $C ibmgross_X_W8 ibm:gross X 8 --out $O --expect sat
fi
if [ "$g" = all ] || [ "$g" = bb90 ] || [ "$g" = bb90all ]; then
  O=$R/bb90
  $C bb90_X_W7 bb90 X 7 --out $O
  $C bb90_Z_W7 bb90 Z 7 --out $O
fi
if [ "$g" = all ] || [ "$g" = bb90w8 ] || [ "$g" = bb90all ]; then
  O=$R/bb90
  $C bb90_X_W8_drop0 bb90 X 8 --out $O --blocks $LOG/bb90_weight8_logicals_X_memory.json --drop-block 0 --expect sat
  $C bb90_X_W8_list bb90 X 8 --out $O --blocks $LOG/bb90_weight8_logicals_X_memory.json
  $C bb90_Z_W8_list bb90 Z 8 --out $O --blocks $LOG/bb90_weight8_logicals_Z_memory.json
fi
if [ "$g" = all ] || [ "$g" = bb90w9X ]; then
  $C bb90_X_W9_lists bb90 X 9 --out $R/bb90 --blocks $LOG/bb90_weight8_logicals_X_memory.json $LOG/bb90_weight9_logicals_X_memory.json
fi
if [ "$g" = all ] || [ "$g" = bb90w9Z ]; then
  $C bb90_Z_W9_lists bb90 Z 9 --out $R/bb90 --blocks $LOG/bb90_weight8_logicals_Z_memory.json $LOG/bb90_weight9_logicals_Z_memory.json
fi
if [ "$g" = all ] || [ "$g" = gross ]; then
  O=$R/gross
  for W in 5 6 7 8; do
    $C gross_Z_W$W gross Z $W --out $O
    $C gross_X_W$W gross X $W --out $O
  done
fi
