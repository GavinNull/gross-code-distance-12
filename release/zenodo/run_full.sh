#!/bin/sh
# Full reproduction of the computer-checked statements of the paper (about 4 CPU hours; P parallel processes).
#   d_ext = 11 and the complete list of 4224 weight-11 extended logicals per basis      (code/dext, ~1.3 CPU h)
#   Lemma 2: lift R = 1..32 for circuit A, R = 1..24 for B, R = 1..14 and 16 for C, both bases; Fig. 12 control
#   Lemma 3 premises (A: gap argument; B: slab premise; C: round separation); upper bound; witnesses; certificates
# Usage: P=4 sh run_full.sh       (PYTHON = interpreter of the environment with requirements.txt; default python)
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python}; P=${P:-4}
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
run code/compare_lifts.py
run code/p8_family.py enumerate
run code/p8_family.py encoding
run code/p8_family.py check
run code/sat/soundness.py 17 0 60 15
run code/sat/soundness.py 17 0 4 4 all
echo "== d_ext searches"; OUT="$OUT/dext" P="$P" PYTHON="$PYTHON" sh code/dext/run_dext.sh both || FAIL=1
[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME CHECKS FAILED"; exit 1; }
