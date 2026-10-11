"""E-025 structure: in a model-blocking circuit, for every modelled logical take ALL its negative cycles and record,
per node (check) on the cycle, the (unit, entry label -> exit label, drift = t(exit) - t(entry)).  Aggregates for each
unit which label pairs are used with large backward drift, and how many logicals have NO negative cycle avoiding a
backward drift <= -thr on a given unit (= logicals that need that unit's long backward read)."""
import json, sys
from collections import Counter, defaultdict
import search.experiments.e021.nwfull as NF
from search.experiments.e021.mono import LAB
from search.experiments.e024a.cegar import adapt
from search.experiments.e024a.selftest import times_of_spec
from search.experiments.e025.cyc import pairing_classes, cycle_sum
from search.experiments.e025.exact_cp import make_family
import search.experiments.e025.cyc as CY

spec = sys.argv[1]; thr = int(sys.argv[2]) if len(sys.argv) > 2 else 12
d = json.load(open(spec)); P = d["period"]
F = make_family("1,2;0,3"); adapt(F)
t = times_of_spec(F, d, P)
recs, _ = NF.prepare_full(F, "XZ")
lab_of = {i: it[2] for i, it in enumerate(F.items)}
unit_of = {i: (it[0], it[1]) for i, it in enumerate(F.items)}


def node_moves(terms):
    """per item, net sign (+1 = exit read, -1 = entry read) -> group by unit-instance: we pair entry/exit per term
    structure: term (s,i1,i2) contributes +s*t_i2 - s*t_i1.  Collect +items and -items, then pair within a unit."""
    plus, minus = [], []
    for s, i1, i2 in terms:
        (plus if s == 1 else minus).append(i2)
        (minus if s == 1 else plus).append(i1)
    return plus, minus


used = defaultdict(Counter)
need = Counter()
for k, r in enumerate(recs):
    cls = next(pairing_classes(r))
    cyc = CY.cycles_of(F, r, cls)
    neg = [c for c in cyc if cycle_sum(c, t, P) < 0]
    assert neg
    per_cycle_units = []
    for c in neg:
        plus, minus = node_moves(c)
        # per unit: total drift sum(t plus) - sum(t minus) restricted to items of that unit; pairs (entry->exit)
        dd = defaultdict(int)
        for i in plus: dd[unit_of[i]] += t[i]
        for i in minus: dd[unit_of[i]] -= t[i]
        per_cycle_units.append(dd)
        # label pairs with big backward drift: match each minus item (entry) with a plus item (exit) of same unit
        pu = defaultdict(list); mu = defaultdict(list)
        for i in plus: pu[unit_of[i]].append(i)
        for i in minus: mu[unit_of[i]].append(i)
        for u in pu:
            for ie, ix in zip(sorted(mu[u], key=lambda i: t[i]), sorted(pu[u], key=lambda i: t[i])):
                pass
    for u in F.units:
        if all(dd.get(u, 0) <= -thr for dd in per_cycle_units):
            need[f"{u[0]}{u[1]}"] += 1
    # best cycle (most negative S): record per unit drift
    best = min(neg, key=lambda c: cycle_sum(c, t, P))
    plus, minus = node_moves(best)
    for u in F.units:
        ip = [i for i in plus if unit_of[i] == u]; im = [i for i in minus if unit_of[i] == u]
        if ip or im:
            dr = sum(t[i] for i in ip) - sum(t[i] for i in im)
            if dr <= -thr:
                used[f"{u[0]}{u[1]}"][(r["kind"], "+".join(LAB[lab_of[i]] for i in ip), "-".join(LAB[lab_of[i]] for i in im))] += 1
print(f"P={P}: logicals whose EVERY negative cycle needs drift <= -{thr} from unit:", dict(need))
for u, c in used.items():
    print(u, c.most_common(6))
