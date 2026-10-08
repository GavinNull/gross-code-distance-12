#!/bin/bash
R=/Users/ephemeral/Desktop/qec-ai-search/results/E-019-audit
I=$R/inst; D=$R/dfs
case $1 in
 A) $R/mdfs $I/bb288_x_VIII11_X_T5_f0_sd6_3-3.txt 9 > $D/bb288_x_VIII11_X_W9.txt; $R/mdfs $I/bb288_x_VIII11_Z_T5_f0_sd6_3-3.txt 10 > $D/bb288_x_VIII11_Z_W10.txt; $R/mdfs $I/bb288_x_VIII11_X_T5_f0_sd6_3-3.txt 10 > $D/bb288_x_VIII11_X_W10.txt;;
 B) $R/mdfs $I/bb288_y_IV00_Z_T5_f0_sd6_3-3.txt 11 > $D/bb288_y_IV00_Z_W11.txt;;
 C) $R/mdfs $I/bb288_xy_VIII00_X_T5_f0_sd6_3-3.txt 11 > $D/bb288_xy_VIII00_X_W11.txt;;
 D) $R/mdfs $I/bb288_y_IV00_X_T5_f0_sd6_3-3.txt 11 > $D/bb288_y_IV00_X_W11.txt;;
esac
