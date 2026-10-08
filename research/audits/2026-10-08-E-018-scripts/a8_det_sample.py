"""Audit E-018 (a8): determinism criterion vs stim on uniformly sampled colour-uniform P=9 schedules: enumerate all
conflict-free ones (no determinism filter), sample n with criterion=det and n with criterion=nondet, check stim; inject
model witnesses (2 lifting single-hook logicals per det schedule) and one-fault-removed negative controls.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-08-E-018-scripts/a8_det_sample.py P n seed
"""
import itertools, json, random, sys, collections
import numpy as np
P = int(sys.argv[1]); n = int(sys.argv[2]); seed = int(sys.argv[3])
sys.argv = [sys.argv[0], str(P), "0", str(seed)]
sys.path.insert(0, "research/audits/2026-10-08-E-018-scripts")
import a4_validate as A
from a1_common import xo, zo, xcol, zcol
from a3_model import single_hook_logicals, lifts
rng = random.Random(seed)
classes = A.classes
offs = list(itertools.combinations(range(1, P - 1), 6))
opts = {c: [(s, o) for s in range(P) for o in offs] for c in classes}
opts[("X", 0)] = [(0, o) for o in offs]
# conflict-free enumeration (pairwise class compatibility on data conflicts only)
touch = collections.defaultdict(list)
for i, o in enumerate(xo):
    for k, q in enumerate(o): touch[q].append((A.cls_of[("X", i)], k))
for j, o in enumerate(zo):
    for k, q in enumerate(o): touch[q].append((A.cls_of[("Z", j)], k))
conf = collections.defaultdict(set)
for q, l in touch.items():
    for (X1, p1), (X2, p2) in itertools.combinations(l, 2):
        if X1 != X2: conf[(X1, X2)].add((p1, p2))
def compat(Ac, Bc):
    oa, ob = opts[Ac], opts[Bc]
    sa = np.array([s for s, _ in oa]); sb = np.array([s for s, _ in ob])
    Oa = np.array([o for _, o in oa]); Ob = np.array([o for _, o in ob])
    M = np.ones((len(oa), len(ob)), bool)
    for pa, pb in conf.get((Ac, Bc), set()) | {(b, a) for a, b in conf.get((Bc, Ac), set())}:
        M &= ((sa + Oa[:, pa])[:, None] - (sb + Ob[:, pb])[None, :]) % P != 0
    return M
C = {(a, b): compat(classes[a], classes[b]) for a in range(6) for b in range(a + 1, 6)}
# randomised DFS sampling of conflict-free schedules (no determinism filter), until n of each criterion class
def sample():
    cand = [np.ones(len(opts[c]), bool) for c in classes]; ch = []
    for k in range(6):
        nz = np.nonzero(cand[k])[0]
        if not len(nz): return None
        oi = int(rng.choice(list(nz))); ch.append(oi)
        for b in range(k + 1, 6): cand[b] = cand[b] & C[(k, b)][oi]
    return ch
dets, nons, sols = [], [], []
tries = 0
while (len(dets) < n or len(nons) < n) and tries < 200000:
    tries += 1
    ch = sample()
    if ch is None: continue
    sols.append(ch)
    sched = A.expand({c: opts[c][o] for c, o in zip(classes, ch)})
    d = A.my_det(sched)
    if d and len(dets) < n: dets.append(sched)
    if not d and len(nons) < n: nons.append(sched)
out = {"P": P, "sampled_conflict_free": len(sols), "tries": tries, "criterion_det": len(dets), "criterion_nondet": len(nons),
       "stim_agree": 0, "stim_disagree": 0, "inject_ok": 0, "inject_bad": 0, "neg_fired": 0, "neg_total": 0}
LOG = single_hook_logicals("X")
for group, want in ((dets, True), (nons, False)):
    for sched in rng.sample(group, min(n, len(group))):
        ok = A.stim_det(A.to_spec(sched)) == want
        out["stim_agree" if ok else "stim_disagree"] += 1
        if want:
            lif = [L for L in LOG if lifts(sched, P, L, "Z")]
            for L in rng.sample(lif, min(2, len(lif))):
                nd, no = A.inject(sched, P, L)
                out["inject_ok" if (nd == 0 and no > 0) else "inject_bad"] += 1
                nd2, _ = A.inject(sched, P, L, drop=("hook", L[1]))
                out["neg_total"] += 1; out["neg_fired"] += nd2 > 0
print(json.dumps(out))
json.dump(out, open(f"results/E-018-audit/a8_P{P}_s{seed}.json", "w"))
