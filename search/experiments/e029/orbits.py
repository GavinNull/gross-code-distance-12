"""E-029 part 3 (+ comparison for part 2): orbit structure of the published weight-11 lists (own code).

    uv run python search/experiments/e029/orbits.py [--compare BASIS SOLFILE INSTMETA ...]

For each basis: the 24 colour-preserving translations act on the 360 extended columns (computed here from the
column supports: translate support, look up the column with the same (H, L) image).  Checks:
  * the action on columns is free (every column orbit has 24 elements);
  * the list of 4224 is closed under the group;
  * no listed logical is fixed by a nontrivial translation (stabiliser of every logical is trivial);
  * orbit counts under every subgroup K (all subgroups, enumerated as subsets closed under addition) equal 4224/|K|.
--compare: SOL lines from ccsearch (enum mode on the ext instance, root cases), mapped to published column
indices via the image keys, expanded by the group, deduplicated, and compared (set equality) with the list.
"""
import itertools
import json
import sys
from pathlib import Path

import numpy as np

REL = Path(__file__).resolve().parents[3] / "release" / "zenodo" / "data"


def tq(q, a, b):
    blk, i = divmod(q, 72)
    x, y = divmod(i, 6)
    return blk * 72 + ((x + a) % 12) * 6 + (y + b) % 6


def load(basis):
    code = json.load(open(REL / "code" / "gross_code.json"))
    ext = json.load(open(REL / "extended_code" / f"extended_code_{basis}_memory.json"))
    lst = json.load(open(REL / "logicals" / f"weight11_logicals_{basis}_memory.json"))
    return code, ext, lst


def mats(code, basis):
    """rows are stored as supports (lists of qubit indices)"""
    n = code["n"]

    def m(name):
        A = np.zeros((len(code[name]), n), np.uint8)
        for i, row in enumerate(code[name]):
            A[i, row] = 1
        return A
    return (m("HZ"), m("LZ")) if basis == "Z" else (m("HX"), m("LX"))


def key(H, L, sup):
    v = np.zeros(H.shape[1], np.uint8)
    v[list(sup)] = 1
    return ((H @ v) % 2).tobytes() + ((L @ v) % 2).tobytes()


def main(argv):
    out = {}
    cmp = {}
    if "--compare" in argv:
        i = argv.index("--compare")
        rest = argv[i + 1:]
        for j in range(0, len(rest), 3):
            cmp.setdefault(rest[j], []).append((rest[j + 1], rest[j + 2]))
    for basis in ("Z", "X"):
        code, ext, lst = load(basis)
        H, L = mats(code, basis)
        cols = ext["columns"]
        kidx = {}
        for c in cols:
            k = key(H, L, c["support"])
            assert k not in kidx
            kidx[k] = c["index"]
            assert sorted(np.nonzero((H @ np.isin(np.arange(H.shape[1]), c["support"])) % 2)[0].tolist()) == sorted(c["H"])
        # all 72 translations; keep those preserving the column set
        G = []
        for a in range(12):
            for b in range(6):
                perm = []
                for c in cols:
                    k = key(H, L, [tq(q, a, b) for q in c["support"]])
                    if k not in kidx:
                        break
                    perm.append(kidx[k])
                else:
                    G.append(((a, b), tuple(perm)))
        assert len(G) == 24, len(G)
        elems = [t for t, _ in G]
        P = dict(G)
        free_cols = all(len({P[g][c] for g in elems}) == 24 for c in range(len(cols)))
        S = [tuple(sorted(x["columns"])) for x in lst["logicals"]]
        Sset = set(S)
        assert len(Sset) == len(S) == 4224
        # validity of each listed logical (H sum 0, L sum != 0, 11 distinct columns)
        valid = 0
        for s in S:
            hs = np.zeros(H.shape[0], np.uint8); ls = np.zeros(L.shape[0], np.uint8)
            for j in s:
                hs[cols[j]["H"]] ^= 1; ls[cols[j]["L"]] ^= 1
            valid += int(len(set(s)) == 11 and not hs.any() and ls.any())
        closed = all(tuple(sorted(P[g][j] for j in s)) in Sset for s in S for g in elems)
        stab_nontrivial = sum(1 for s in S for g in elems if g != (0, 0) and tuple(sorted(P[g][j] for j in s)) == s)

        def add(g, h):
            return ((g[0] + h[0]) % 12, (g[1] + h[1]) % 6)
        # all subgroups: closures of 1- and 2-element generating sets (G is abelian of rank <= 2)
        subs = set()
        for g, h in itertools.combinations_with_replacement(elems, 2):
            K = {(0, 0)}
            frontier = [g, h]
            while frontier:
                x = frontier.pop()
                if x in K:
                    continue
                K.add(x)
                frontier += [add(x, y) for y in list(K)]
            subs.add(frozenset(K))
        sub_rows = []
        for K in sorted(subs, key=lambda K: (len(K), sorted(K))):
            seen, norb, sizes = set(), 0, {}
            for s in S:
                if s in seen:
                    continue
                orb = {tuple(sorted(P[g][j] for j in s)) for g in K}
                seen |= orb
                norb += 1
                sizes[len(orb)] = sizes.get(len(orb), 0) + 1
            sub_rows.append(dict(order=len(K), gens=sorted(K)[:4], orbits=norb, orbit_sizes=sizes,
                                 expected=4224 // len(K), ok=(norb * len(K) == 4224 and list(sizes) == [len(K)])))
        res = dict(group=elems, free_on_columns=free_cols, count=len(S), valid=valid, closed=closed,
                   nontrivial_stabiliser_pairs=stab_nontrivial, subgroups=sub_rows,
                   n_subgroups=len(sub_rows), all_subgroups_ok=all(r["ok"] for r in sub_rows),
                   G_orbits=next(r["orbits"] for r in sub_rows if r["order"] == 24))
        # comparison with ccsearch enumeration
        for solfile, meta in cmp.get(basis, []):
            mcols = json.load(open(meta))["columns"]
            mapj = [kidx[key(H, L, c["support"])] for c in mcols]
            found = set()
            nsol = 0
            for line in open(solfile):
                if not line.startswith("SOL"):
                    continue
                nsol += 1
                w = int(line.split()[1])
                ids = [int(x) for x in line.split(":")[1].split()]
                assert w == len(ids)
                s = [mapj[j] for j in ids]
                for g in elems:
                    found.add(tuple(sorted(P[g][j] for j in s)))
            res.setdefault("compare", []).append(dict(file=solfile, sol_lines=nsol, expanded=len(found),
                                                      equal_to_list=(found == Sset), only_new=len(found - Sset),
                                                      only_list=len(Sset - found),
                                                      weights=sorted({len(s) for s in found})))
        out[basis] = res
        print(basis, json.dumps({k: v for k, v in res.items() if k != "subgroups"}, default=str))
        for r in sub_rows:
            print("   |K|=%2d orbits=%4d sizes=%s ok=%s" % (r["order"], r["orbits"], r["orbit_sizes"], r["ok"]))
    od = Path("results/E-029-direct-dcirc")
    od.mkdir(parents=True, exist_ok=True)
    (od / "orbits.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1:])
