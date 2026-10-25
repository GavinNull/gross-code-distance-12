#!/bin/sh
# E-037 checks: witnesses (task 3) at the certified R, ccsearch cross-check (task 4) at small R.
#   sh search/experiments/e037/run_checks.sh witness | cross
O=results/E-037-ibm-cert
case $1 in
witness)
  for s in "ibm:gross:X:12 10" "ibm:gross:Z:12 10" "sd6:gross:Z:12 10" "sd6:gross:X:12 10" \
           "ibm:bb108:X:10 8" "ibm:bb108:Z:10 8" "sd6:bb108:Z:10 8" "sd6:bb108:X:10 8"; do
    uv run python search/experiments/e037/witness.py $s $O/witness
  done ;;
cross)
  for s in "ibm:gross:X:1 10" "ibm:gross:Z:1 10" "sd6:gross:Z:1 10" "sd6:gross:X:1 10" "ibm:gross:X:2 10" "sd6:gross:Z:2 10" \
           "ibm:bb108:X:1 8" "ibm:bb108:Z:1 8" "sd6:bb108:Z:1 8" "sd6:bb108:X:1 8" "ibm:bb108:X:2 8"; do
    uv run python search/experiments/e037/crosscheck.py $s $O/crosscheck.jsonl
  done ;;
esac
