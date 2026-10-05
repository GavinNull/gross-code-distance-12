#!/bin/bash
# usage: run_a5.sh <inst-prefix> <W> <jobsfile> <outdir> <P>
cd /Users/ephemeral/Desktop/qec-ai-search
R=results/E-014-E-015-audit
mkdir -p $4
cat $3 | xargs -P $5 -L 1 bash -c 'f='$4'/out_${0}_c${1}_s${3}.txt; [ -s $f ] && grep -q SUMMARY $f && exit 0; '$R'/dfs128 '$1'_${0}.txt '$2' $1 $2 $3 > $f'
echo DONE
