#!/bin/sh
# E-042 audit, item 3: regenerate the W=10 kind-X (Z-basis memory) VeriPB proof with my own build of the unmodified
# e034/pbdfs.c, from the OPB/.inst I regenerated with e042/pbbuild (sha256 = record), compare the gz sha256 with the
# record (13570e39...), then check it with VeriPB 3.0.2 (tools/veripb).  Verdict only by "s VERIFIED UNSATISFIABLE".
# Peak: pbdfs + gzip, then veripb alone.  Run from the repository root.
set -eu
O=results/E-042-audit
mkdir -p $O/bin $O/veripb
cc -O2 -Wall -o $O/bin/pbdfs search/experiments/e034/pbdfs.c
shasum -a 256 search/experiments/e034/pbdfs.c $O/bin/pbdfs tools/veripb/target/release/veripb > $O/veripb/binaries.sha256
I=$O/regen_opb/g10_X_W10
P=$O/veripb/g10_X_W10.pbp.gz
/usr/bin/time -p $O/bin/pbdfs $I.inst -p $P -F 1000000 > $O/veripb/search.log 2>&1
shasum -a 256 $P > $O/veripb/proof.sha256
ls -l $P >> $O/veripb/proof.sha256
/usr/bin/time -p tools/veripb/target/release/veripb --stats $I.opb $P > $O/veripb/veripb.log 2>&1 || true
grep -x "s VERIFIED UNSATISFIABLE" $O/veripb/veripb.log && echo VERDICT_OK >> $O/veripb/veripb.log
rm -f $P
echo done
