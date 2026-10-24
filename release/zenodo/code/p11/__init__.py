"""Verification code for the two period-11 circuits of the paper (Table I) and their relatives.

  u11   gross code [[144,12,12]], period 11, d_circ = 12 (Theorem 1)
  c11   [[90,8,10]], period 11, d_circ = 10 (Theorem 2); c12 (period 12, non-wrapping) and c13 (period 13) likewise;
        c16 (period 16) is treated in code/bb90/.

Library module: common (circuit registry, codes, extended codes, lists, translation groups, extended lift).
The memory-circuit template and SD6 noise are those of code/gross12/ (schedule.py, noise.py); the augmented
detector error model and the exact SAT lift are those of code/bb90/ext.py, which are written for any CSS code.
Scripts (run from the package root): check_circuits.py, lists.py, lift.py, premises.py, inject_upper_bound.py,
direct.py (direct search on the DEM, mitm.c).
"""
