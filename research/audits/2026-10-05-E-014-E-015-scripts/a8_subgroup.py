"""A5b: second symmetry reduction for gross Fig. 12: lattice instance with the order-8 subgroup
{(di, dj): di in {0,3}, dj in {0,3,6,9}} of the 24-element colour-preserving translation group."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
import a1_gross as A, extx
from gf2 import logical_basis
HX, HZ, xo, zo, q = A.lat()
LX = logical_basis(HZ, HX); LZ = logical_basis(HX, HZ)
perms = []
for di in (0, 3):
    for dj in (0, 3, 6, 9):
        perms.append(np.array([q("F" if j < 72 else "O", (j % 72) // 12 + di, (j % 72) % 12 + dj) for j in range(144)]))
for kind, H, L, oo in (("X", HZ, LZ, xo), ("Z", HX, LX, zo)):
    e = extx.build(H, L, oo, 144)
    assert all(extx.logical_transform_ok(H, L, p) for p in perms)
    orb, reps, _ = extx.orbits(e, perms)
    print(kind, len(reps), np.bincount(orb).tolist()[:5])
    extx.dump128(e["He"], e["Le"], orb, reps, A.OUT / f"gross_lat_sub8_{kind}.txt")
