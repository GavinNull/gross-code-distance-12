"""A4: own extended code from the c16 / u16 CNOT orders (suffix hooks), d_ext, and complete weight-8 / weight-9 lists by
SAT model enumeration with blocking clauses (different algorithm from the project's orbit-split DFS).  Compares with the
project's pickled lists (keys recomputed with the evaluator's HZ/LZ, HX/LX, which only fixes a basis).
Usage: a4_extlist.py SPEC"""
import sys, json, pickle, time, collections
sys.path.insert(0, "research/audits/2026-10-15-E-028-scripts")
import numpy as np
from alib import *
from pysat.card import CardEnc, EncType
from pysat.solvers import Solver

HX, HZ, LX, LZ = code_with_logicals()

def ext_code(spec, kind):
    """kind 'X': X-check hooks, X errors, (HZ, LZ) [Z-basis memory]; kind 'Z': Z-check hooks, (HX, LX)."""
    H, Lg = (HZ, LZ) if kind == "X" else (HX, LX)
    chk = spec["x_checks"] if kind == "X" else spec["z_checks"]
    sups = [(q,) for q in range(N)]
    for c in chk:
        order = [a for a, t in sorted(c["cnots"], key=lambda x: x[1])]
        for k in range(1, 6):            # X error on ancilla after k CNOTs -> suffix order[k:]
            sups.append(tuple(sorted(order[k:])))
    cols = {}
    for S in sups:
        v = np.zeros(N, np.uint8); v[list(S)] = 1
        key = (tuple((H.astype(int) @ v) % 2), tuple((Lg.astype(int) @ v) % 2))
        if not any(key[0]) and not any(key[1]):
            continue
        cols.setdefault(key, []).append(S)
    keys = list(cols)
    return keys, cols

def enum(keys, W, exact=True, limit=10**6):
    n = len(keys)
    nh, nl = len(keys[0][0]), len(keys[0][1])
    top = n
    cls = []
    def chain(vs):
        nonlocal top, cls
        cur = vs[0]
        for v in vs[1:]:
            top += 1; y = top
            cls += [[-cur, -v, -y], [cur, v, -y], [cur, -v, y], [-cur, v, y]]
            cur = y
        return cur
    for r in range(nh):
        vs = [j + 1 for j in range(n) if keys[j][0][r]]
        if vs: cls.append([-chain(vs)])
    outs = []
    for r in range(nl):
        vs = [j + 1 for j in range(n) if keys[j][1][r]]
        if vs: outs.append(chain(vs))
    cls.append(outs)
    lits = list(range(1, n + 1))
    am = CardEnc.atmost(lits, bound=W, top_id=top, encoding=EncType.totalizer); cls += am.clauses; top = am.nv
    if exact:
        al = CardEnc.atleast(lits, bound=W, top_id=top, encoding=EncType.totalizer); cls += al.clauses; top = al.nv
    sols = []
    with Solver(name="cd15", bootstrap_with=cls) as s:
        while s.solve():
            m = s.get_model()
            S = tuple(j for j in range(n) if m[j] > 0)
            sols.append(S)
            s.add_clause([-(j + 1) for j in S])
            if len(sols) >= limit: break
    return sols

def verify(keys, S):
    h = np.zeros(len(keys[0][0]), int); l = np.zeros(len(keys[0][1]), int)
    for j in S:
        h += keys[j][0]; l += keys[j][1]
    return not (h % 2).any() and (l % 2).any()

if __name__ == "__main__":
    spec_path = sys.argv[1]
    spec = load_spec(spec_path)
    tag = spec_path.split("/")[-1][:3]
    from evaluators.tasks import build_code, get_task
    c, _ = build_code(get_task("bb90-dcirc"), None)
    res = {}
    for kind in "XZ":
        t0 = time.time()
        keys, cols = ext_code(spec, kind)
        r = {"N": len(keys), "multi_support_columns": sum(1 for k in keys if len(cols[k]) > 1)}
        r["w<=7"] = len(enum(keys, 7, exact=False, limit=1))
        s8 = enum(keys, 8); s9 = enum(keys, 9)
        assert all(verify(keys, S) for S in s8 + s9)
        r["w8"], r["w9"] = len(s8), len(s9)
        # compare with project lists (evaluator keys)
        He, Le = ((np.asarray(c.HZ) % 2, np.asarray(c.LZ) % 2) if kind == "X" else (np.asarray(c.HX) % 2, np.asarray(c.LX) % 2))
        def ekey(S):
            v = np.zeros(N, np.uint8); v[list(S)] = 1
            return ((He.astype(int) @ v) % 2).astype(np.uint8).tobytes() + ((Le.astype(int) @ v) % 2).astype(np.uint8).tobytes()
        mykey = [ekey(cols[k][0]) for k in keys]
        for w, sols in ((8, s8), (9, s9)):
            try:
                d = pickle.load(open(f"results/E-028-bb90-interleaved/w{w}_{kind}_all_A1A2A3B2B1B3.pkl", "rb"))
            except FileNotFoundError:
                r[f"cmp{w}"] = "no project list"; continue
            proj = {frozenset(S) for S in d["keys"]}
            mine = {frozenset(mykey[j] for j in S) for S in sols}
            r[f"cmp{w}"] = {"proj": len(proj), "mine": len(mine), "equal": proj == mine,
                            "colset_equal": set(d["colset"]) == set(mykey)}
        r["sec"] = round(time.time() - t0, 1)
        res[kind] = r
        print(tag, kind, json.dumps(r), flush=True)
        pickle.dump({"keys": keys, "cols": cols, "s8": s8, "s9": s9}, open(f"results/E-028-audit/ext_{tag}_{kind}.pkl", "wb"))
    with open("results/E-028-audit/a4_extlist.jsonl", "a") as f:
        f.write(json.dumps({"spec": spec_path, **res}) + "\n")
