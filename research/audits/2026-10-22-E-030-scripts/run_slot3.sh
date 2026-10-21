#!/bin/bash
# sequential queue for the third worker slot (auditor E-030)
cd "$(dirname "$0")/../../.." || exit 1
S=research/audits/2026-10-22-E-030-scripts
O=results/E-030-audit
while kill -0 37881 2>/dev/null; do sleep 10; done
uv run python $S/a3_lift.py search/experiments/e030/c11_spec.json X 1 2 3 4 > $O/a3_c11_X_1-4.log 2>&1
PYTHONPATH=. uv run python $S/a4_gap.py search/experiments/e030/c11_spec.json > $O/a4_gap.log 2>&1
uv run python $S/a3_lift.py results/E-028-bb90-interleaved/segctl_A1A2A3B2B1B3_A1A2A3B2B1B3.json Z 1 > $O/a3_segctl.log 2>&1
for t in "A1A2A3B2B1B3 A1A3A2B3B1B2 10" "A1A3A2B3B1B2 A1A2A3B3B1B2 9" "A1A2A3B3B1B2 A1A3A2B2B1B3 8" "A1A2A3B2B1B3 A1A2A3B2B1B3 10"; do
  set -- $t
  PYTHONPATH=.:tests uv run python -m search.experiments.e028.cegar9 --xo $1 --zo $2 --hs "0,1;1,0" --P $3 --nowrap 0 \
    --max_sec 600 --tag ../E-030-audit/cegar_rerun_$1_$2_P$3 > $O/cegar_rerun_$1_$2_P$3.log 2>&1
done
uv run python $S/a5_random_uniform.py 10 6 1 > $O/a5_rand_P10.log 2>&1
uv run python $S/a3_lift.py search/experiments/e030/c11_spec.json X $(seq 5 25) > $O/a3_c11_X_5-25.log 2>&1
echo DONE > $O/slot3.done
