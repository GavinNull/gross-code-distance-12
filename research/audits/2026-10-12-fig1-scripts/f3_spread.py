"""Spread of irreducible-set sizes: 300 random deletion orders per logical; group by minimum size."""
import collections, json, random, sys
from multiprocessing import Pool
sys.path.insert(0, __import__("os").path.dirname(__file__))
import f2_stats as F
from f_common import feasible, iis_deletion, R

coords = F.my_dem(F.circuit(F.p18_spec()))[1].get_detector_coordinates()


def work(args):
    idx, S = args
    cols = [[t[0] for t in F.G18[k]] for k in S]
    allds = sorted(set().union(*[d for col in cols for d in col]))
    fin = [d for d in allds if coords[d][1] == R]
    rng = random.Random(7 + idx)
    sizes = collections.Counter()
    for _ in range(300):
        o = allds[:]; rng.shuffle(o); sizes[len(iis_deletion(cols, o))] += 1
    finfeas = feasible(cols, set(fin))[0]
    fmin = None
    if not finfeas:
        # minimum among final-detector-only subsets: IHS restricted to finals
        sub = [[frozenset(d for d in t if d in set(fin)) for t in col] for col in cols]
        fmin = len(F.minimum_iis(sub))
    return idx, dict(sizes), len(allds), finfeas, fmin


if __name__ == "__main__":
    lists = F.load()
    r2 = [(i, S) for i, S in enumerate(lists) if sorted(F.supw.get(k, 99) for k in S) == [1] * 10 + [2]]
    with Pool(4) as p:
        out = p.map(work, r2, chunksize=4)
    prev = {o["idx"]: o for o in json.load(open("results/fig1-audit/f2_stats.json"))}
    bymin = collections.defaultdict(collections.Counter)
    for idx, sz, nd, ff, fmin in out:
        bymin[prev[idx]["n_min"]].update(sz.keys())
    print("irreducible sizes seen, grouped by minimum size:", {k: dict(v) for k, v in sorted(bymin.items())})
    print("overall max irreducible seen:", max(max(s) for _, s, *_ in out))
    print("#detectors touched per logical:", collections.Counter(nd for _, _, nd, _, _ in out))
    print("final-only detectors infeasible for all:", all(not ff for *_, ff, _ in out))
    print("minimum among final-only sets:", dict(collections.Counter(f for *_, f in out)))
    json.dump(out, open("results/fig1-audit/f3_spread.json", "w"))
