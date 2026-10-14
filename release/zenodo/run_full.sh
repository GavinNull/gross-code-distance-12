#!/bin/sh
# Full reproduction of the computer-checked statements of the paper (about 4 CPU hours; P parallel processes).
#   d_ext = 11 and the complete list of 4224 weight-11 extended logicals per basis      (code/dext, ~1.3 CPU h)
#   Lemma 2: lift R = 1..32 for circuit A, R = 1..24 for B, R = 1..14 and 16 for C, both bases; Fig. 12 control
#   Lemma 3 premises (A: gap argument; B: slab premise; C: round separation); upper bound; witnesses; certificates
#   DRAT proofs (about 12 more CPU hours; skipped with NO_PROOFS=1; builds the tools with code/proofs/build_tools.sh,
#   which downloads CaDiCaL, drat-trim and cake_lpr from their official repositories, unless CADICAL / DRAT_TRIM point
#   to existing binaries): every shipped proof checked with drat-trim, the 14 proofs over 100 MB regenerated and
#   checked, and the Lemma 2 lift batches of circuits A (R <= 32), B (R <= 24), C (R <= 14, 16) refuted with DRAT
#   proofs checked by drat-trim (LRAT core by cake_lpr when built), with the CNF sha256 compared to the records.
# Usage: P=4 sh run_full.sh       (PYTHON = interpreter of the environment with requirements.txt; default python)
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python}; P=${P:-4}
export CADICAL=${CADICAL:-tools/cadical/build/cadical} DRAT_TRIM=${DRAT_TRIM:-tools/drat-trim/drat-trim}
export CAKE_LPR=${CAKE_LPR:-tools/cake_lpr/cake_lpr}
OUT=${OUT:-full_run}; mkdir -p "$OUT"
FAIL=0
run() { echo "== $*"; "$PYTHON" "$@" || FAIL=1; }
run code/check_circuits.py A B C fig12
run code/premises.py --circuit A --rmax 32
run code/premises.py --circuit B --slab
run code/premises.py --circuit C --separated --rmax 14
run code/inject_upper_bound.py A B C
# lift jobs in parallel (one per line: circuit basis R-range)
{ for b in Z X; do echo "A $b 1-16"; echo "A $b 17-24"; echo "A $b 25-28"; echo "A $b 29-32"
                   echo "B $b 1-16"; echo "B $b 17-24"; echo "C $b 1-14,16"; echo "fig12 $b 1-3"; done; } \
  | xargs -P "$P" -L 1 sh -c '"$0" code/lift.py --circuit $1 --basis $2 --R $3 > "$4/lift_$1_$2_$3.log" 2>&1' "$PYTHON" "$OUT"
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
echo "== d_ext searches"; OUT="$OUT/dext" P="$P" PYTHON="$PYTHON" sh code/dext/run_dext.sh both || FAIL=1
if [ "${NO_PROOFS:-0}" != 1 ]; then
  echo "== DRAT proofs"
  { [ -x "$CADICAL" ] && [ -x "$DRAT_TRIM" ]; } || sh code/proofs/build_tools.sh || FAIL=1
  run code/proofs/check_proofs.py
  run code/proofs/check_proofs.py --regenerate unshipped
  run code/proofs/lift_control.py fig12 Z 1
  run code/proofs/lift_control.py fig12 X 1
  /bin/rm -rf "$OUT/proofs_lift_A" "$OUT/proofs_lift_B" "$OUT/proofs_lift_C"
  run code/proofs/run_lift_certs.py A 1-32 "$OUT/proofs_lift_A" --workers "$P" --compare certificates/proofs/lift_circuit_A.jsonl
  run code/proofs/run_lift_certs.py B 1-24 "$OUT/proofs_lift_B" --workers "$P" --compare certificates/proofs/lift_circuit_B.jsonl
  run code/proofs/run_lift_certs.py C 1-14,16 "$OUT/proofs_lift_C" --workers "$P" --compare certificates/proofs/lift_circuit_C.jsonl
fi
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME CHECKS FAILED"; exit 1; }
