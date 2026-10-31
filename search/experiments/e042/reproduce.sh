#!/bin/sh
# E-042 reproduction: certificates for search/experiments/e040/g10_d12_spec.json (period-10 gross circuit).
#   sh search/experiments/e042/reproduce.sh rstar|lift|ctl|export|count KIND W|cert KIND W|planted KIND|all
# Needs: tools/veripb (VeriPB 3.0.2), tools/cadical, tools/drat-trim, tools/cake_lpr (tools/VERSIONS.txt);
# lists results/E-040-min-period/list{,11}_gross_{X,Z}_A1A2B1A3B2B3.pkl and the audit's
# results/E-040-audit-circ/list_g10_{Z,X}_w1{0,1}.pkl (cross-checked set-equal before use).
# Runs at most 2 heavy processes (a VeriPB stream = pbdfs + veripb).  Verdicts: VeriPB only by the output line
# "s VERIFIED UNSATISFIABLE"; drat-trim by "s VERIFIED"; cake_lpr by "s VERIFIED UNSAT".
set -eu
cd "$(dirname "$0")/../../.."
O=results/E-042-g10-cert
PB=$O/pb
L=$PB/lists   # list JSONs in a directory of their own (macOS names are case-insensitive: g10_X_w10.json = g10_X_W10.json)
mkdir -p $O/bin $PB/counts $PB/lists $PB/certs
[ -x $O/bin/pbdfs ] || cc -O2 -Wall -o $O/bin/pbdfs search/experiments/e034/pbdfs.c
blocks() {   # kind W -> block files
  if [ "$2" -ge 11 ]; then echo "$L/g10_$1_w10.json $L/g10_$1_w11.json"; else echo "$L/g10_$1_w10.json"; fi
}
case "$1" in
rstar)    # R* = 13, window conditions, existence conditions; model == DEM signature sets at R* (audited dem_check)
  uv run python -m search.experiments.e042.rstar > $O/rstar.json
  uv run python -m search.theory.B_audit.dem_check gross search/experiments/e040/g10_d12_spec.json 13 > $O/dem_check_R13.log ;;
lift)     # 2 x 125 batches, every list item, R = 13
  env PYTHONPATH=. uv run python -m search.experiments.e042.lift run 13 $O/lift/R13 > $O/lift/R13.log 2>&1
  uv run python -m search.experiments.e042.summarize lift $O/lift/R13/results.jsonl ;;
ctl)      # positive control: segmented timing, same orders: every batch SAT
  env PYTHONPATH=. uv run python -m search.experiments.e042.lift ctl 13 $O/lift/ctl > $O/lift/ctl.log 2>&1 ;;
export)
  for k in X Z; do uv run python -m search.experiments.e042.pbbuild export $k $L; done ;;
count)    # count-only search (no proof), kind W
  uv run python -m search.experiments.e042.pbbuild build $2 $3 $PB/counts/g10_$2_W$3 --blocks $(blocks $2 $3) > $PB/counts/g10_$2_W$3.build.log
  /usr/bin/time -p $O/bin/pbdfs $PB/counts/g10_$2_W$3.inst > $PB/counts/g10_$2_W$3.log 2>&1 ;;
planted)  # blocking test: drop the orbit of block #200 (weight 10); the search must stop inside that orbit
  uv run python -m search.experiments.e042.pbbuild build $2 10 $PB/counts/g10_$2_W10_drop200 --blocks $(blocks $2 10) --drop-block 200 > $PB/counts/g10_$2_W10_drop200.build.log
  /usr/bin/time -p $O/bin/pbdfs $PB/counts/g10_$2_W10_drop200.inst > $PB/counts/g10_$2_W10_drop200.log 2>&1 ;;
cert)     # VeriPB 3 certificate, proof streamed (never stored), kind W
  uv run python search/experiments/e042/certify_pb.py g10_$2_W$3 g10 $2 $3 --out $PB/certs --stream --cachemax 1000000 \
    --blocks $(blocks $2 $3) ;;
all)
  sh "$0" rstar; sh "$0" export; sh "$0" lift; sh "$0" ctl
  for k in X Z; do sh "$0" cert $k 10; done
  for k in X Z; do sh "$0" cert $k 11; done ;;
esac
