#!/bin/bash
cd /Users/ephemeral/Desktop/qec-ai-search/research/audits/2026-10-11-E-022-scripts
exec uv run --project /Users/ephemeral/Desktop/qec-ai-search python a3_dcirc.py "$@" > /dev/null 2>> /Users/ephemeral/Desktop/qec-ai-search/results/E-022-audit/a3_err.log
