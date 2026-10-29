"""Unit tests of the union-find pairing solver (bulk_lift).  uv run python -m search.theory.B.test_bulk"""
from search.theory.B.bulk import bulk_lift

T = lambda co, **k: bulk_lift(co, **k) is not None
# private reader with offsets differing by 1: needs a flip
assert T([[{0: (0,)}], [{0: (1,)}]])   # one private reader: shifts absorb it
# 2-cycle with holonomy 1: f -z0- g -z1- f
co = [[{0: (0,), 1: (0,)}], [{0: (0,), 1: (1,)}]]
assert not T(co) and T(co, flips=1) and T(co, mod=1)
# holonomy 2: infeasible in bulk and mod 3, feasible mod 2
co = [[{0: (0,), 1: (0,)}], [{0: (0,), 1: (2,)}]]
assert not T(co) and T(co, mod=2) and not T(co, mod=3)
# data-like option choice resolves it
co = [[{0: (0,), 1: (0,)}], [{0: (0,), 1: (2,)}, {0: (1,), 1: (0,)}]]
assert not T(co)
co = [[{0: (0,), 1: (0,)}], [{0: (0,), 1: (2,)}, {0: (1,), 1: (2,)}, {0: (0,), 1: (0,)}]]
assert T(co)
# four items at one reader: pairing choice
co = [[{0: (0,)}], [{0: (5,)}], [{0: (5,)}], [{0: (0,)}]]
assert T(co)
co = [[{0: (0,), 1: (0,)}], [{0: (0,), 1: (3,)}], [{1: (0,), 2: (0,)}], [{1: (3,), 2: (0,)}]]
assert T(co)   # z1 pairs (f0,f2) and (f1,f3)? offsets 0,3,0,3 -> yes with equal shifts
print("ok")
