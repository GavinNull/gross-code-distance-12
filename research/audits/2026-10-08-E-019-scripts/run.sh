#!/bin/bash
# helper: run t2_dcirc.py with uv
cd /Users/ephemeral/Desktop/qec-ai-search/research/audits/2026-10-08-E-019-scripts
exec uv run --project /Users/ephemeral/Desktop/qec-ai-search python t2_dcirc.py "$@"
