"""Audit E-018 (a3_enum): EXHAUSTIVE enumeration of colour-uniform (24-translation-symmetric) single-ancilla schedules
of period P with Fig. 12 per-check CNOT orders (pipelining and ancilla gaps allowed, evaluator rules
0 < off(cnot) < off(meas) < P), data-conflict-free, deterministic (own criterion, validated against stim in a4),
and for each one decide with the own bulk model (a3_model.lifts) whether ALL 360 Z-basis single-hook logicals are
blocked.  Independent of design3.py's path-certificate encoding.

Global time shift: class X-colour-0 has s = 0 (everything depends only on time differences).
    PYTHONPATH=.:tests uv run python research/audits/2026-10-08-E-018-scripts/a3_enum.py P [basis]
"""
import itertools, json, sys, time, collections
import numpy as np
sys.path.insert(0, "research/audits/2026-10-08-E-018-scripts")
from a1_common import xo, zo, xcol, zcol
from a3_model import single_hook_logicals, lifts

P = int(sys.argv[1]); basis = sys.argv[2] if len(sys.argv) > 2 else "Z"
SPLIT = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (1, 0)   # (mod, idx) on class-1 option
OUT = "results/E-018-audit"
classes = [("X", 0), ("X", 1), ("X", 2), ("Z", 0), ("Z", 1), ("Z", 2)]
cls_of = {("X", i): ("X", xcol[i]) for i in range(72)} | {("Z", j): ("Z", zcol[j]) for j in range(72)}
offsets = list(itertools.combinations(range(1, P - 1), 6))
opts = {c: [(s, o) for s in range(P) for o in offsets] for c in classes}
opts[("X", 0)] = [(0, o) for o in offsets]

# data-conflict position pairs between classes, and determinism quadruples
touch = collections.defaultdict(list)
for i, o in enumerate(xo):
    for k, q in enumerate(o): touch[q].append((cls_of[("X", i)], k))
for j, o in enumerate(zo):
    for k, q in enumerate(o): touch[q].append((cls_of[("Z", j)], k))
conf = collections.defaultdict(set)
for q, l in touch.items():
    for (A, pa), (B, pb) in itertools.combinations(l, 2):
        assert not (A == B and pa == pb), "two same-class checks at same position on one qubit"
        if A == B:
            continue        # distinct offsets within one option -> never equal mod P (offsets < P)
        conf[(A, B)].add((pa, pb))
det = collections.defaultdict(set)
for i, oi in enumerate(xo):
    for j, oj in enumerate(zo):
        sh = sorted(set(oi) & set(oj))
        if sh:
            assert len(sh) == 2
            u, v = sh
            det[(cls_of[("X", i)], cls_of[("Z", j)])].add((oi.index(u), oj.index(u), oi.index(v), oj.index(v)))

def compat(A, B):
    oa, ob = opts[A], opts[B]
    M = np.ones((len(oa), len(ob)), bool)
    sa = np.array([s for s, _ in oa]); sb = np.array([s for s, _ in ob])
    Oa = np.array([o for _, o in oa]); Ob = np.array([o for _, o in ob])
    for pa, pb in conf.get((A, B), ()) | {(b, a) for a, b in conf.get((B, A), ())}:
        ta = sa + Oa[:, pa]; tb = sb + Ob[:, pb]
        M &= (ta[:, None] - tb[None, :]) % P != 0
    if A[0] == "X" and B[0] == "Z":
        for pu, qu, pv, qv in det.get((A, B), ()):
            du = (sa + Oa[:, pu])[:, None] - (sb + Ob[:, qu])[None, :]
            dv = (sa + Oa[:, pv])[:, None] - (sb + Ob[:, qv])[None, :]
            M &= (du // P) == (dv // P)
    return M

t0 = time.time()
C = {(a, b): compat(classes[a], classes[b]) for a in range(6) for b in range(6) if a < b}
LOG = single_hook_logicals("X" if basis == "Z" else "Z")
nsol = nblock_all = 0
min_lift = 10 ** 9; hist = collections.Counter(); examples = []

def rec(k, chosen, cand):
    global nsol, nblock_all, min_lift
    if k == 6:
        nsol += 1
        sched = {}
        for ci, oi in zip(classes, chosen):
            s, o = opts[ci][oi]
            for chk, cc in cls_of.items():
                if cc == ci: sched[chk] = (s, o)
        nl = 0
        for L in LOG:
            if lifts(sched, P, L, basis):
                nl += 1
                if nl > 0 and min_lift <= 0: break
                break                       # one lifting logical suffices: not blocked
        if nl == 0:
            nblock_all += 1
            examples.append([opts[c][o] for c, o in zip(classes, chosen)])
        return
    for oi in np.nonzero(cand[k])[0]:
        if k == 1 and oi % SPLIT[0] != SPLIT[1]:
            continue
        if k == 1:
            print("progress", int(oi), nsol, nblock_all, round(time.time() - t0), flush=True)
        nc = list(cand)
        ok = True
        for b in range(k + 1, 6):
            nc[b] = cand[b] & C[(k, b)][oi]
            if not nc[b].any(): ok = False; break
        if ok:
            rec(k + 1, chosen + [int(oi)], nc)

rec(0, [], [np.ones(len(opts[c]), bool) for c in classes])
res = {"P": P, "basis": basis, "options_per_class": len(opts[("X", 1)]), "legal_deterministic_schedules": nsol,
       "block_all_single_hook": nblock_all, "examples": examples[:5], "sec": round(time.time() - t0, 1),
       "n_logicals": len(LOG)}
print(json.dumps(res))
res["split"] = SPLIT
json.dump(res, open(f"{OUT}/a3_enum_P{P}_{basis}_split{SPLIT[1]}of{SPLIT[0]}.json", "w"))
