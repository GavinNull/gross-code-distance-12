#!/bin/bash
# stim injection of every R=1 witness into R-round experiments (start and 2 rounds in), argument item (4)
cd "$(dirname "$0")/../../.."
P="uv run python -m search.experiments.e043_audit.persist"
Rs=1,2,3,5,8,12,20,30
if [ "$1" = a ]; then for b in Z X; do $P ibm90 $b 1 8 $Rs --shifts 0,2; $P b9 $b 1 9 $Rs --shifts 0,2; $P b10 $b 1 9 $Rs --shifts 0,2; done
else for b in Z X; do $P ibmg $b 1 10 $Rs --shifts 0,2; $P g9 $b 1 11 $Rs --shifts 0,2; done; fi
