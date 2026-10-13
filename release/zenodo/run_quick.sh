#!/bin/sh
# Quick reproduction (about 6 CPU minutes): circuit checks, lift R = 1..3 (circuit A, both bases) with the Fig. 12
# positive control, gap-argument premises, weight-12 injection, a sample of the weight-11 witnesses and of the
# certificates, byte-identical regeneration of two certificates, three lift implementations compared at R = 1,
# the uniqueness witnesses and the P = 8 enumeration.  Every check prints PASS or FAIL; the last line is ALL PASS or
# SOME CHECKS FAILED.
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
run code/verify_witnesses.py --max-per-case 10 --max-cases 60
run code/check_certificates.py --max-clauses 45000
run code/sat/regenerate.py primary 8
run code/sat/regenerate.py second 10
run code/compare_lifts.py --circuit A fig12 --R 1 --methods cpsat dp mitm
run code/check_uniqueness_witnesses.py
run code/p8_family.py enumerate
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME CHECKS FAILED"; exit 1; }
