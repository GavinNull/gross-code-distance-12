#!/bin/sh
# E-034 lift certificates (drat-trim + cake_lpr).  sh search/experiments/e034/run_lift.sh A|B
set -u
cd "$(dirname "$0")/../../.."
L="env PYTHONPATH=.:tests uv run python search/experiments/e034/liftsel.py"
O=results/E-034-veripb3-u11/lift
OR=A1A2A3B2B1B3
case "$1" in
A)  # c11: R 20-25 (any-R bound R'_9 = 25, E-030); then cake_lpr for the E-031 batches checked by drat-trim only
  $L e028 search/experiments/e030/c11_spec.json $OR $OR 20-25 $O/c11
  $L e028 search/experiments/e030/c11_spec.json $OR $OR 13-19 $O/c11_cake --only results/E-031-xor-certificates/lift/c11/results.jsonl ;;
B)  # c13, c12: R' <= 12 (E-028 / E-030)
  $L e028 search/experiments/e030/c13_spec.json $OR $OR 1-12 $O/c13
  $L e028 search/experiments/e030/c12_spec.json $OR $OR 1-12 $O/c12 ;;
esac
