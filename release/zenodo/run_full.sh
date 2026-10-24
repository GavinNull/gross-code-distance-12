#!/bin/sh
# Full reproduction of the computer-checked statements of the paper (P parallel processes).  CPU times on the
# reference machine (section 6 of README.md):
#   period-11 circuits (Theorems 1 and 2): circuit checks; extended lift u11 R = 1..31, c11 R = 1..25, c12 / c13
#     R = 1..12, both bases, with the controls; any-R premises (insertion checked for R = 2..16 / 2..15); injections;
#     direct DEM search (second implementation) u11 R = 1, both bases, and the period-10 control;
#     logical-error-rate tables, every sampled task rebuilt (sinter task hash = record)          (about 4 CPU h)
#   version 1 part: d_ext = 11 and the 4224 list of Fig. 12 (code/dext); lift for circuits A (R <= 32), B (R <= 24),
#     C (R <= 14, 16), both bases, Fig. 12 control; premises; upper bound; witnesses; certificates re-solved;
#     [[90,8,10]] c16 (lists, lift R <= 12, premises, injection, d_ext <= 8 CNF); direct DEM search (ccsearch)
#                                                                                                (about 5.5 CPU h)
#   with the proof tools (skipped with NO_PROOFS=1; code/proofs/build_tools.sh is run if CADICAL / DRAT_TRIM are not
#     found): every shipped DRAT proof checked, the large ones regenerated, the lift batches of A, B, C and the
#     extended-lift batches of u11, c11, c12, c13, c16 regenerated (CNF sha256 = record), refuted and checked by
#     drat-trim and cake_lpr                                                                     (about 12 + 25 CPU h)
#   with VeriPB (VERIPB; skipped with NO_VERIPB=1): every VeriPB certificate regenerated, checked and compared with its
#     hash, except the two weight-11 u11 certificates unless VERIPB_ALL=1 (about 18 CPU h more, 18-40 GB of memory)
#                                                                                                (about 3.5 CPU h)
# Usage: P=4 sh run_full.sh       (PYTHON = interpreter of the environment with requirements.txt; default python)
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python}; P=${P:-4}
export CADICAL=${CADICAL:-tools/cadical/build/cadical} DRAT_TRIM=${DRAT_TRIM:-tools/drat-trim/drat-trim}
export CAKE_LPR=${CAKE_LPR:-tools/cake_lpr/cake_lpr} VERIPB=${VERIPB:-tools/veripb/target/release/veripb}
OUT=${OUT:-full_run}; mkdir -p "$OUT"
FAIL=0
run() { echo "== $*"; "$PYTHON" "$@" || FAIL=1; }
run code/check_circuits.py A B C fig12
run code/premises.py --circuit A --rmax 32
run code/premises.py --circuit B --slab
run code/premises.py --circuit C --separated --rmax 14
run code/inject_upper_bound.py A B C
run code/bb90/check_circuits.py c16 u16 s16
run code/bb90/premises.py --rmax 14
run code/bb90/inject_upper_bound.py c16
run code/bb90/lists.py --wmax 9
run code/bb90/dext_free.py "$OUT/bb90_X_side.cnf" --compare certificates/bb90_dext_free/X_side.cnf.gz
# lift jobs in parallel (one per line: circuit basis R-range)
{ for b in Z X; do echo "A $b 1-16"; echo "A $b 17-24"; echo "A $b 25-28"; echo "A $b 29-32"
                   echo "B $b 1-16"; echo "B $b 17-24"; echo "C $b 1-14,16"; echo "fig12 $b 1-3"; done; } \
  | xargs -P "$P" -L 1 sh -c '"$0" code/lift.py --circuit $1 --basis $2 --R $3 > "$4/lift_$1_$2_$3.log" 2>&1' "$PYTHON" "$OUT"
# [[90,8,10]] extended lift (one per line: circuit basis R-range)
{ for b in Z X; do echo "c16 $b 1-8"; echo "c16 $b 9-12"; echo "u16 $b 1-2"; echo "s16 $b 1-2"; done; } \
  | xargs -P "$P" -L 1 sh -c '"$0" code/bb90/lift.py --circuit $1 --basis $2 --R $3 > "$4/lift_bb90_$1_$2_$3.log" 2>&1' "$PYTHON" "$OUT"
for f in "$OUT"/lift_*.log; do grep -E '^(PASS|FAIL)' "$f"; grep -q '^FAIL' "$f" && FAIL=1; grep -q '^PASS' "$f" || FAIL=1; done
run code/verify_witnesses.py
run code/check_certificates.py --family
run code/check_uniqueness_witnesses.py
for j in "primary 8" "primary 12" "primary 20 --common-frame" "second 8" "second 12" "second 9 --sub 1,2"; do
  run code/sat/regenerate.py $j
done
for n in $("$PYTHON" code/sat/len2only.py list); do run code/sat/len2only.py "$n"; done
run code/compare_lifts.py
run code/p8_family.py enumerate
run code/p8_family.py encoding
run code/p8_family.py check
run code/sat/completeness_sample.py check
run code/sat/soundness.py 17 0 60 15
run code/sat/soundness.py 17 0 4 4 all
run code/dcirc/run.py full --workers "$P" --out "$OUT/dcirc"
echo "== d_ext searches"; OUT="$OUT/dext" P="$P" PYTHON="$PYTHON" sh code/dext/run_dext.sh both || FAIL=1
if [ "${NO_PROOFS:-0}" != 1 ]; then
  echo "== DRAT proofs"
  { [ -x "$CADICAL" ] && [ -x "$DRAT_TRIM" ]; } || sh code/proofs/build_tools.sh || FAIL=1
  run code/proofs/check_proofs.py
  run code/proofs/check_proofs.py --regenerate unshipped
  run code/proofs/lift_control.py fig12 Z 1
  run code/proofs/lift_control.py fig12 X 1
  run code/proofs/check_proofs.py --records certificates/proofs/bb90_dext_free.jsonl --regenerate all --timeout 20000
  /bin/rm -rf "$OUT/proofs_lift_A" "$OUT/proofs_lift_B" "$OUT/proofs_lift_C"
  run code/proofs/run_lift_certs.py A 1-32 "$OUT/proofs_lift_A" --workers "$P" --compare certificates/proofs/lift_circuit_A.jsonl
  run code/proofs/run_lift_certs.py B 1-24 "$OUT/proofs_lift_B" --workers "$P" --compare certificates/proofs/lift_circuit_B.jsonl
  run code/proofs/run_lift_certs.py C 1-14,16 "$OUT/proofs_lift_C" --workers "$P" --compare certificates/proofs/lift_circuit_C.jsonl
fi
# ---- period-11 circuits
run code/p11/check_circuits.py u11 u11_control_p10 u11_control_segmented c11 c12 c13 c16
{ for b in Z X; do echo "u11 $b 1-16"; echo "u11 $b 17-24"; echo "u11 $b 25-28"; echo "u11 $b 29-31"
                   echo "c11 $b 1-14"; echo "c11 $b 15-20"; echo "c11 $b 21-25"; echo "c12 $b 1-12"; echo "c13 $b 1-12"
                   echo "u11_control_p10 $b 1-2"; echo "u11_control_segmented $b 1-2"; done; } \
  | xargs -P "$P" -L 1 sh -c '"$0" code/p11/lift.py --circuit $1 --basis $2 --R $3 > "$4/lift_p11_$1_$2_$3.log" 2>&1' "$PYTHON" "$OUT"
for f in "$OUT"/lift_p11_*.log; do grep -E '^(PASS|FAIL)' "$f"; grep -q '^FAIL' "$f" && FAIL=1; grep -q '^PASS' "$f" || FAIL=1; done
run code/p11/premises.py --circuit u11 --rmax 31 --rins 2-16
run code/p11/premises.py --circuit c11 --rmax 25 --rins 2-15
run code/p11/premises.py --circuit c12 --separated --rmax 12 --rins 2-12
run code/p11/premises.py --circuit c13 --separated --rmax 12 --rins 2-12
run code/p11/inject_upper_bound.py u11 c11 c12 c13
run code/p11/direct.py selftest --out "$OUT/p11_direct"
run code/p11/direct.py run u11 Z 1 11 --workers "$P" --out "$OUT/p11_direct"
run code/p11/direct.py run u11 X 1 11 --workers "$P" --out "$OUT/p11_direct"
run code/p11/direct.py run u11_control_p10 Z 1 11 --workers "$P" --out "$OUT/p11_direct"
run code/veripb/check_opb.py
run code/veripb/certify.py opb all --out "$OUT/veripb"
run code/ler/tables.py
if "$PYTHON" -c "import sinter, stimbposd, relay_bp" 2> /dev/null; then
  run code/ler/tables.py --verify-circuits 0
  run code/ler/sample_one.py --workers "$P"
else
  echo "SKIP  logical-error-rate sampling: optional dependencies not installed (requirements-ler.txt)"
fi
if [ "${NO_PROOFS:-0}" != 1 ]; then
  for c in "u11 1-31" "c11 1-25" "c12 1-12" "c13 1-12" "c16 1-12"; do
    set -- $c
    /bin/rm -rf "$OUT/ext_lift_$1"
    run code/proofs/ext_lift_certs.py $1 $2 "$OUT/ext_lift_$1" --workers "$P"
  done
  run code/proofs/ext_lift_certs.py u11_control_p10 1 "$OUT/ext_lift_controls" --expect sat
  run code/proofs/ext_lift_certs.py shipped "$OUT/ext_lift_shipped"
fi
if [ "${NO_VERIPB:-0}" != 1 ] && [ -x "$VERIPB" ]; then
  if [ "${VERIPB_ALL:-0}" = 1 ]; then run code/veripb/certify.py check all --out "$OUT/veripb"
  else run code/veripb/certify.py check --max-nodes 1e9 --out "$OUT/veripb"; fi
elif [ "${NO_VERIPB:-0}" != 1 ]; then
  echo "SKIP  VeriPB certificates: VeriPB not found (sh code/veripb/build_veripb.sh, or set VERIPB)"
fi
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME CHECKS FAILED"; exit 1; }
