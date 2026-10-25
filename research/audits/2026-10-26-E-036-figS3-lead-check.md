# E-036 addendum: lead's edge-by-edge check of SI Fig. S3 (2026-10-26)

Source: arXiv 2505.09684v1, image `2D_Exp_SM_circuit.png` (Fig. S3), viewed in the browser.
Panels (2),(3),(5),(6),(7),(9),(10) are CZ layers 1–7; (1),(4),(8),(11) are H layers; (12) is measurement.
Expected edges were generated from `search/experiments/e036/common.py` (kunlun_spec: IBM slot order,
X: -,A2,B2,B1,B3,A1,A3; Z: A1T,A3T,B1T,B2T,B3T,A2T,-; index x^a y^b = 3a+b).

| CZ layer | panel | expected edges | match |
|---|---|---|---|
| 1 | (2) | Z0-R6 Z1-R7 Z2-R8 Z5-R2 Z6-R3 Z7-R4 Z8-R5 | 7/7 |
| 2 | (3) | Xj-Lj (j=0,1,3..7); Z0-R1 Z1-R2 Z2-R0 Z5-R3 Z6-R7 Z7-R8 Z8-R6 | 14/14 |
| 3 | (5) | Xj-Rj; Z0-L2 Z1-L0 Z2-L1 Z5-L4 Z6-L8 Z7-L6 Z8-L7 | 14/14 |
| 4 | (6) | X0-R1 X1-R2 X3-R4 X4-R5 X5-R3 X6-R7 X7-R8; Zj-Lj | 14/14 |
| 5 | (7) | X0-R6 X1-R7 X3-R0 X4-R1 X5-R2 X6-R3 X7-R4; Z0-L3 Z1-L4 Z2-L5 Z5-L8 Z6-L0 Z7-L1 Z8-L2 | 14/14 |
| 6 | (9) | X0-L3 X1-L4 X3-L6 X4-L7 X5-L8 X6-L0 X7-L1; Zj-Rj | 14/14 |
| 7 | (10) | X0-L2 X1-L0 X3-L5 X4-L3 X5-L4 X6-L8 X7-L6 | 7/7 |

All 84 edges match; measured checks (X2, X8, Z3, Z4 absent) and the final measurement of all 14 checks match.
The reconstruction qualifier in the audit ("as we reconstruct it"; layers 2/5 only spot-checked) is resolved:
the E-036 circuit is the published Fig. S3 circuit.
