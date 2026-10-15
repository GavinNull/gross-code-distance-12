"""Auditor (E-029): independent DEM export + symmetry verification.

    [TASK=bb90-dcirc] PYTHONPATH=.:tests uv run python research/audits/2026-10-15-E-029-scripts/myexport.py CIRCUIT_JSON BASIS R OUT [THEIR_INST]

* DEM via evaluator public entry (build_circuits + add_noise sd6 1e-3), decompose_errors=False, my own parser
  (detector/observable XOR per error instruction).
* Columns are written in MY order (sorted by (observables, detectors) descending) so that index-dependent
  behaviour of the engine differs from the experimenter's run.
* Symmetry: each of the 72 translations of the 12x6 check torus acts on detectors (check idx, round, type).
  Accepted iff it maps the column set onto itself AND every row of L∘P lies in rowspace[D;L] AND every row of L lies
  in rowspace[D;L∘P] (=> ker[D;L] = ker[D;L∘P], so on ker D: Lx != 0 <=> L P x != 0).  Gaussian elimination on Python
  ints (own code, not export.py's gf2_rank).
* Orbits listed in my own order (by descending max column index), representative = LAST column of the orbit list
  (the engine takes the first, so I write orbits with the max element first).
* If THEIR_INST is given: compare column multiset and orbit partition with the experimenter's instance.
"""
import json
import sys

import stim

sys.path[:0] = [".", "tests"]
from evaluators.candidate import build_circuits, parse_schedule  # noqa: E402
from evaluators.noise import add_noise  # noqa: E402
from evaluators.tasks import build_code, get_task  # noqa: E402


class Basis:
    """GF(2) row space with reduction (rows are python ints)."""

    def __init__(self):
        self.piv = {}  # leading bit -> row

    def reduce(self, v):
        while v:
            h = v.bit_length() - 1
            if h in self.piv:
                v ^= self.piv[h]
            else:
                return v
        return 0

    def add(self, v):
        v = self.reduce(v)
        if v:
            self.piv[v.bit_length() - 1] = v
            return True
        return False


def dem_cols(circ):
    dem = circ.detector_error_model(decompose_errors=False)
    cols = []
    for ins in dem.flattened():
        if ins.type != "error":
            continue
        d, o = 0, 0
        for t in ins.targets_copy():
            if t.is_relative_detector_id():
                d ^= 1 << t.val
            elif t.is_logical_observable_id():
                o ^= 1 << t.val
            elif t.is_separator():
                raise RuntimeError("separator in undecomposed DEM")
        cols.append((d, o))
    return dem, cols


def bits(x):
    out = []
    while x:
        b = x & -x
        out.append(b.bit_length() - 1)
        x ^= b
    return out


def main():
    path, basis, R, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    import os
    task = os.environ.get("TASK", "gross-dcirc")
    LMd = {"gross-dcirc": (12, 6), "bb90-dcirc": (15, 3), "bb72-dcirc": (6, 6)}
    l, m = LMd[task]
    code, _ = build_code(get_task(task), None)
    spec = parse_schedule(json.load(open(path)))
    circ = add_noise(build_circuits(spec.canonical(), code, R)[basis], "sd6", 1e-3)
    dem, cols = dem_cols(circ)
    nd, no = dem.num_detectors, dem.num_observables
    assert all(d or not o for d, o in cols), "weight-1 logical (empty detectors, nonzero obs)"
    cols = [c for c in cols if c[0]]
    assert len({d for d, _ in cols}) == len(cols), "duplicate detector sets"
    cols.sort(reverse=True)
    nc = len(cols)
    idx = {d: j for j, (d, _) in enumerate(cols)}
    # rows of D and L as ints over columns
    Drows = [0] * nd
    Lrows = [0] * no
    for j, (d, o) in enumerate(cols):
        for r in bits(d):
            Drows[r] |= 1 << j
        for r in bits(o):
            Lrows[r] |= 1 << j
    BD = Basis()
    rD = sum(BD.add(r) for r in Drows)
    BDL = Basis()
    for r in Drows + Lrows:
        BDL.add(r)
    rDL = len(BDL.piv)
    co = dem.get_detector_coordinates()
    key = {tuple(v): k for k, v in co.items()}
    group = []
    for a in range(l):
        for b in range(m):
            tmap = {}
            for k, v in co.items():
                i = int(v[0])
                x, y = divmod(i, m)
                tmap[k] = key[(float(((x + a) % l) * m + (y + b) % m),) + tuple(v[1:])]
            perm = []
            for d, o in cols:
                img = 0
                for r in bits(d):
                    img |= 1 << tmap[r]
                if img not in idx:
                    break
                perm.append(idx[img])
            else:
                assert sorted(perm) == list(range(nc))
                # (L P)_r as int over columns j: bit j set iff L[r, perm[j]]
                LP = []
                for r in range(no):
                    v = 0
                    for j in range(nc):
                        if (Lrows[r] >> perm[j]) & 1:
                            v |= 1 << j
                    LP.append(v)
                ok1 = all(BDL.reduce(v) == 0 for v in LP)
                B2 = Basis()
                for v in Drows + LP:
                    B2.add(v)
                ok2 = all(B2.reduce(v) == 0 for v in Lrows)
                if ok1 and ok2:
                    group.append(((a, b), perm))
                else:
                    print("translation", (a, b), "maps detector sets but not logical classes")
    # closure check
    gset = {tuple(p) for _, p in group}
    for _, p in group:
        for _, q in group:
            assert tuple(q[p[j]] for j in range(nc)) in gset, "accepted translations not closed"
    seen = [False] * nc
    orbs = []
    for c in range(nc):
        if seen[c]:
            continue
        orb = sorted({p[c] for _, p in group})
        for x in orb:
            seen[x] = True
        orbs.append(orb)
    assert all(len(o) == len(group) for o in orbs), "non-free orbit"
    orbs.sort(key=lambda o: -o[-1])
    with open(out, "w") as f:
        f.write(f"{nd} {nc} {no} {len(orbs)}\n")
        for d, o in cols:
            f.write(f"{len(bits(d))} {' '.join(map(str, bits(d)))} {len(bits(o))} {' '.join(map(str, bits(o)))}\n")
        for orb in orbs:
            o2 = [orb[-1]] + orb[:-1]   # representative = max index
            f.write(f"{len(o2)} {' '.join(map(str, o2))}\n")
    info = dict(nd=nd, nc=nc, no=no, rank_D=rD, rank_DL=rDL, obs_independent_mod_D=rDL - rD,
                group=[t for t, _ in group], norb=len(orbs), maxw=max(len(bits(d)) for d, _ in cols))
    if len(sys.argv) > 5:
        their = open(sys.argv[5]).read().split("\n")
        nr2, nc2, no2, norb2 = map(int, their[0].split())
        tcols = []
        for line in their[1:1 + nc2]:
            v = list(map(int, line.split()))
            k = v[0]
            d = sum(1 << r for r in v[1:1 + k])
            o = sum(1 << r for r in v[2 + k:2 + k + v[1 + k]])
            tcols.append((d, o))
        torbs = [frozenset(tcols[j] for j in map(int, line.split()[1:])) for line in their[1 + nc2:1 + nc2 + norb2]]
        info["same_columns_as_experimenter"] = sorted(tcols) == sorted(cols) and (nr2, no2) == (nd, no)
        info["same_orbit_partition"] = set(torbs) == {frozenset(cols[j] for j in o) for o in orbs}
    print(json.dumps(info))
    json.dump(info, open(out + ".info.json", "w"))


if __name__ == "__main__":
    main()
