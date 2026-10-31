#!/bin/bash
cd "$(dirname "$0")/../../.." || exit 1
D="env PYTHONPATH=.:tests uv run python -m search.experiments.e044.diag"
$D ibm90 Z lam1 16 6000
$D c11 Z lam1 16 15000
$D ibm Z lam1 36 2000
$D g10 Z lam1 36 2000
echo ALLDONE
