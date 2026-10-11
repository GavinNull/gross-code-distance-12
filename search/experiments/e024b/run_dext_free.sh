#!/bin/bash
# E-024b step 1d: per-check free type assignment (trivial subgroup: colours = the 72 checks), after run_dext2.sh
cd "$(dirname "$0")/../../.."
until grep -q ALLDONE2 results/E-024b-gross12-other-classes/dext_summary.jsonl; do sleep 30; done
for kind in X Z; do
  PYTHONPATH=. uv run python -m search.experiments.e024b.dextsat2 --kind $kind --sub "0,0" --workers 4 --max_sec 10800 \
    >> results/E-024b-gross12-other-classes/dext2_${kind}_free.log 2>&1
done
echo ALLDONE3 >> results/E-024b-gross12-other-classes/dext_summary.jsonl
