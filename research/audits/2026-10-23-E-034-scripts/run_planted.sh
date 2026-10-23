#!/bin/sh
# Auditor planted tests (orbits chosen by the auditor), sequential, one worker
cd /Users/ephemeral/Desktop/qec-ai-search
P="uv run python research/audits/2026-10-23-E-034-scripts/planted.py"
$P Z 11 5144 400000000 results/E-031-xor-certificates/u11/u11_Z_w10.json results/E-031-xor-certificates/u11/u11_Z_w11.json
$P Z 10 77 400000000 results/E-031-xor-certificates/u11/u11_Z_w10.json
$P X 10 77 400000000 results/E-031-xor-certificates/u11/u11_X_w10.json
$P X 11 1378 400000000 results/E-031-xor-certificates/u11/u11_X_w10.json results/E-031-xor-certificates/u11/u11_X_w11.json
