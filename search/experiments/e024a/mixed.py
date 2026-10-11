"""E-024a: 'mixed' families: start from the colour-symmetric units (orbits of the 24-element group G24), and split
only chosen units into orbits of a subgroup Hsplit <= G24 (others stay colour-symmetric).  Interface compatible with
e021.nwsat.Family as used by e021.nwfull.prepare_full / evaluate_full and e024a.cegar (item, label_of, items, idx,
touch, T, Hs = Hsplit [every unit is Hsplit-invariant, so logical orbit reps under Hsplit are valid]).
The family is invariant under all of G24 (abelian: g maps Hsplit-orbits inside a G24-orbit to Hsplit-orbits of the
same G24-orbit, and each split unit's sub-units are all free), so the 24 nogood images stay valid.
"""
from search.experiments.e018 import common as C
from search.experiments.e021.mono import table
from search.experiments.e021.nwsat import subgroup

N2 = 72
G24 = subgroup([(1, 2), (0, 3)])


def orbits(H):
    cls, reps = [-1] * N2, []
    for i in range(N2):
        if cls[i] >= 0:
            continue
        for h in H:
            pr, _ = C.tr(*h)
            cls[int(pr[i])] = len(reps)
        reps.append(i)
    return cls, reps


class MixedFamily:
    def __init__(self, split_gens, split_units):
        """split_units: set of (type, colour class index in the G24 orbit numbering)."""
        Hs = subgroup(split_gens)
        assert set(Hs) <= set(G24)
        self.Hs = Hs
        self.T = table()
        c24, r24 = orbits(G24)
        cH, rH = orbits(Hs)
        self.ucls, self.units, self.unit_rep = {}, [], {}
        for ty in "XZ":
            lab = {}
            arr = []
            for i in range(N2):
                key = ("s", c24[i], cH[i]) if (ty, c24[i]) in split_units else ("c", c24[i])
                if key not in lab:
                    lab[key] = len(lab)
                    self.units.append((ty, lab[key]))
                    self.unit_rep[(ty, lab[key])] = i
                arr.append(lab[key])
            self.ucls[ty] = arr
        self.items = [(ty, k, l) for (ty, k) in self.units for l in range(6)]
        self.idx = {it: n for n, it in enumerate(self.items)}
        self.touch = [[] for _ in range(144)]
        for ty in "XZ":
            for i in range(N2):
                for l in range(6):
                    self.touch[int(self.T[ty][i][l])].append((ty, i, l))
        self.nc = max(len([u for u in self.units if u[0] == ty]) for ty in "XZ")
        self.cls = None

    def item(self, ty, check, lab):
        return self.idx[(ty, self.ucls[ty][check], lab)]

    def label_of(self, ty, check, q):
        return int(list(self.T[ty][check]).index(q))
