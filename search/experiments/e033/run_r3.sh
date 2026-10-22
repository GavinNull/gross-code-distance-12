#!/bin/bash
# E-033: u11 Z R=3 W=12 enumeration split by root orbit ranges (ccsearch enum W o0 o1; root cases are disjoint, so the
# union over ranges is the full enumeration).  Orbit 0 starts when the R=2 run ends; [1,2) and [2,32) when stage 3 ends.
cd "$(dirname "$0")/../../.." || exit 1
O=results/E-033-gross-u11-ler
while pgrep -f "inst/u11_Z_R2.txt enum" >/dev/null; do sleep 20; done
/usr/bin/time -p $O/ccsearch $O/inst/u11_Z_R3.txt enum 12 0 1 > $O/runs/u11_Z_R3_enum12_o0-1.txt 2>&1 &
while kill -0 $(cat $O/stage3.pid) 2>/dev/null; do sleep 20; done
/usr/bin/time -p $O/ccsearch $O/inst/u11_Z_R3.txt enum 12 1 2 > $O/runs/u11_Z_R3_enum12_o1-2.txt 2>&1 &
/usr/bin/time -p $O/ccsearch $O/inst/u11_Z_R3.txt enum 12 2 32 > $O/runs/u11_Z_R3_enum12_o2-32.txt 2>&1 &
wait
