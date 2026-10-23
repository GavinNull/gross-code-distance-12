#!/bin/sh
# Auditor: regenerate and re-check 7 E-034 lift batches (sequential, one worker)
cd /Users/ephemeral/Desktop/qec-ai-search
B="env PYTHONPATH=.:tests uv run python research/audits/2026-10-23-E-034-scripts/batchchk.py e028"
$B search/experiments/e030/c11_spec.json A1A2A3B2B1B3 A1A2A3B2B1B3 X 25 33 34 results/E-034-veripb3-u11/lift/c11/results.jsonl
$B search/experiments/e030/c11_spec.json A1A2A3B2B1B3 A1A2A3B2B1B3 Z 20 0 27 results/E-034-veripb3-u11/lift/c11/results.jsonl
$B search/experiments/e030/c11_spec.json A1A2A3B2B1B3 A1A2A3B2B1B3 X 19 7 26 results/E-034-veripb3-u11/lift/c11_cake/results.jsonl
$B search/experiments/e030/c13_spec.json A1A2A3B2B1B3 A1A2A3B2B1B3 Z 12 16 17 results/E-034-veripb3-u11/lift/c13/results.jsonl
$B search/experiments/e030/c13_spec.json A1A2A3B2B1B3 A1A2A3B2B1B3 X 6 3 12 results/E-034-veripb3-u11/lift/c13/results.jsonl
$B search/experiments/e030/c12_spec.json A1A2A3B2B1B3 A1A2A3B2B1B3 X 12 9 17 results/E-034-veripb3-u11/lift/c12/results.jsonl
$B search/experiments/e030/c12_spec.json A1A2A3B2B1B3 A1A2A3B2B1B3 Z 1 0 12 results/E-034-veripb3-u11/lift/c12/results.jsonl
