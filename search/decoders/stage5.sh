#!/bin/zsh
# E-006 stage 5: method (c) low-weight failure search
cd /Users/ephemeral/Desktop/qec-ai-search
W() { uv run python -m search.decoders.run_wdec "$@"; }
W --code bb72 --p 0.001 --n3 100000 --decoders bposd,relay5 --workers 6
W --code bb90 --p 0.001 --n3 100000 --n4 100000 --decoders bposd,relay5 --workers 6
