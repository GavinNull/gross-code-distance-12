#!/bin/sh
# Auditor: c16 / u16 spot checks with the independent engine on the auditor's own exports (run in results/E-029-audit)
for B in Z X; do
  for R in 1 2 3; do ./auditsearch c16_${B}_R${R}.txt decide 9 > au_c16_${B}_R${R}_d9.txt; done
  ./auditsearch c16_${B}_R1.txt decide 10 > au_c16_${B}_R1_d10.txt
  for R in 1 2; do ./auditsearch u16_${B}_R${R}.txt decide 8 > au_u16_${B}_R${R}_d8.txt; ./auditsearch u16_${B}_R${R}.txt decide 9 > au_u16_${B}_R${R}_d9.txt; done
done
./auditsearch c16_Z_R12.txt decide 9 > au_c16_Z_R12_d9.txt
