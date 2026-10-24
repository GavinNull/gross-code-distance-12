#!/bin/sh
# Quick reproduction (about 13 CPU minutes with all optional tools).
# Version 1 part (gross circuits A, B, C and Fig. 12; [[90,8,10]] c16): circuit checks, lift R = 1..3 (circuit A, both
# bases) with the Fig. 12 positive control, gap-argument premises, weight-12 injection, a sample of the weight-11
# witnesses and of the certificates, byte-identical regeneration of two certificates, three lift implementations
# compared at R = 1, the uniqueness witnesses and the P = 8 enumeration; c16: circuit checks, d_ext = 8 and the weight-8
# list (MITM), the extended lift R = 1, 2 with the u16 / s16 controls, the any-R premises, the weight-10 injection; the
# direct DEM search (ccsearch: selftest, c16 and u16 at R = 1).
# Period-11 part (Theorems 1 and 2): u11, its controls, c11, c12, c13: circuit checks (timing of Table I,
# non-segmentability), extended lift R = 1, 2 with the positive controls, any-R premises (insertion checked for
# R = 2..4), the upper-bound injections, the selftest of the second direct search; the VeriPB part: semantic check of
# every shipped OPB file and rebuild of three of them from the data files; with VeriPB (code/veripb/build_veripb.sh):
# the six smallest VeriPB certificates regenerated, checked and compared with their recorded hash; with the proof tools
# (code/proofs/build_tools.sh): drat-trim checks of the shipped DRAT proofs below 2 MB, DRAT-checked lift batches of
# circuit A (R = 1, 2) and of u11 (R = 1, CNF sha256 = record), the shipped extended-lift proofs; the logical-error-rate
# tables recomputed from the shipped statistics; with requirements-ler.txt also six sampled tasks rebuilt (sinter task
# hash = record) and one ratio re-sampled (code/ler/sample_one.py, about 3 CPU minutes).
# Every check prints PASS or FAIL (SKIP: optional tool absent); the last line is ALL PASS or SOME CHECKS FAILED.
# Usage: sh run_quick.sh      (PYTHON = interpreter of the environment with requirements.txt; default python)
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python}
export CADICAL=${CADICAL:-tools/cadical/build/cadical} DRAT_TRIM=${DRAT_TRIM:-tools/drat-trim/drat-trim}
export CAKE_LPR=${CAKE_LPR:-tools/cake_lpr/cake_lpr} VERIPB=${VERIPB:-tools/veripb/target/release/veripb}
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
# ---- period-11 circuits (Theorems 1 and 2)
run code/p11/check_circuits.py u11 u11_control_p10 u11_control_segmented c11 c12 c13
run code/p11/lift.py --circuit u11 --basis Z X --R 1-2
run code/p11/lift.py --circuit u11_control_p10 --basis Z X --R 1
run code/p11/lift.py --circuit u11_control_segmented --basis Z --R 1
run code/p11/lift.py --circuit c11 --basis Z X --R 1-2
run code/p11/lift.py --circuit c12 --basis Z X --R 1
run code/p11/premises.py --circuit u11 --rins 2-4
run code/p11/premises.py --circuit c11 --rins 2-4
run code/p11/premises.py --circuit c12 --separated --rins 2-4
run code/p11/inject_upper_bound.py u11 c11 c12 c13 --R 1,2,3
/bin/rm -rf p11_direct_run_quick
run code/p11/direct.py selftest --out p11_direct_run_quick
# ---- certificates of the period-11 proofs
run code/veripb/check_opb.py
/bin/rm -rf veripb_run_quick
run code/veripb/certify.py opb bb90_Z_W7 bb90_X_W8 u11_Z_W10 --out veripb_run_quick
if [ -x "$VERIPB" ]; then
  run code/veripb/certify.py check --max-nodes 1e6 --out veripb_run_quick
else
  echo "SKIP  VeriPB checks: VeriPB not found (build it with: sh code/veripb/build_veripb.sh, or set VERIPB)"
fi
if [ -x "$CADICAL" ] && [ -x "$DRAT_TRIM" ]; then
  /bin/rm -rf ext_lift_run_quick
  run code/proofs/ext_lift_certs.py u11 1 ext_lift_run_quick
  run code/proofs/ext_lift_certs.py shipped ext_lift_run_quick
else
  echo "SKIP  extended-lift DRAT checks: proof tools not found"
fi
# ---- logical error rates
run code/ler/tables.py
if "$PYTHON" -c "import sinter, stimbposd, relay_bp" 2> /dev/null; then
  run code/ler/tables.py --verify-circuits 2
  run code/ler/sample_one.py --workers 2
else
  echo "SKIP  logical-error-rate sampling: optional dependencies not installed (requirements-ler.txt)"
fi
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME CHECKS FAILED"; exit 1; }
