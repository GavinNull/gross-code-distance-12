#!/bin/zsh
# E-006 stage 1: surface validation + BB72 direct sampling (method a)
cd /Users/ephemeral/Desktop/qec-ai-search
R() { uv run python -m search.decoders.run_direct "$@"; }
R --code surf3 --p 0.004 --batches 40 --batch-size 500 --sub 1.0 --workers 6 --decoders bposd,relay5
R --code surf5 --p 0.004 --batches 60 --batch-size 500 --sub 1.0 --workers 6 --decoders bposd,relay5
R --code bb72 --p 0.004 --batches 30 --batch-size 100 --sub 0.25 --workers 6
R --code bb72 --p 0.003 --batches 40 --batch-size 200 --sub 0.15 --workers 6
