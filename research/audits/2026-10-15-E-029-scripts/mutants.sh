#!/bin/sh
# Auditor: mutation test of the adversarial harness (does it catch plausible bugs in ccsearch?)
SRC=search/experiments/e029/ccsearch.c; O=results/E-029-audit/mut
mk() { sed "$2" $SRC > $O/$1.c; cc -O2 -o $O/$1 $O/$1.c 2>/dev/null; }
mk m1_lb_plus1    's/return lb1 > lb2 ? lb1 : lb2;/return (lb1 > lb2 ? lb1 : lb2) + 1;/'
mk m2_no_restore  's/for (int i = 0; i < n; i++) setav(list\[i\], 1);/;/'
mk m3_orbit_gt    's/setav(c, orbof\[c\] >= o \&\& colW\[c\] > 0)/setav(c, orbof[c] > o \&\& colW[c] > 0)/'
mk m4_lookup_noav 's/if (c >= 0 \&\& isav(c)) {/if (c >= 0) {/'
mk m5_lb_ceil     's/int lb1 = (w + wmax - 1) \/ wmax;/int lb1 = (w + wmax - 2) \/ (wmax - 1);/'
mk m6_wmax_minus1 's/colW\[c\] = k; if (k > wmax) wmax = k;/colW[c] = k; if (k - 1 > wmax) wmax = k - 1;/'
mk m7_skip_last   's/for (int i = 0; i < n \&\& !stopflag; i++) {/for (int i = 0; i + 1 < n \&\& !stopflag; i++) {/'
for m in m1_lb_plus1 m2_no_restore m3_orbit_gt m4_lookup_noav m5_lb_ceil m6_wmax_minus1 m7_skip_last; do
  cmp -s $O/$m.c $SRC && echo "$m: SED DID NOT APPLY"
  r=$(uv run python research/audits/2026-10-15-E-029-scripts/advtest.py $O/$m results/E-029-audit/auditsearch 120 7 $O/mutinst hard 2>&1 | tail -1)
  echo "$m -> $r"
done
