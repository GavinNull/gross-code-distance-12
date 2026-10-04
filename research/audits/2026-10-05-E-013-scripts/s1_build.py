import sys, json; sys.path.insert(0, "research/audits/2026-10-05-E-013-scripts")
import numpy as np, stim
from aud13 import *
c, s = build()
print("legality problems:", legality(c, s)[:20], len(legality(c, s)))
