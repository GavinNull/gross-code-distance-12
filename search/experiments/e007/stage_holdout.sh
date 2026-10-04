#!/bin/zsh
cd /Users/ephemeral/Desktop/qec-ai-search
R=results/E-007-relay-sa-tuning
uv run python -m search.experiments.e007.holdout bb72-dec-p3e-3 $R/sa-restricted-bb72-s0 15,11,12,24 holdout-restricted > $R/log-holdout-restricted-bb72.txt 2>&1
uv run python -m search.experiments.e007.holdout_direct bb72-dec-p3e-3 300 $R/sa-unrestricted-bb72-s0 15,19,7,20 6 > $R/log-holdout-direct-bb72.txt 2>&1
uv run python -m search.experiments.e007.holdout_direct bb90-dec-p3e-3 100 $R/sa-unrestricted-bb90-s0 7,5,6 7 > $R/log-holdout-direct-bb90.txt 2>&1
