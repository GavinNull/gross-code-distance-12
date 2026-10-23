"""Classify every forced (single-detector) conflict of the 144 logicals from g3_stats.json; translation orbits."""
import collections, json, sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from g_common import *
res = json.load(open(OUT + "/g3_stats.json"))
pat = collections.Counter(); per_logical = collections.Counter(); checks_per = collections.Counter()
rounds_pair = collections.Counter(); asc_vs = collections.Counter()
for r in res:
    kinds = []
    zs = collections.defaultdict(set)
    for f in r["forced"]:
        zs[f["zcheck"]].add(f["round"])
        T = f["touching"]
        # every touching column: hook, single term, deterministic flip of this detector
        desc = []
        ok = True
        for e in T:
            if e["data"] or e["nterms"] != 1: ok = False
        hooks = [e for e in T if not e["data"]]
        datas = [e for e in T if e["data"]]
        qs = sorted(q for e in hooks for q in e["qubits"])
        sides = [dep > rd for e in hooks for (q, dep, rd) in e["u11"]]
        segsides = [dep > rd for e in hooks for (q, dep, rd) in e["seg"]]
        key = (f"round{f['round']}", f"{len(hooks)}hook", f"{len(datas)}data", "same-q" if len(set(qs)) == 1 else f"{len(set(qs))}q",
               f"u11 after-read {sum(sides)}/{len(sides)}", f"seg after-read {sum(segsides)}/{len(segsides)}",
               "data cols flip?" + str(sorted({tuple(e['flips']) for e in datas})))
        pat[key] += 1
        kinds.append(key)
    per_logical[(len(r["forced"]), tuple(sorted(len(v) for v in zs.values())))] += 1
    checks_per[len(zs)] += 1
    # was the asc-deletion core one of the forced detectors' check?  pattern of the logical's "first" forced detector
print("forced-detector patterns (over all forced detectors of all 144 logicals):")
for k, v in sorted(pat.items(), key=lambda x: -x[1]): print(v, k)
print("per logical (#forced, rounds per check):", per_logical)
print("Z checks with forced detectors per logical:", checks_per)
# same-qubit vs two-qubit per logical: does every logical have at least one same-qubit straddle?
sq = collections.Counter()
for r in res:
    ty = set()
    for f in r["forced"]:
        hooks = [e for e in f["touching"] if not e["data"]]
        qs = {q for e in hooks for q in e["qubits"]}
        ty.add("same" if len(qs) == 1 else "two")
    sq[tuple(sorted(ty))] += 1
print("per logical, kinds of forced checks present:", sq)
# translation orbits of the 144 (supports)
_, W10 = load_w10()
canon = {i: tuple(sorted(tuple(x) for x in r["supports"])) for i, r in enumerate(res)}
COLS = ext_columns(U11)
keyset = {tuple(sorted(W10[r["idx"]])): r["idx"] for r in res}
orb = {}
for r in res:
    i = r["idx"]
    if i in orb: continue
    S = [tuple(x) for x in r["supports"]]
    members = set()
    for a in range(12):
        for b in range(6):
            T = tuple(sorted(key_of(tuple(sorted(translate(q, a, b) for q in s))) for s in S))
            assert T in keyset, "translated logical not in list"
            members.add(keyset[T])
    for m in members: orb[m] = i
O = collections.defaultdict(list)
byidx = {r["idx"]: r for r in res}
for m, o in orb.items(): O[o].append(m)
for o, ms in O.items():
    print("orbit", o, "size", len(ms), "#forced", collections.Counter(len(byidx[m]["forced"]) for m in ms),
          "del_asc", sorted(collections.Counter(byidx[m]["del_asc"] for m in ms).items()),
          "del_desc", sorted(collections.Counter(byidx[m]["del_desc"] for m in ms).items()))
