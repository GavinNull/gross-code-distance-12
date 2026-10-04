#!/bin/zsh
# E-006 stage 2: BB90 / gross direct sampling (method a). (first attempt at bb90 p=0.004 used sub=0.15 for
# batches 0,2,3,4,8; restarted with sub=0.03 because MILP solves on BB90 cost ~5-20 s each)
cd /Users/ephemeral/Desktop/qec-ai-search
R() { uv run python -m search.decoders.run_direct "$@"; }
R --code bb90 --p 0.004 --batches 30 --batch-size 100 --sub 0.03 --workers 6 --decoders bposd,lsd,relay5,relay1
R --code bb90 --p 0.003 --batches 25 --batch-size 200 --sub 0.02 --workers 6 --decoders bposd,relay5,relay1
R --code gross --p 0.004 --batches 20 --batch-size 50 --sub 0.03 --workers 6 --decoders bposd,relay5,relay1
