"""Audit E-024b (u1): independent replay of the d_ext >= 11 uniqueness enumeration (dextsat / dextsat2).
No DFS is trusted: every recorded witness is re-verified from scratch (each column support is a genuine column of
THAT assignment's extended code: a data qubit or a residual set of some check's order; the columns' (H,L) images
sum to H = 0, L != 0; <= 10 distinct columns).  Then an own CNF is built from the verified witnesses only
(per-colour one-hot types; for every one of the 72 translates of a witness: "not all of its hook columns present",
present(key) <= x[colour(a)][t] for every realisation (check a, label set U in residuals of t)); recorded survivors /
'known' assignments are blocked with all their translation images after checking that their extended code IS a
translate of Fig. 12's.  UNSAT => every per-colour type assignment of that colouring/side other than Fig. 12
translates has a (verified) weight <= 10 extended logical.
Also: own bad-triple witnesses (CP-SAT) and own 45-type enumeration; own subgroup list.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-11-E-024b-scripts/u1_dext.py
"""
import glob, itertools, json, sys, time
sys.path.insert(0, "tests")
import numpy as np
from ortools.sat.python import cp_model
from pysat.solvers import Cadical153
from pysat.formula import IDPool
from evaluators.tasks import build_code, get_task
from search.experiments.e021.mono import table, fig12_labels      # label table: verified below
from search.experiments.e024b.common import types as their_types, ext_general, bad_triples as their_bad

RD = "results/E-024b-gross12-other-classes"
code, _ = build_code(get_task("gross-dcirc"), None)
HX, HZ, LX, LZ = [np.asarray(m, np.uint8) % 2 for m in (code.HX, code.HZ, code.LX, code.LZ)]
T = table()
info = {}
for kind, H in (("X", HX), ("Z", HZ)):
    for i in range(72):
        assert sorted(T[kind][i]) == sorted(np.nonzero(H[i])[0].tolist())


def trq(ga, gb):          # own translation on data qubits / checks
    p = np.array([((i // 6 + ga) % 12) * 6 + (i % 6 + gb) % 6 for i in range(72)])
    return p, np.concatenate([p, p + 72])


TR = [trq(ga, gb) for ga in range(12) for gb in range(6)]
for pr, pq in TR:      # translations preserve labels => code automorphisms acting label-wise
    for kind in "XZ":
        for i in range(72):
            assert all(pq[T[kind][i][l]] == T[kind][pr[i]][l] for l in range(6))
HL = {"X": (HZ, LZ), "Z": (HX, LX)}


def key(kind, qs):
    H, L = HL[kind]; v = np.zeros(144, np.uint8); v[list(qs)] = 1
    return ((H @ v) % 2).astype(np.uint8).tobytes() + ((L @ v) % 2).astype(np.uint8).tobytes()


def vec_of_key(k):
    return np.frombuffer(k, np.uint8)


# ---- bad triples: own CP-SAT witness (triple column at check 0 + <= 9 data columns = logical)
def triple_witness(kind, Tl):
    H, L = HL[kind]
    v = np.zeros(144, int); v[[T[kind][0][l] for l in Tl]] = 1
    m = cp_model.CpModel(); e = [m.NewBoolVar("") for _ in range(144)]
    m.Add(sum(e) <= 9)
    for row in H:
        idx = np.nonzero(row)[0]; k = m.NewIntVar(0, 6, "")
        m.Add(sum(e[j] for j in idx) + int(v[idx].sum()) == 2 * k)
    bs = []
    for row in L:
        idx = np.nonzero(row)[0]; k = m.NewIntVar(0, 80, ""); b = m.NewBoolVar("")
        m.Add(sum(e[j] for j in idx) + int(v[idx].sum()) == 2 * k + b); bs.append(b)
    m.AddBoolOr(bs)
    s = cp_model.CpSolver(); s.parameters.num_workers = 1; s.parameters.max_time_in_seconds = 120
    st = s.Solve(m)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        ev = np.array([s.Value(x) for x in e]); w = (v + ev) % 2
        assert not ((H @ w) % 2).any() and ((L @ w) % 2).any()
        return int(ev.sum())
    return s.StatusName(st)


bad = {}
for kind in "XZ":
    tb = their_bad(kind); bad[kind] = set()
    rec = {}
    for Tl in itertools.combinations(range(6), 3):
        if frozenset(Tl) in tb:
            r = triple_witness(kind, Tl); rec["".join(map(str, Tl))] = r
            if isinstance(r, int): bad[kind].add(frozenset(Tl)); bad[kind].add(frozenset(range(6)) - frozenset(Tl))
    info[f"bad_triples_{kind}"] = {"theirs": len(tb), "own_witnessed": len(bad[kind]), "data_weights": rec}
    print(kind, info[f"bad_triples_{kind}"], flush=True)


def tkey(o):
    P1, Tt, P3 = frozenset(o[:2]), frozenset(o[:3]), frozenset(o[4:])
    a = (tuple(sorted(P1)), tuple(sorted(Tt)), tuple(sorted(P3)))
    b = (tuple(sorted(P3)), tuple(sorted(frozenset(range(6)) - Tt)), tuple(sorted(P1)))
    return min(a, b)


def resid(o):           # label residual sets of sizes 2,3,4 (size 5/1 = data-equivalent)
    return {frozenset(o[2:]), frozenset(o[3:]), frozenset(o[4:])}


MYTYPES = {}
for kind in "XZ":
    ks = {}
    for o in itertools.permutations(range(6)):
        if frozenset(o[:3]) in bad[kind]: continue
        ks.setdefault(tkey(o), o)
    MYTYPES[kind] = ks
    th = {tkey(o) for o in their_types(kind)}
    info[f"types_{kind}"] = {"own_allowed": len(ks), "theirs": len(th), "equal": th == set(ks),
                             "all_classes": len({tkey(o) for o in itertools.permutations(range(6))})}
    print(kind, info[f"types_{kind}"], flush=True)

# ---- realisations and data keys
REAL, DKEY = {}, {}
for kind in "XZ":
    DKEY[kind] = {key(kind, [q]) for q in range(144)}
    R = {}
    for a in range(72):
        for size in (2, 3, 4):
            for U in itertools.combinations(range(6), size):
                R.setdefault(key(kind, [T[kind][a][l] for l in U]), []).append((a, frozenset(U)))
    REAL[kind] = R
F12 = fig12_labels()


def ext_keyset(kind, labs):
    ks = set(DKEY[kind])
    for a in range(72):
        for U in resid(labs[a]):
            ks.add(key(kind, [T[kind][a][l] for l in U]))
    return frozenset(ks)


F12SETS = {}
for kind in "XZ":
    sets = set()
    for pr, pq in TR:
        lab1 = [None] * 72
        for i in range(72): lab1[pr[i]] = F12[kind][i]
        sets.add(ext_keyset(kind, lab1))
    F12SETS[kind] = sets


def colourings():
    G = [(a, b) for a in range(12) for b in range(6)]
    out = []
    for m, al, be in ((2, 1, 0), (2, 0, 1), (2, 1, 1), (3, 1, 0), (3, 0, 1), (3, 1, 1), (3, 1, 2)):
        colv = [(al * (i // 6) + be * (i % 6)) % m for i in range(72)]
        out.append((f"m{m}_{al}{be}", colv, f"{RD}/dext_{{k}}_m{m}_{al}{be}.jsonl"))
    for sub in ("0,1;4,0", "0,2;2,0", "0,2;2,1", "0,0;1,0", "0,0;1,1", "0,0;1,2", "0,0;1,3", "0,0;1,4", "0,0;1,5",
                "0,0;3,1", "0,0;3,2", "0,1;6,0", "0,3;2,0", "0,3;2,1", "0,3;2,2", "0,2;4,0", "0,3;3,0"):
        gens = [tuple(map(int, g.split(","))) for g in sub.split(";")]
        Hs = {(0, 0)}
        while True:
            N = Hs | {((h[0] + g[0]) % 12, (h[1] + g[1]) % 6) for h in Hs for g in gens}
            if N == Hs: break
            Hs = N
        colv = [-1] * 72; m = 0
        for i in range(72):
            if colv[i] >= 0: continue
            a, b = divmod(i, 6)
            for h in Hs: colv[((a + h[0]) % 12) * 6 + (b + h[1]) % 6] = m
            m += 1
        out.append((sub, colv, f"{RD}/dext2_{{k}}_{sub.replace(';', '_').replace(',', '')}.jsonl"))
    return out


summary = {}
t00 = time.time()
for name_, colv, pat in colourings():
    m = max(colv) + 1
    perms = set()
    for pr, _ in TR:
        p = [None] * m
        for i in range(72):
            assert p[colv[i]] in (None, colv[pr[i]]); p[colv[i]] = colv[pr[i]]
        perms.add(tuple(p))
    for kind in "XZ":
        fn = pat.format(k=kind)
        TY = their_types(kind)
        mykeys = list(MYTYPES[kind]); myidx = {k: n for n, k in enumerate(mykeys)}
        conv = [myidx[tkey(o)] for o in TY]
        nt = len(mykeys)
        RS = [resid(MYTYPES[kind][k]) for k in mykeys]
        pool = IDPool(); S = Cadical153()
        x = [[pool.id(("x", c, t)) for t in range(nt)] for c in range(m)]
        for c in range(m):
            S.add_clause(x[c])
            for t1, t2 in itertools.combinations(range(nt), 2): S.add_clause([-x[c][t1], -x[c][t2]])
        pres = {}

        def present(k):
            if k not in pres:
                p = pool.id(("p", k))
                for a_, U in REAL[kind].get(k, []):
                    for t in range(nt):
                        if U in RS[t]: S.add_clause([-x[colv[a_]][t], p])
                pres[k] = p
            return pres[k]
        st = {"records": 0, "witness_ok": 0, "witness_bad": 0, "blocked": 0, "blocked_is_fig12": 0, "max_w": 0}
        for line in open(fn):
            r = json.loads(line); st["records"] += 1
            asg = [conv[t] for t in r["assign"]]
            labs = [MYTYPES[kind][mykeys[asg[colv[i]]]] for i in range(72)]   # canonical rep order of the type
            if r.get("survivor") or r.get("known"):
                st["blocked"] += 1
                st["blocked_is_fig12"] += int(ext_keyset(kind, labs) in F12SETS[kind])
                for p in perms: S.add_clause([-x[p[c]][asg[c]] for c in range(m)])
                continue
            E = ext_general(kind, [tuple(TY[r["assign"][colv[i]]]) for i in range(72)])
            sups = [E["col_sups"][j][0] for j in r["witness"]]
            # verify: each support is a column of THIS assignment's extended code; logical; <= 10 distinct keys
            ok = len(sups) <= 10 and len({key(kind, s) for s in sups}) == len(sups)
            acc = np.zeros(len(next(iter(DKEY[kind]))), np.uint8)
            hooks = []
            eks = ext_keyset(kind, labs)
            for s in sups:
                k = key(kind, s); acc ^= vec_of_key(k)
                if len(s) == 1 or k in DKEY[kind]: continue
                genuine = k in eks        # column of THIS assignment's extended code (key = column identity)
                ok &= genuine; hooks.append(s)
            nH = 72
            ok &= (not acc[:nH].any()) and bool(acc[nH:].any())
            if not ok:
                st["witness_bad"] += 1; continue
            st["witness_ok"] += 1; st["max_w"] = max(st["max_w"], len(sups))
            own_violated = None
            for gi, (pr, pq) in enumerate(TR):
                ks = [key(kind, [int(pq[q]) for q in s]) for s in hooks]
                S.add_clause(sorted({-present(k) for k in ks}))
        res = S.solve()
        st["sat_after_replay"] = bool(res)
        if res:
            md = set(l for l in S.get_model() if l > 0)
            st["model"] = [next(t for t in range(nt) if x[c][t] in md) for c in range(m)]
        summary[f"{name_}_{kind}"] = st
        print(name_, kind, st, round(time.time() - t00), flush=True)
info["replay"] = summary
info["all_unsat"] = all(not v["sat_after_replay"] for v in summary.values())
info["all_witness_ok"] = all(v["witness_bad"] == 0 for v in summary.values())
info["all_blocked_fig12"] = all(v["blocked"] == v["blocked_is_fig12"] for v in summary.values())
print({k: info[k] for k in ("all_unsat", "all_witness_ok", "all_blocked_fig12")})
json.dump(info, open("results/E-024b-audit/u1_dext.json", "w"), indent=1, default=str)
