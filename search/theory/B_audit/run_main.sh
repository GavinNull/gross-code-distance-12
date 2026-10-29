#!/bin/bash
# worker 1: targets (u11 Z, c11 X)
set -e
cd "$(dirname "$0")/../../.."
O=results/theoryB_audit/lift_main.jsonl
L=search.theory.B_audit.lift
uv run python -m $L gross search/experiments/e032/u11_spec.json Z results/E-032-gross-short-period/w10_X_all_A1A2A3B3B1B2.pkl --flips 1 --out $O
uv run python -m $L bb90 search/experiments/e030/c11_spec.json X results/E-028-bb90-interleaved/w8_Z_all_A1A2A3B2B1B3.pkl --flips 1 --out $O
uv run python -m $L gross search/experiments/e032/u11_spec.json Z results/E-032-gross-short-period/w11_X_all_A1A2A3B3B1B2.pkl --out $O
uv run python -m $L bb90 search/experiments/e030/c11_spec.json X results/E-028-bb90-interleaved/w9_Z_all_A1A2A3B2B1B3.pkl --out $O
