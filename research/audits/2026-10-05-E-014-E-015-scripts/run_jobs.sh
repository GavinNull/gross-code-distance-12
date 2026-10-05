#!/bin/bash
# usage: run_jobs.sh <jobsfile> <P> ; each line: outfile inst W case [split_mod split_idx]
cd /Users/ephemeral/Desktop/qec-ai-search
cat $1 | xargs -P $2 -L 1 bash -c 'o=$0; shift 0; [ -s $o ] && grep -q SUMMARY $o && exit 0; results/E-014-E-015-audit/dfs128 "$1" "$2" "$3" $4 $5 > $o'
echo DONE
