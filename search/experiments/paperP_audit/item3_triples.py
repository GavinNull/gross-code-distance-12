"""Item 3: which pairs / triples of term labels of check 0 lie in a weight-d nontrivial logical.
Own code construction (from the polynomials in paper/scripts/check_tables.CODES), own GF(2) algebra, CP-SAT
feasibility at weight exactly d (d = code distance, so weight <= d nontrivial means weight d).
  uv run python search/experiments/paperP_audit/item3_triples.py <gross|bb90> <X|Z> <pairs|triples> [timeout_s]
"""
import itertools, json, sys, time
import numpy as np
from ortools.sat.python import cp_model

CODES = {"gross": dict(L=12, M=6, A=[(3, 0), (0, 1), (0, 2)], B=[(0, 3), (1, 0), (2, 0)], d=12),
         "bb90": dict(L=15, M=3, A=[(9, 0), (0, 1), (0, 2)], B=[(0, 0), (2, 0), (7, 0)], d=10)}


def build(c):
    L, M = c["L"], c["M"]; m = L * M
    idx = lambda a, b: M * (a % L) + (b % M)
    def mat(terms):
        T = np.zeros((m, m), np.uint8)
        for r in range(m):
            a, b = divmod(r, M)
            for dx, dy in terms:
                T[r, idx(a + dx, b + dy)] ^= 1
        return T
    A, B = mat(c["A"]), mat(c["B"])
    HX = np.hstack([A, B]); HZ = np.hstack([B.T, A.T])
    assert not ((HX.astype(int) @ HZ.T.astype(int)) % 2).any()
    # labels on check 0
    labX = {f"A{i+1}": idx(*t) for i, t in enumerate(c["A"])} | {f"B{j+1}": m + idx(*t) for j, t in enumerate(c["B"])}
    labZ = {f"B{j+1}": idx(-t[0], -t[1]) for j, t in enumerate(c["B"])} | {f"A{i+1}": m + idx(-t[0], -t[1]) for i, t in enumerate(c["A"])}
    assert sorted(labX.values()) == sorted(np.flatnonzero(HX[0]).tolist())
    assert sorted(labZ.values()) == sorted(np.flatnonzero(HZ[0]).tolist())
    return HX, HZ, labX, labZ


def gf2_kernel(H):
    H = H.copy() % 2; r, n = H.shape; piv = []; row = 0
    for col in range(n):
        p = next((i for i in range(row, r) if H[i, col]), None)
        if p is None: continue
        H[[row, p]] = H[[p, row]]
        for i in range(r):
            if i != row and H[i, col]: H[i] ^= H[row]
        piv.append(col); row += 1
        if row == r: break
    free = [j for j in range(n) if j not in piv]
    K = []
    for f in free:
        v = np.zeros(n, np.uint8); v[f] = 1
        for i, pc in enumerate(piv):
            if H[i, f]: v[pc] = 1
        K.append(v)
    return np.array(K), len(piv)


def solve(Hdet, Kstab, T, d, timeout):
    """x in ker Hdet, x not in rowspace(stabilisers) <=> some k in Kstab (basis of ker of stab matrix) has k.x = 1."""
    n = Hdet.shape[1]; md = cp_model.CpModel(); x = [md.NewBoolVar(f"x{i}") for i in range(n)]
    one = md.NewConstant(1)
    for row in Hdet:
        md.AddBoolXOr([x[i] for i in np.flatnonzero(row)] + [one])
    bs = []
    for k in Kstab:
        b = md.NewBoolVar("")
        md.AddBoolXOr([x[i] for i in np.flatnonzero(k)] + [b.Not()]); bs.append(b)
    md.AddBoolOr(bs)
    md.Add(sum(x) == d)
    for q in T: md.Add(x[q] == 1)
    s = cp_model.CpSolver(); s.parameters.num_workers = 1; s.parameters.max_time_in_seconds = timeout
    st = s.Solve(md)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        v = np.array([s.Value(xx) for xx in x], np.uint8)
        ok = (not ((Hdet.astype(int) @ v) % 2).any()) and bool(((Kstab.astype(int) @ v) % 2).any()) and v.sum() == d and all(v[q] for q in T)
        return "FEASIBLE", bool(ok)
    return {cp_model.INFEASIBLE: "INFEASIBLE"}.get(st, "UNKNOWN"), None


def main():
    code, side, what = sys.argv[1:4]; timeout = float(sys.argv[4]) if len(sys.argv) > 4 else 600
    c = CODES[code]; HX, HZ, labX, labZ = build(c)
    # X side: hooks of X checks put X errors on X-check support labels; X errors are seen by HZ; trivial iff in rowspace(HX)
    Hdet, stab, lab = (HZ, HX, labX) if side == "X" else (HX, HZ, labZ)
    K, rk = gf2_kernel(stab)
    r = 2 if what == "pairs" else 3
    names = sorted(lab)
    out = []
    for T in itertools.combinations(names, r):
        t = time.time(); st, ok = solve(Hdet, K, [lab[nm] for nm in T], c["d"], timeout)
        out.append({"T": "".join(T), "status": st, "witness_ok": ok, "s": round(time.time() - t, 1)})
        print(json.dumps(out[-1]), flush=True)
    print(json.dumps({"code": code, "side": side, "what": what, "n": len(out),
                      "feasible": sum(o["status"] == "FEASIBLE" for o in out),
                      "infeasible": sum(o["status"] == "INFEASIBLE" for o in out),
                      "unknown": sum(o["status"] == "UNKNOWN" for o in out),
                      "feasible_list": [o["T"] for o in out if o["status"] == "FEASIBLE"]}), flush=True)


if __name__ == "__main__":
    main()
