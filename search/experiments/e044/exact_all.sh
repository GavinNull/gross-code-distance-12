#!/bin/bash
cd "$(dirname "$0")/../../.." || exit 1
E="env PYTHONPATH=.:tests uv run python -m search.experiments.e044.exact weights"
$E ibm 10 1,2,3 ZX
$E ibm90 8 1,2,3,4,5 ZX
$E c11 10 2,3,4 ZX
$E u11 12 1,2 Z
$E u11 12 1 X
$E g10 12 1 Z
$E g10 12 1 X
echo ALLDONE
