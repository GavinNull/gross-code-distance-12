#!/bin/sh
# E-031 part 3: DRAT certificates of the extended lift (sh search/experiments/e031/run_lift.sh)
set -u
cd "$(dirname "$0")/../../.."
L="env PYTHONPATH=.:tests uv run python search/experiments/e031/liftcert.py"
O=results/E-031-xor-certificates/lift
# positive controls (must be SAT): [[90]] u16 (d_circ = 9, E-028), gross ctl_p10 (E-032 control, weight-11 lifts)
$L e028 search/experiments/e028/u16_spec.json A1A2A3B2B1B3 A1A2A3B2B1B3 1 $O/control --expect sat
$L e032 search/experiments/e032/ctl_p10_spec.json A1A2A3B3B1B2 A1A2A3B3B1B2 1 $O/control --expect sat
# u11: any-R bound R' = 31 (E-032);  [[90]]: c16, c13 R' <= 12 (E-028/E-030), c11 R' = 25 (E-030)
$L e032 search/experiments/e032/u11_spec.json A1A2A3B3B1B2 A1A2A3B3B1B2 1-31 $O/u11
$L e028 search/experiments/e028/c16_spec.json A1A2A3B2B1B3 A1A2A3B2B1B3 1-12 $O/c16
# not run (budget): $L e028 search/experiments/e030/c13_spec.json A1A2A3B2B1B3 A1A2A3B2B1B3 1-12 $O/c13
# run: R 1-13 with cake_lpr, R 13-19 with --no-cake (drat-trim only), R 20-25 not run (budget)
$L e028 search/experiments/e030/c11_spec.json A1A2A3B2B1B3 A1A2A3B2B1B3 1-12 $O/c11
$L e028 search/experiments/e030/c11_spec.json A1A2A3B2B1B3 A1A2A3B2B1B3 13-19 $O/c11 --no-cake
