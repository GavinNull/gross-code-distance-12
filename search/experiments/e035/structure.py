"""E-035 structure probe: per period-layer, which (check type, BB term) CNOT groups, preps and measurements occur.
A "term" is the displacement (block, dx, dy) between a check at grid position (a, b) and its data qubit; in a
translation-invariant schedule every check of one type applies the same term in a layer, so each group is one
rigid AOD translation of that ancilla sub-array (qSIEVE 2311.16980 / Xu 2308.08648 picture)."""
from __future__ import annotations
import json
from collections import defaultdict

from search.experiments.e035.common import CIRCS, spec, code_of, grid


def layer_structure(name: str):
    s = spec(name)
    l, m, nh = grid(name)
    P = s.period
    lay = defaultdict(lambda: {"X": set(), "Z": set(), "prepX": 0, "prepZ": 0, "measX": 0, "measZ": 0})
    for typ, checks in (("X", s.x_checks), ("Z", s.z_checks)):
        for i, c in enumerate(checks):
            ia, ib = divmod(i, m)
            lay[c.prep % P]["prep" + typ] += 1
            lay[c.meas % P]["meas" + typ] += 1
            for col, t in c.cnots:
                blk, j = divmod(col, nh)
                ja, jb = divmod(j, m)
                lay[t % P][typ].add((blk, (ja - ia) % l, (jb - ib) % m))
    out = []
    for t in range(P):
        L = lay[t]
        out.append(dict(t=t, X=sorted(L["X"]), Z=sorted(L["Z"]), prepX=L["prepX"], prepZ=L["prepZ"],
                        measX=L["measX"], measZ=L["measZ"]))
    return out


def main():
    res = {}
    for name in CIRCS:
        st = layer_structure(name)
        res[name] = st
        print(name, "period", len(st))
        for L in st:
            print("  t=%2d X%s Z%s prep(X%d,Z%d) meas(X%d,Z%d)" % (L["t"], L["X"], L["Z"], L["prepX"], L["prepZ"],
                                                                 L["measX"], L["measZ"]))
    return res


if __name__ == "__main__":
    main()
