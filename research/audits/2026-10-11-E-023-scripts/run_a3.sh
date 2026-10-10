#!/bin/bash
# priority (a) MC: 4 parallel jobs then Z sectors
cd /Users/ephemeral/Desktop/qec-ai-search
S=research/audits/2026-10-11-E-023-scripts
L=results/E-023-audit/logs; mkdir -p $L
export PYTHONPATH=. OMP_NUM_THREADS=1
uv run python $S/a3_decode_basis.py mc m54_repo X 2 10000 91001 > $L/a3_repo_X_w2.log 2>&1 &
uv run python $S/a3_decode_basis.py mc m54_paper X 2 10000 91002 > $L/a3_paper_X_w2.log 2>&1 &
uv run python $S/a3_decode_basis.py mc m54_repo X 3 6000 91003 > $L/a3_repo_X_w3.log 2>&1 &
uv run python $S/a3_decode_basis.py mc m54_paper X 3 6000 91004 > $L/a3_paper_X_w3.log 2>&1 &
wait
uv run python $S/a3_decode_basis.py mc m54_repo Z 2 10000 91005 > $L/a3_repo_Z_w2.log 2>&1 &
uv run python $S/a3_decode_basis.py mc m54_paper Z 2 10000 91006 > $L/a3_paper_Z_w2.log 2>&1 &
uv run python $S/a3_decode_basis.py mc m54_repo Z 3 6000 91007 > $L/a3_repo_Z_w3.log 2>&1 &
uv run python $S/a3_decode_basis.py mc m54_paper Z 3 6000 91008 > $L/a3_paper_Z_w3.log 2>&1 &
wait
echo ALLDONE
