#!/bin/bash
# E-024b tool control + sweep: gsat on the Fig. 12 class (colour-symmetric, (a+b) mod 3), wrap P=13..20 and nowrap P=8..20.
# Up to 3 concurrent single-process runs (xargs -P 3), 1800 s each.
cd "$(dirname "$0")/../../.."
X=A1A2A3B3B1B2,A1A2A3B1B2B3,A1A3A2B3B1B2; Z=A1A3A2B3B1B2,A1A2A3B1B2B3,A1A2A3B3B1B2; R=results/E-024b-gross12-other-classes
jobs=""
for P in 13 14 15 16 17 18 19 20; do jobs="$jobs $P:0"; done
for P in 8 9 10 11 12 13 14 15 16 17 18 19 20; do jobs="$jobs $P:1"; done
echo $jobs | tr ' ' '\n' | xargs -P 3 -I{} bash -c 'P=${0%%:*}; W=${0##*:}; t=gs_fig12_P${P}$([ $W = 1 ] && echo nw); PYTHONPATH=.:tests uv run python -m search.experiments.e024b.gsat --col 3,1,1 --x '$X' --z '$Z' --P $P --nowrap $W --max_sec 1800 --tag $t > '$R'/$t.log 2>&1' {}
echo SWEEPDONE > $R/sweep_done.txt
