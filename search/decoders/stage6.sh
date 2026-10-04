#!/bin/zsh
# E-006 stage 6 (lead priority 2026-10-04): gross code. (B) directed low-weight search; (A) fixed-weight f_w Relay5 vs MLE
cd /Users/ephemeral/Desktop/qec-ai-search
uv run python -m search.decoders.run_wdec --code gross --p 0.001 --skip12 --n3 20000 --n4 40000 --n5 60000 --decoders relay5,bposd --workers 6
uv run python -m search.decoders.run_fixedweight --code gross --p 0.001 --w 55,65,75 --n 3000 --batch 250 --sub 0.02 --trigger relay5 --seed 7206 --file-tag A --workers 6 --decoders relay5
