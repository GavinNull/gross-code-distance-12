#!/bin/sh
# Quick reproduction (about 7 CPU minutes): circuit checks, lift R = 1..3 (circuit A, both bases) with the Fig. 12
# positive control, gap-argument premises, weight-12 injection, a sample of the weight-11 witnesses and of the
# certificates, byte-identical regeneration of two certificates, three lift implementations compared at R = 1,
# the uniqueness witnesses and the P = 8 enumeration; for the [[90,8,10]] circuit c16: circuit checks, d_ext = 8 and
# the weight-8 list (MITM), the extended lift R = 1, 2 (cases a and b) with the u16 / s16 controls, the any-R premises,
# the weight-10 injection; the direct DEM search (ccsearch: selftest, c16 and u16 at R = 1);
# if the proof tools are built (sh code/proofs/build_tools.sh),
# also drat-trim checks of the shipped DRAT proofs below 2 MB and DRAT-checked lift batches of circuit A for R = 1, 2.
# Every check prints PASS or FAIL; the last line is ALL PASS or SOME CHECKS FAILED.
# Usage: sh run_quick.sh      (PYTHON = interpreter of the environment with requirements.txt; default python)
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python}
export CADICAL=${CADICAL:-tools/cadical/build/cadical} DRAT_TRIM=${DRAT_TRIM:-tools/drat-trim/drat-trim}
export CAKE_LPR=${CAKE_LPR:-tools/cake_lpr/cake_lpr}
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
run code/sat/len2only.py primary_P10_pipelined
run code/compare_lifts.py --circuit A fig12 --R 1 --methods cpsat dp mitm
run code/check_uniqueness_witnesses.py
run code/p8_family.py enumerate
run code/bb90/check_circuits.py c16 u16 s16
run code/bb90/lists.py --wmax 8
run code/bb90/lift.py --circuit c16 --basis Z X --R 1-2
run code/bb90/lift.py --circuit u16 --basis Z --R 1
run code/bb90/lift.py --circuit s16 --basis Z --R 1
run code/bb90/premises.py --rmax 8
run code/bb90/inject_upper_bound.py c16
/bin/rm -rf dcirc_run_quick
run code/dcirc/run.py quick --workers 1 --out dcirc_run_quick
if [ -x "$CADICAL" ] && [ -x "$DRAT_TRIM" ]; then
  [ -x "$CAKE_LPR" ] || echo "SKIP  cake_lpr not found: LRAT cores are not checked (recorded as \"not run\")"
  run code/proofs/check_proofs.py --max-bytes 2e6
  /bin/rm -rf proof_run_quick
  run code/proofs/run_lift_certs.py A 1-2 proof_run_quick --compare certificates/proofs/lift_circuit_A.jsonl
  run code/proofs/lift_control.py fig12 Z 1
else
  echo "SKIP  DRAT proof checks: proof tools not found (build them with: sh code/proofs/build_tools.sh)"
fi
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME CHECKS FAILED"; exit 1; }
