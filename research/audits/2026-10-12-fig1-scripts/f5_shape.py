"""Shape of the minimum conflicting sets: distinct checks, columns per check (degree), cycle test."""
import collections, json, sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
import f2_stats as F
coords = F.my_dem(F.circuit(F.p18_spec()))[1].get_detector_coordinates()
lists = F.load()
out = json.load(open("results/fig1-audit/f2_stats.json"))
shape = collections.Counter()
for o in out:
    S = lists[o["idx"]]
    A = set(o["minset"])
    chk = sorted(int(coords[d][0]) for d in A)
    # column-check incidence: column touches check if any of its terms flips a detector of A on that check
    inc = {}
    for ci, k in enumerate(S):
        cs = {int(coords[d][0]) for t in F.G18[k] for d in t[0] if d in A}
        if cs: inc[ci] = cs
    deg = collections.Counter(c for cs in inc.values() for c in cs)
    cycle = all(v == 2 for v in deg.values()) and all(len(cs) == 2 for cs in inc.values()) and len(inc) == len(set(chk))
    shape[(len(A), len(set(chk)), tuple(sorted(deg.values())), tuple(sorted(len(c) for c in inc.values())), cycle)] += 1
for k, v in sorted(shape.items()): print("size,#checks,check-degrees,column-degrees,simple-cycle:", k, v)
# support-based incidence (P18 realisation of the hook = suffix of a P18 X-check order with the same key)
from f_common import key_of, xorders, HZ
suf = {}
for o in xorders(F.p18_spec()):
    for s in range(1, 6): suf.setdefault(key_of(tuple(o[s:])), tuple(o[s:]))
sh2 = collections.Counter()
for o in out:
    S = lists[o["idx"]]
    chk = {int(coords[d][0]) for d in o["minset"]}
    sup = [suf[k] if F.supw[k] == 2 else [q for q in range(144) if key_of((q,)) == k][:1] for k in S]
    deg = collections.Counter(r for s in sup for r in chk for q in s if HZ[r, q])
    coldeg = [sum(1 for r in chk if any(HZ[r, q] for q in s)) for s in sup]
    sh2[(len(chk), tuple(sorted(deg.values())), tuple(sorted(c for c in coldeg if c)))] += 1
for k, v in sorted(sh2.items()): print("support view #checks, errors-per-check, checks-per-column:", k, v)
