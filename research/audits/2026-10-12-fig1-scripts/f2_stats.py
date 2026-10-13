"""Claim 2: IIS sizes over all '10 data + 1 length-2 hook' weight-11 logicals (Z basis, R=1, P18).
Own column classification, own DEM, own DP oracle; three notions: ascending-id deletion (as paper script),
minimum cardinality (implicit hitting set, exact), and deletion under random orders (spread of irreducible sizes)."""
import collections, json, random, sys, time
from multiprocessing import Pool
sys.path.insert(0, __import__("os").path.dirname(__file__))
from f_common import *

NRAND = int(sys.argv[1]) if len(sys.argv) > 1 else 20


def load():
    sys.path.insert(0, ROOT + "/research/audits/2026-10-10-E-021-scripts")
    from b_common import audit018_lists     # input data only: E-018 audit's 4224 list (column-key tuples)
    lists, _ = audit018_lists("X")
    return lists


f12 = fig12_spec()
supw = {}
for q in range(N):
    k = key_of((q,)); supw[k] = min(supw.get(k, 99), 1)
for o in xorders(f12):
    for s in range(1, 6):
        k = key_of(tuple(o[s:])); supw[k] = min(supw.get(k, 99), 6 - s)
_, _, G18 = my_dem(circuit(p18_spec()))
_, _, G12 = my_dem(circuit(f12))


def work(args):
    idx, S = args
    cols = [[t[0] for t in G18[k]] for k in S]
    assert not feasible(cols)[0]
    allds = sorted(set().union(*[d for col in cols for d in col]))
    asc = iis_deletion(cols, allds)
    mn = minimum_iis(cols)
    rng = random.Random(1000 + idx)
    rs = []
    for _ in range(NRAND):
        o = allds[:]; rng.shuffle(o); rs.append(len(iis_deletion(cols, o)))
    desc = iis_deletion(cols, allds[::-1])
    cols12 = [[t[0] for t in G12[k]] for k in S]
    return dict(idx=idx, asc=asc, n_asc=len(asc), n_min=len(mn), minset=mn, n_desc=len(desc),
                rand=sorted(rs), fig12_lifts=feasible(cols12)[0])


if __name__ == "__main__":
    lists = load()
    assert len(lists) == 4224, len(lists)
    # sanity on every logical: columns sum to H-syndrome 0, nonzero L
    for S in lists:
        acc = np.zeros(72 + LZ.shape[0], np.uint8)
        for k in S: acc ^= np.frombuffer(k, np.uint8)
        assert not acc[:72].any() and acc[72:].any()
    r2 = [(i, S) for i, S in enumerate(lists) if sorted(supw.get(k, 99) for k in S) == [1] * 10 + [2]]
    shapes = collections.Counter(tuple(sorted(supw.get(k, 99) for k in S)) for S in lists)
    print("shapes:", {str(k): v for k, v in shapes.items()})
    print("n '10 data + r2':", len(r2), " first idx:", r2[0][0])
    t0 = time.time()
    with Pool(4) as p:
        out = p.map(work, r2, chunksize=4)
    print("time", time.time() - t0)
    C = lambda f: dict(sorted(collections.Counter(f(o) for o in out).items()))
    print("ascending-id deletion sizes:", C(lambda o: o["n_asc"]))
    print("descending-id deletion sizes:", C(lambda o: o["n_desc"]))
    print("minimum sizes:", C(lambda o: o["n_min"]))
    print("random-order deletion: overall min/max:", min(min(o["rand"]) for o in out), max(max(o["rand"]) for o in out))
    print("per-logical (min over rand) dist:", C(lambda o: min(o["rand"])), " (max over rand):", C(lambda o: max(o["rand"])))
    print("asc==min count:", sum(o["n_asc"] == o["n_min"] for o in out))
    print("fig12 lifts all 360:", all(o["fig12_lifts"] for o in out))
    # what detectors make up the minimum sets: final vs round, how many checks
    coords = my_dem(circuit(p18_spec()))[1].get_detector_coordinates()
    print("minimum sets all-final:", collections.Counter(all(coords[d][1] == R for d in o["minset"]) for o in out))
    print("ascending sets all-final:", collections.Counter(all(coords[d][1] == R for d in o["asc"]) for o in out))
    json.dump(out, open("results/fig1-audit/f2_stats.json", "w"), default=str)
