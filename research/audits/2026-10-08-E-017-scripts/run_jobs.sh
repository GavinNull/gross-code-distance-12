#!/bin/bash
# usage: run_jobs.sh jobsfile npar ; each line: inst W case [split nsplit] [first] ; output dfs/<inst>_W<W>_c<case>[_s<split>of<n>].txt
cd /Users/ephemeral/Desktop/qec-ai-search/results/E-017-audit
cat "$1" | xargs -P "$2" -L 1 bash -c 'inst=$0; W=$1; cs=$2; sp=$3; ns=$4; extra=$5; tag=$(basename $inst .txt)_W${W}_c${cs}; if [ -n "$sp" ] && [ "$sp" != first ]; then tag=${tag}_s${sp}of${ns}; fi; [ "$sp" = first ] && extra=first && sp=; [ -n "$extra" ] && tag=${tag}_$extra; ./adfs $inst $W $cs $sp $ns $extra > dfs/$tag.txt 2>&1'
echo ALLDONE
