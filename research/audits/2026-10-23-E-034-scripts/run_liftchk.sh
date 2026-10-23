#!/bin/sh
cd /Users/ephemeral/Desktop/qec-ai-search
B="env PYTHONPATH=.:tests uv run python research/audits/2026-10-23-E-034-scripts/liftchk.py e028"
$B search/experiments/e030/c13_spec.json A1A2A3B2B1B3 A1A2A3B2B1B3 Z 12 --n 300 --seed 34
$B search/experiments/e030/c12_spec.json A1A2A3B2B1B3 A1A2A3B2B1B3 X 7 --n 300 --seed 34
$B search/experiments/e030/c12_spec.json A1A2A3B2B1B3 A1A2A3B2B1B3 Z 12 --n 200 --seed 34
$B search/experiments/e030/c11_spec.json A1A2A3B2B1B3 A1A2A3B2B1B3 X 25 --n 150 --seed 34
