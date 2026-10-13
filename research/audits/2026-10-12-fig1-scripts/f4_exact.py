"""Exact: all achievable syndromes (numpy), inclusion-minimal family, then exact min and max IIS
(IIS = minimal hitting set of the minimal-syndrome family) via CP-SAT, plus total count of IIS by enumeration."""
import collections, json, sys
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, __import__("os").path.dirname(__file__))
import f2_stats as F
from ortools.sat.python import cp_model


def fam_of(cols):
    allds = sorted(set().union(*[d for col in cols for d in col]))
    pos = {d: i for i, d in enumerate(allds)}
    st = np.zeros(1, np.uint64)
    for col in cols:
        ms = np.array([sum(1 << pos[d] for d in t) for t in col], np.uint64)
        st = np.unique((st[:, None] ^ ms[None, :]).ravel())
    assert 0 not in set(st.tolist())
    # inclusion-minimal (vectorised: repeatedly take a min-popcount state, drop its supersets)
    pc = np.array([bin(int(x)).count("1") for x in st])
    mins = []
    while st.size:
        m = st[np.argmin(pc)]
        mins.append(int(m))
        keep = (st & m) != m
        st, pc = st[keep], pc[keep]
    return allds, mins


def solve(allds, mins, sense, forbid=()):
    n = len(allds)
    M = cp_model.CpModel(); y = [M.NewBoolVar("") for _ in range(n)]
    bits = [[i for i in range(n) if m >> i & 1] for m in mins]
    for b in bits: M.AddBoolOr([y[i] for i in b])
    # irreducible: each chosen d has a private syndrome s (s ∩ A = {d})
    for i in range(n):
        priv = []
        for b in bits:
            if i in b:
                z = M.NewBoolVar(""); priv.append(z)
                M.AddImplication(z, y[i])
                for j in b:
                    if j != i: M.AddImplication(z, y[j].Not())
        M.AddBoolOr(priv + [y[i].Not()])
    for A in forbid: M.AddBoolOr([y[i].Not() for i in A] + [y[i] for i in range(n) if i not in A])
    (M.Minimize if sense == "min" else M.Maximize)(sum(y))
    s = cp_model.CpSolver(); s.parameters.num_workers = 1
    st = s.Solve(M)
    if st != cp_model.OPTIMAL: return None
    return [i for i in range(n) if s.Value(y[i])]


def enum_all(allds, mins, cap=500):
    out, forbid = [], []
    while len(out) < cap:
        A = solve(allds, mins, "min", forbid)
        if A is None: break
        out.append(A); forbid.append(A)
    return out


def work(args):
    idx, S = args
    cols = [[t[0] for t in F.G18[k]] for k in S]
    allds, mins = fam_of(cols)
    mn, mx = solve(allds, mins, "min"), solve(allds, mins, "max")
    alls = enum_all(allds, mins)
    return idx, len(mins), len(mn), len(mx), dict(collections.Counter(len(a) for a in alls)), len(alls)


if __name__ == "__main__":
    lists = F.load()
    r2 = [(i, S) for i, S in enumerate(lists) if sorted(F.supw.get(k, 99) for k in S) == [1] * 10 + [2]]
    with Pool(4) as p:
        out = p.map(work, r2, chunksize=4)
    print("minimal-syndrome family sizes:", collections.Counter(o[1] for o in out))
    print("exact MIN IIS size:", dict(sorted(collections.Counter(o[2] for o in out).items())))
    print("exact MAX IIS size:", dict(sorted(collections.Counter(o[3] for o in out).items())))
    print("(min,max) pairs:", dict(collections.Counter((o[2], o[3]) for o in out)))
    print("#IIS per logical:", dict(collections.Counter(o[5] for o in out)))
    print("IIS size profiles:", collections.Counter(tuple(sorted(o[4].items())) for o in out))
    json.dump(out, open("results/fig1-audit/f4_exact.json", "w"))
