#!/bin/bash
# worker 2: controls
set -e
cd "$(dirname "$0")/../../.."
O=results/theoryB_audit/lift_ctl.jsonl
L=search.theory.B_audit.lift
uv run python -m $L gross results/E-032-audit/segctl_spec.json Z results/E-032-gross-short-period/w10_X_all_A1A2A3B3B1B2.pkl --out $O
uv run python -m $L bb90 search/experiments/e028/u16_spec.json Z results/E-028-bb90-interleaved/w9_X_all_A1A2A3B2B1B3.pkl --out $O
uv run python -m $L bb90 search/experiments/e028/u16_spec.json X results/E-028-bb90-interleaved/w9_Z_all_A1A2A3B2B1B3.pkl --out $O
uv run python -m $L gross search/experiments/e032/ctl_p10_spec.json Z results/E-032-gross-short-period/w11_X_all_A1A2A3B3B1B2.pkl --out $O
uv run python -m $L gross search/experiments/e032/ctl_p10_spec.json X results/E-032-gross-short-period/w11_Z_all_A1A2A3B3B1B2.pkl --out $O
uv run python -m $L gross search/experiments/e032/ctl_p10_spec.json Z results/E-032-gross-short-period/w10_X_all_A1A2A3B3B1B2.pkl --flips 1 --out $O
