#!/bin/bash
# complete extended-logical lists (auditor's enumeration) + set comparison with E-043's pickles
cd "$(dirname "$0")/../../.."
T=results/E-043-table
L="uv run python -m search.experiments.e043_audit.lists"
$L ibm90 Z 8 --cmp 7:$T/list_ibm90_spec_Z_w7.pkl,8:$T/list_ibm90_spec_Z_w8.pkl
$L ibm90 X 8 --cmp 6:$T/list_ibm90_spec_X_w6.pkl,7:$T/list_ibm90_spec_X_w7.pkl,8:$T/list_ibm90_spec_X_w8.pkl
for b in Z X; do
  $L b9 $b 8 --cmp 7:$T/list_bb90_P9_c3_${b}_w7.pkl,8:$T/list_bb90_P9_c3_${b}_w8.pkl
  $L b10 $b 8 --cmp 7:$T/list_bb90_P10_c31_${b}_w7.pkl,8:$T/list_bb90_P10_c31_${b}_w8.pkl
done
$L ibmg Z 9 --cmp 9:$T/list_ibm_gross_spec_Z_w9.pkl
$L ibmg X 9 --cmp 8:$T/list_ibm_gross_spec_X_w8.pkl,9:$T/list_ibm_gross_spec_X_w9.pkl
for b in Z X; do $L g9 $b 10 --cmp 9:$T/list_g9_d11_spec_${b}_w9.pkl,10:$T/list_g9_d11_spec_${b}_w10.pkl; done
