"""Claim 3: all 144 weight-10 extended logicals at R = 1 (Z basis): lift in segctl, no lift in u11; exact
conflicting-set structure in u11 (all achievable syndromes -> minimal family -> all irreducible conflicting sets),
order dependence of the deletion filter, translation orbits, and the single-detector mechanism classification."""
import collections, json, random, sys
from multiprocessing import Pool
sys.path.insert(0, __import__("os").path.dirname(__file__))
from g_common import *

SEG = segctl()
COLS = ext_columns(U11)
_, W10 = load_w10()


def prep(sj):
    c = circ(sj, 1)
    aug, dem, G, zero = dem_groups(c)
    return c, aug, dem, G


cS, augS, demS, GS = prep(SEG)
cU, augU, demU, GU = prep(U11)
COORD = demU.get_detector_coordinates()
cxU, measU, _ = tick_tables(cU)
cxS, measS, _ = tick_tables(cS)
P = U11["period"]
SUFFIX_OF = {}   # support -> X check index (for hook supports)
for i, ch in enumerate(U11["x_checks"]):
    o = order_of(ch, P)
    for k in range(1, 5):
        SUFFIX_OF.setdefault(tuple(sorted(o[k:])), i)


def rep(k):
    """representative support of a column: a data qubit if the column is a data column, else the hook suffix."""
    sups = COLS[k]
    d = [s for s in sups if len(s) == 1]
    return d[0] if d else min(sups, key=len)


def work(idx):
    S = W10[idx]
    v = np.zeros(N, np.uint8)
    for k in S:
        for q in rep(k): v[q] ^= 1
    r = dict(idx=idx, hz0=bool(not ((HZ @ v) % 2).any()), lz=[int(x) for x in np.flatnonzero((LZ @ v) % 2)],
             incols=all(k in COLS for k in S), ndata=sum(len(rep(k)) == 1 for k in S),
             supports=[rep(k) for k in S])
    colsS = [[d for d, _ in GS[k]] for k in S]
    colsU = [[d for d, _ in GU[k]] for k in S]
    r["seg_lift"] = feasible(colsS)[0]
    r["u11_lift"] = feasible(colsU)[0]
    syns = all_syndromes(colsU)
    assert (frozenset() in syns) == r["u11_lift"]
    mins = minimal_family(syns)
    univ = sorted(set().union(*[d for col in colsU for d in col]))
    hs = hitting_sets(mins)
    for A in hs:   # cross-check each IIS with the DP oracle
        assert not feasible(colsU, set(A))[0]
        assert all(feasible(colsU, set(A) - {d})[0] for d in A)
    r.update(n_min_family=len(mins), n_iis=len(hs), iis_sizes=sorted(collections.Counter(map(len, hs)).items()),
             minimum=min(map(len, hs)), maximum=max(map(len, hs)))
    r["minimum_sets"] = [[(d, int(COORD[d][0]), int(COORD[d][1])) for d in A] for A in hs if len(A) == r["minimum"]]
    r["del_asc"] = len(iis_deletion(colsU, univ))
    r["del_desc"] = len(iis_deletion(colsU, univ[::-1]))
    rng = random.Random(1000 + idx)
    rs = []
    for _ in range(10):
        o = univ[:]; rng.shuffle(o); rs.append(len(iis_deletion(colsU, o)))
    r["del_rand"] = rs
    # mechanism for each forced detector
    forced = [d for d in univ if all(d in s for s in syns)]
    mech = []
    for d in forced:
        zr, rnd = int(COORD[d][0]), int(COORD[d][1])
        touching = []
        for k, col, sup in zip(S, colsU, r["supports"]):
            qs = [q for q in sup if HZ[zr, q]]
            flips = sorted({int(d in t) for t in col})
            if not qs and flips == [0]: continue
            ent = dict(support=sup, data=len(sup) == 1, qubits=qs, nterms=len(col), flips=flips)
            if len(sup) > 1:
                xi = SUFFIX_OF[sup]
                ent["xcheck"] = xi
                ent["u11"] = [(q, cxU[(N + xi, q)][0], cxU[(q, N + NC + zr)][0]) for q in qs]   # (q, deposit, read)
                ent["seg"] = [(q, cxS[(N + xi, q)][0], cxS[(q, N + NC + zr)][0]) for q in qs]
            touching.append(ent)
        mech.append(dict(det=d, zcheck=zr, round=rnd, meas_u11=measU[N + NC + zr], touching=touching))
    r["forced"] = mech
    return r


if __name__ == "__main__":
    with Pool(2) as p:
        res = p.map(work, range(len(W10)), chunksize=4)
    json.dump(res, open(OUT + "/g3_stats.json", "w"), default=str)
    print("n", len(res), "all H=0", all(r["hz0"] for r in res), "all L!=0", all(r["lz"] for r in res),
          "all in ext code", all(r["incols"] for r in res), "distinct", len({tuple(sorted(W10[r['idx']])) for r in res}))
    print("ndata", collections.Counter(r["ndata"] for r in res))
    print("seg lifts", sum(r["seg_lift"] for r in res), "u11 lifts", sum(r["u11_lift"] for r in res))
    print("EXACT minimum size:", sorted(collections.Counter(r["minimum"] for r in res).items()))
    print("EXACT maximum irreducible size:", sorted(collections.Counter(r["maximum"] for r in res).items()))
    print("(min,max):", sorted(collections.Counter((r["minimum"], r["maximum"]) for r in res).items()))
    print("deletion asc:", sorted(collections.Counter(r["del_asc"] for r in res).items()))
    print("deletion desc:", sorted(collections.Counter(r["del_desc"] for r in res).items()))
    print("deletion rand (all 10 runs pooled):", sorted(collections.Counter(x for r in res for x in r["del_rand"]).items()))
    print("#forced detectors per logical:", sorted(collections.Counter(len(r["forced"]) for r in res).items()))
