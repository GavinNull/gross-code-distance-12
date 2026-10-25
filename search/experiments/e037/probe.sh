#!/bin/sh
# E-037: count-only pass-1 probes (no proof): nodes and trivial sets per R.   sh probe.sh SOURCE_PREFIX W R1 R2 ...
# e.g. sh search/experiments/e037/probe.sh ibm:gross:X 9 1 2 3 6 12
P=$1; W=$2; shift 2
O=results/E-037-ibm-cert/probe
for R in "$@"; do
  n=$(echo $P:$R | tr ':' '_')_W$W
  uv run python search/experiments/e037/dem_inst.py $P:$R $W $O/$n --no-symcheck > $O/$n.build.log 2>&1
  /usr/bin/time -p results/E-037-ibm-cert/bin/pbdfs $O/$n.inst -R $O/$n.triv > $O/$n.pass1.log 2>&1
  echo "$P:$R W=$W $(grep RESULT $O/$n.pass1.log | cut -c1-60) $(grep -o 'trivial_recorded=[0-9]*' $O/$n.pass1.log) $(grep user $O/$n.pass1.log)"
  rm -f $O/$n.opb $O/$n.inst
done
