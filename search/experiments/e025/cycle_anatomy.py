"""E-025 structure: anatomy of the blocking (negative) cycles of a model-blocking circuit.
For every modelled logical: all negative directed cycles of its qubit graph (e025.cyc); for each, the per-node
intra-check drift (exit read time - entry read time, absolute times) and the 'time-travel' decomposition.
Reports, per logical, whether EVERY negative cycle uses a node of a given unit with drift <= -thr (i.e. the logical's
blocking depends on that unit having a long backward read inside one check)."""
import json, sys
from collections import Counter, defaultdict
import search.experiments.e021.nwfull as NF
from search.experiments.e025.cyc import pairing_classes, cycles_of, cycle_sum
from search.experiments.e025.exact_cp import make_family
from search.experiments.e024a.selftest import times_of_spec

spec = sys.argv[1]; sub = sys.argv[2] if len(sys.argv) > 2 else "1,2;0,3"
thr = int(sys.argv[3]) if len(sys.argv) > 3 else 10
d = json.load(open(spec)); P = d["period"]
F = make_family(sub)
from search.experiments.e024a.cegar import adapt
adapt(F)
t = times_of_spec(F, d, P)
recs, _ = NF.prepare_full(F, "XZ")
unit_of = [(it[0], it[1]) for it in F.items]


def drifts(terms):
    """per-unit drift contributions: D = sum s*(t_i2 - t_i1) telescopes into intra-check moves; we attribute
    -s*t_i1 and +s*t_i2 to the units of i1, i2 and sum per unit."""
    acc = defaultdict(int)
    for s, i1, i2 in terms:
        acc[unit_of[i2]] += s * t[i2]
        acc[unit_of[i1]] -= s * t[i1]
    return acc


need = Counter(); minS = Counter(); lens = Counter(); maxdrift_unit = Counter()
for k, r in enumerate(recs):
    allneg = []
    for cls in pairing_classes(r):
        cyc = cycles_of(F, r, cls)
        neg = [c for c in cyc if cycle_sum(c, t, P) < 0]
        allneg.append(neg)
    # a logical is blocked iff every pairing has a negative cycle; analyse pairing 0
    neg = allneg[0]
    assert neg, "circuit does not block logical %d" % k
    lens[min(len(c) for c in neg)] += 1
    # for each unit: does every negative cycle contain a drift of <= -thr attributed to this unit?
    per = [drifts(c) for c in neg]
    for u in F.units:
        if all(p.get(u, 0) <= -thr for p in per):
            need[f"{u[0]}{u[1]}"] += 1
    best = min(per, key=lambda p: min(p.values()))
    uu = min(best, key=best.get)
    maxdrift_unit[f"{uu[0]}{uu[1]}"] += 1
print("P", P, "logicals", len(recs))
print("min #terms of a negative cycle:", sorted(lens.items()))
print(f"logicals for which EVERY negative cycle has a unit drift <= -{thr} on unit:", dict(need))
print("unit carrying the most backward drift in the 'best' cycle:", dict(maxdrift_unit))
