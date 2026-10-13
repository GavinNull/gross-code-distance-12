#!/bin/sh
# Quick reproduction (about 5 CPU minutes): circuit checks, lift R = 1..3 (circuit A, both bases) with the Fig. 12
# positive control, gap-argument premises, weight-12 injection, a sample of the weight-11 witnesses and of the
# certificates.  Every line starts with PASS or FAIL; the last line is ALL PASS or SOME CHECKS FAILED.
# Usage: sh run_quick.sh      (PYTHON = interpreter of the environment with requirements.txt; default python)
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python}
FAIL=0
run() { echo "== $*"; "$PYTHON" "$@" || FAIL=1; }
run code/check_circuits.py A fig12
run code/lift.py --circuit A --basis Z X --R 1-3
run code/lift.py --circuit fig12 --basis Z X --R 1
run code/premises.py --circuit A --rmax 32
run code/inject_upper_bound.py A
run code/verify_witnesses.py --max-per-case 10
run code/check_certificates.py --max-clauses 45000
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME CHECKS FAILED"; exit 1; }
