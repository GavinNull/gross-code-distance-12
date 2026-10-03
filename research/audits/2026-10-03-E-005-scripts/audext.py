"""Auditor's independent implementation of the Strikis-Browne-Beverland extended code (arXiv:2603.05481 v2,
Sec. IV.A Def. 2-3, Eq. 7-8) and exact extended-code distance.

Written WITHOUT reading search/noninterleaved/ (E-005's code).  Only generic, read-only project utilities are used:
  * baselines.bb_code.gf2_nullspace / gf2_rank (GF(2) linear algebra) -- results re-verified here;
  * baselines.schedule / baselines.strikis (circuit definitions, only to read CNOT orders);
  * search.codes.distance._milp_one_type (HiGHS) as a SECOND solver for cross-checks.
Primary solver: OR-tools CP-SAT with native XOR constraints (own model).

Conventions
  Z-type residuals (from Z checks; Z errors) are appended to (HX, LX):  x is a Z-type ext. logical iff
      HX_ext x = 0 and LX_ext x != 0      (LX = basis of X logicals, rows).
  X-type residuals (from X checks; X errors) are appended to (HZ, LZ) analogously.
  Residual set of a check with CNOT order (i1..iw): suffixes {i_l..i_w}, l = 2..w  (Sec. IV.A).
"""
from __future__ import annotations

import itertools
import time

import numpy as np

from baselines.bb_code import gf2_nullspace, gf2_rank

# --------------------------------------------------------------------------- codes (own construction)
CODE_DEFS = {   # arXiv:2308.07915 Table 3 (as transcribed in search/codes/catalog.py)
    "bb90": (15, 3, ["x^9", "y", "y^2"], ["1", "x^2", "x^7"], (90, 8, 10)),
    "bb108": (9, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"], (108, 8, 10)),
    "gross": (12, 6, ["x^3", "y", "y^2"], ["y^3", "x", "x^2"], (144, 12, 12)),
}


def _mono(term, l, m):
    a = b = 0
    for f in term.split("*"):
        f = f.strip()
        if f == "1":
            continue
        v, _, p = f.partition("^")
        p = int(p) if p else 1
        if v == "x":
            a += p
        else:
            b += p
    Sl = np.roll(np.eye(l, dtype=np.int64), 1, axis=1)
    Sm = np.roll(np.eye(m, dtype=np.int64), 1, axis=1)
    return np.kron(np.linalg.matrix_power(Sl, a % l), np.linalg.matrix_power(Sm, b % m))


class Code:
    def __init__(self, name):
        l, m, A, B, nkd = CODE_DEFS[name]
        self.name, self.l, self.m, self.nkd = name, l, m, nkd
        self.Aterms = [_mono(t, l, m).astype(np.uint8) for t in A]
        self.Bterms = [_mono(t, l, m).astype(np.uint8) for t in B]
        Am = sum(self.Aterms) % 2
        Bm = sum(self.Bterms) % 2
        self.HX = np.hstack([Am, Bm]).astype(np.uint8)
        self.HZ = np.hstack([Bm.T, Am.T]).astype(np.uint8)
        self.n = self.HX.shape[1]
        self.n2 = self.n // 2
        assert not ((self.HX.astype(int) @ self.HZ.T.astype(int)) % 2).any()
        self.k = self.n - gf2_rank(self.HX) - gf2_rank(self.HZ)
        assert (self.n, self.k) == nkd[:2], (self.n, self.k)
        self.LX = self._logicals(self.HX, self.HZ)   # X logicals: in ker HZ, not in rs HX
        self.LZ = self._logicals(self.HZ, self.HX)

    def _logicals(self, Hsame, Hother):
        ker = gf2_nullspace(Hother)
        base = gf2_rank(Hsame)
        cur = Hsame.copy()
        out = []
        for v in ker:
            t = np.vstack([cur, v[None]])
            if gf2_rank(t) > base + len(out):
                out.append(v)
                cur = t
            if len(out) == self.k:
                break
        L = np.array(out, dtype=np.uint8)
        assert L.shape[0] == self.k
        assert not ((Hother.astype(int) @ L.T.astype(int)) % 2).any()
        return L

    def det(self, err_type):
        """(H, L) that see errors of type err_type ('Z' -> (HX, LX); 'X' -> (HZ, LZ))."""
        return (self.HX, self.LX) if err_type == "Z" else (self.HZ, self.LZ)

    def check_support(self, check_type, row):
        H = self.HX if check_type == "X" else self.HZ
        return [int(j) for j in np.nonzero(H[row])[0]]


# --------------------------------------------------------------------------- residuals / extended code
def suffixes(order):
    """Residual supports of one check with CNOT order (i1..iw): {i_l..i_w}, l = 2..w."""
    return [tuple(order[l:]) for l in range(1, len(order))]


def ext_matrix(H, L, residual_supports):
    """Stack [H; L] and append one column per residual (mod-2 sum of its data columns).
    Returns (M, nrowsH) with M uint8 of shape (rH + k, n + |R|)."""
    M0 = np.vstack([H, L]).astype(np.uint8)
    cols = [M0]
    if residual_supports:
        R = np.zeros((M0.shape[0], len(residual_supports)), dtype=np.uint8)
        for j, S in enumerate(residual_supports):
            R[:, j] = M0[:, list(S)].sum(1) % 2
        cols.append(R)
    return np.hstack(cols), H.shape[0]


def dedupe_columns(M):
    """Drop zero columns and duplicate columns (neither changes the minimum weight).  Returns (M', keep_idx)."""
    seen = {}
    keep = []
    for j in range(M.shape[1]):
        c = M[:, j]
        if not c.any():
            continue
        key = c.tobytes()
        if key in seen:
            continue
        seen[key] = j
        keep.append(j)
    return M[:, keep], np.array(keep)


def verify(M, rH, x):
    s = (M.astype(np.int64) @ x.astype(np.int64)) % 2
    return (not s[:rH].any()) and bool(s[rH:].any())


# --------------------------------------------------------------------------- CP-SAT solver
def cpsat_min(M, rH, cap=None, minimize=True, time_limit=600.0, workers=1, seed=0, hint=None):
    """min |x| s.t. M[:rH] x = 0, M[rH:] x != 0 (mod 2).  cap: |x| <= cap.
    minimize=False: pure feasibility for |x| <= cap.
    Returns dict(status, value, lower, x)."""
    from ortools.sat.python import cp_model
    nr, nc = M.shape
    md = cp_model.CpModel()
    x = [md.NewBoolVar(f"x{j}") for j in range(nc)]
    one = md.NewBoolVar("one")
    md.Add(one == 1)
    for i in range(rH):
        idx = np.nonzero(M[i])[0]
        if len(idx):
            md.AddBoolXOr([x[j] for j in idx] + [one])     # even parity
    bs = []
    for i in range(rH, nr):
        idx = np.nonzero(M[i])[0]
        b = md.NewBoolVar(f"b{i}")
        md.AddBoolXOr([x[j] for j in idx] + [b.Not()])     # b = parity
        bs.append(b)
    md.AddBoolOr(bs)
    if cap is not None:
        md.Add(sum(x) <= cap)
    if minimize:
        md.Minimize(sum(x))
    if hint is not None:
        for j in range(nc):
            md.AddHint(x[j], int(hint[j]))
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = float(time_limit)
    s.parameters.num_workers = int(workers)
    s.parameters.random_seed = int(seed)
    t0 = time.time()
    st = s.Solve(md)
    out = {"seconds": round(time.time() - t0, 2), "solver": "cpsat", "cap": cap}
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        xv = np.array([s.Value(v) for v in x], dtype=np.uint8)
        assert verify(M, rH, xv), "CP-SAT returned an invalid logical"
        out.update(value=int(xv.sum()), x=xv)
        if minimize:
            lb = int(np.ceil(s.BestObjectiveBound() - 1e-6))
            out["lower"] = lb
            out["status"] = "optimal" if st == cp_model.OPTIMAL else "feasible"
        else:
            out["status"] = "feasible"
            out["lower"] = None
    elif st == cp_model.INFEASIBLE:
        out.update(status="infeasible", value=None, x=None, lower=(cap + 1 if cap is not None else None))
    else:
        out.update(status="unknown", value=None, x=None,
                   lower=(int(np.ceil(s.BestObjectiveBound() - 1e-6)) if minimize else None))
    return out


def highs_min(M, rH, cap=None, time_limit=600.0):
    """Second solver: HiGHS via search.codes.distance._milp_one_type (read-only use)."""
    from search.codes.distance import _milp_one_type
    r = _milp_one_type(M[:rH], M[rH:], cap, time_limit, None)
    out = {"solver": "highs", "cap": cap, "status": ("infeasible" if r["status"] == 2 else
                                                     "optimal" if r["optimal"] else "unknown"),
           "value": r["value"], "lower": r.get("lower")}
    if r["value"] is not None:
        assert verify(M, rH, r["witness"])
        out["x"] = r["witness"]
    if out["status"] == "infeasible":
        out["lower"] = cap + 1
    return out


# --------------------------------------------------------------------------- single-check classes
def single_check_classes(code: Code, check_type: str, row: int = 0):
    """Enumerate all 720 CNOT orders of one weight-6 check; group by the SET of distinct extended columns
    contributed by the residuals that are not already data columns (exact column equality in [H; L]).
    Returns list of (representative order, n_orders, residual supports of the rep)."""
    err = check_type          # X check -> X-type residuals
    H, L = code.det(err)
    M0 = np.vstack([H, L]).astype(np.uint8)
    datacols = {np.ascontiguousarray(M0[:, j]).astype(np.uint8).tobytes() for j in range(M0.shape[1])}
    supp = code.check_support(check_type, row)
    groups = {}
    for perm in itertools.permutations(supp):
        key = set()
        for S in suffixes(perm):
            c = (M0[:, list(S)].sum(1) % 2).astype(np.uint8)
            if c.any() and c.tobytes() not in datacols:
                key.add(c.tobytes())
        key = frozenset(key)
        groups.setdefault(key, []).append(perm)
    out = []
    for key, perms in groups.items():
        rep = min(perms)
        out.append({"rep": list(rep), "n_orders": len(perms), "n_new_cols": len(key),
                    "residuals": suffixes(rep)})
    out.sort(key=lambda d: d["rep"])
    return out


# --------------------------------------------------------------------------- schedules -> orders
def orders_from_schedule(sched):
    """CNOT order of every check, read cyclically from its prep layer.  Returns ({'X': [order per row]}, {'Z': ...})
    with orders as lists of data COLUMN indices."""
    D = sched.depth
    col = {q: j for j, q in enumerate(sched.data)}
    res = {}
    for ctype, checks in (("X", sched.x_checks), ("Z", sched.z_checks)):
        prep = {}
        for t, Lr in enumerate(sched.layers):
            for q in (Lr.prep_x if ctype == "X" else Lr.prep_z):
                prep[q] = t
        ev = {q: [] for q in checks}
        cs = set(checks)
        for t, Lr in enumerate(sched.layers):
            for a, b in Lr.cnots:
                if ctype == "X" and a in cs:
                    ev[a].append(((t - prep[a]) % D, col[b]))
                if ctype == "Z" and b in cs:
                    ev[b].append(((t - prep[b]) % D, col[a]))
        res[ctype] = [[c for _, c in sorted(ev[q])] for q in checks]
        for q in checks:
            ts = [t for t, _ in ev[q]]
            assert len(set(ts)) == len(ts)
    return res


def full_residuals(orders_one_type):
    return [S for o in orders_one_type for S in suffixes(o)]


# --------------------------------------------------------------------------- non-interleaving tests (own)
def pairwise_and_partition(sched, rounds=8):
    """Two independent tests on the time-unrolled periodic schedule (instance j of check q starts at its
    prep layer + D*j; CNOT offsets read cyclically from prep, as in Schedule.validate).

    pairwise: for every (X instance, Z instance) pair sharing data qubits, the X-CNOTs and Z-CNOTs on the shared
              qubits are not mixed (all X before all Z, or all Z before all X)  [paper Sec. II.A wording].
    partition: there is a phase function on check instances, nondecreasing along every data qubit's time line and
              strictly increasing whenever the check type changes  <=>  no strongly connected component of the
              instance precedence graph contains a type-changing edge.  This is exactly what the proofs of Prop. 2 /
              Corollary 1 use ('temporally partitioned into X- and Z-type parts' after inserting error-free idles),
              for a finite number of rounds.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    D = sched.depth
    xs = set(sched.x_checks)
    info = {}
    for q in sched.x_checks + sched.z_checks:
        tp = next(t for t, L in enumerate(sched.layers) if q in L.prep_x + L.prep_z)
        cn = [((t - tp) % D, (b if q == a else a)) for t, L in enumerate(sched.layers) for a, b in L.cnots if q in (a, b)]
        info[q] = (tp, cn)
    nodes = {}
    ev = {}
    for q, (tp, cn) in info.items():
        for j in range(rounds):
            nid = nodes.setdefault((q, j), len(nodes))
            for d, dq in cn:
                ev.setdefault(dq, []).append((tp + D * j + d, nid, q in xs))
    typ = {}
    for (q, j), nid in nodes.items():
        typ[nid] = q in xs
    edges = {}
    # pairwise
    seq = {}
    for dq, L in ev.items():
        L.sort()
        assert len(set(t for t, _, _ in L)) == len(L), "two CNOTs on one data qubit in the same layer"
        for (t1, a, ta), (t2, b, tb) in zip(L, L[1:]):
            if a != b:
                w = 1 if ta != tb else 0
                edges[(a, b)] = max(edges.get((a, b), 0), w)
        for i, (t1, a, ta) in enumerate(L):
            for (t2, b, tb) in L[i + 1:]:
                if ta != tb:
                    key = (a, b) if ta else (b, a)        # (X inst, Z inst)
                    seq.setdefault(key, set()).add("XZ" if ta else "ZX")
    mixed_pairs = sum(1 for v in seq.values() if len(v) > 1)
    N = len(nodes)
    r = [a for a, b in edges]
    c = [b for a, b in edges]
    G = coo_matrix((np.ones(len(r)), (r, c)), shape=(N, N)).tocsr()
    ncomp, lab = connected_components(G, directed=True, connection="strong")
    bad = [(a, b) for (a, b), w in edges.items() if w == 1 and lab[a] == lab[b]]
    return {"rounds": rounds, "overlapping_instance_pairs": len(seq), "pairwise_mixed": mixed_pairs,
            "pairwise_noninterleaved": mixed_pairs == 0,
            "type_change_edges_inside_SCC": len(bad), "partitionable": len(bad) == 0,
            "largest_SCC": int(np.bincount(lab).max())}


# --------------------------------------------------------------------------- symmetry-reduced exact solve
def nontrivial_suffixes(order):
    """Suffixes of size 2..w-2 only.  Size-1 suffix = a data column; size-(w-1) suffix differs from the first data
    qubit by the check itself (a stabiliser of the SAME type, which has zero column in [H; L] of the opposite type),
    so both give columns identical to data columns and can be dropped without changing any minimum."""
    w = len(order)
    return [tuple(order[l:]) for l in range(2, w - 1)]


def translation_perm(code, h):
    """Data-column permutation for translation by group element h=(a,b): L g -> L g+h, R g -> R g+h."""
    l, m = code.l, code.m
    n2 = code.n2
    p = np.empty(code.n, dtype=np.int64)
    for a in range(l):
        for b in range(m):
            g = a * m + b
            g2 = ((a + h[0]) % l) * m + (b + h[1]) % m
            p[g] = g2
            p[n2 + g] = n2 + g2
    return p


def column_orbits(code, residual_supports, group=None):
    """Orbits of extended columns (data + residuals) under the translations that map the residual SET to itself.
    Returns (orbits as lists of column indices, list of symmetry translations)."""
    n = code.n
    idx = {frozenset(S): n + i for i, S in enumerate(residual_supports)}
    assert len(idx) == len(residual_supports)
    syms = []
    perms = []
    for a in range(code.l):
        for b in range(code.m):
            p = translation_perm(code, (a, b))
            # automorphism of the code?
            ok = True
            for H in (code.HX, code.HZ):
                rows = {np.nonzero(H[i])[0].tobytes() for i in range(H.shape[0])}
                rows2 = {np.sort(p[np.nonzero(H[i])[0]]).tobytes() for i in range(H.shape[0])}
                if rows != rows2:
                    ok = False
            assert ok
            img = [frozenset(int(p[q]) for q in S) for S in residual_supports]
            if all(s in idx for s in img):
                full = np.concatenate([p, np.array([idx[s] for s in img])])
                perms.append(full)
                syms.append((a, b))
    N = n + len(residual_supports)
    seen = np.full(N, -1)
    orbits = []
    for j in range(N):
        if seen[j] >= 0:
            continue
        orb = sorted({int(P[j]) for P in perms})
        for o in orb:
            seen[o] = len(orbits)
        orbits.append(orb)
    return orbits, syms


def highs_fixed(M, rH, cap, time_limit, force_one=None, force_zero=(), feasibility=False):
    """HiGHS min-weight logical with x[force_one]=1 and x[j]=0 for j in force_zero (own MILP formulation:
    H x - 2 s = 0, L x - 2 t - y = 0, sum y >= 1)."""
    import scipy.sparse as sp
    from scipy.optimize import Bounds, LinearConstraint, milp
    H = M[:rH].astype(np.int64)
    L = M[rH:].astype(np.int64)
    r, n = H.shape
    k = L.shape[0]
    nv = n + r + 2 * k
    c = np.zeros(nv); c[:n] = 0 if feasibility else 1
    A = sp.vstack([
        sp.hstack([sp.csr_matrix(H), -2 * sp.identity(r), sp.csr_matrix((r, 2 * k))]),
        sp.hstack([sp.csr_matrix(L), sp.csr_matrix((k, r)), -2 * sp.identity(k), -sp.identity(k)]),
        sp.csr_matrix(np.r_[np.zeros(n + r + k), np.ones(k)][None]),
        sp.csr_matrix(np.r_[np.ones(n), np.zeros(r + 2 * k)][None]),
    ]).tocsr()
    lb = np.r_[np.zeros(r + k), 1, 0]
    ub = np.r_[np.zeros(r + k), np.inf, cap if cap is not None else np.inf]
    lo = np.zeros(nv)
    hi = np.full(nv, np.inf); hi[:n] = 1; hi[n + r + k:] = 1
    hi[n:n + r] = np.floor(H.sum(1) / 2); hi[n + r:n + r + k] = np.floor(L.sum(1) / 2)
    if force_one is not None:
        lo[force_one] = 1
    for j in force_zero:
        hi[j] = 0
    t0 = time.time()
    res = milp(c, constraints=LinearConstraint(A, lb, ub), integrality=np.ones(nv), bounds=Bounds(lo, hi),
               options={"time_limit": time_limit, "disp": False, "mip_rel_gap": 0})
    out = {"seconds": round(time.time() - t0, 1), "cap": cap}
    if res.status == 2:
        out.update(status="infeasible", value=None, lower=(cap + 1 if cap is not None else None))
    elif res.x is not None:
        x = np.round(res.x[:n]).astype(np.uint8)
        assert verify(M, rH, x)
        lbd = getattr(res, "mip_dual_bound", None)
        out.update(status=("feasible" if feasibility else "optimal" if res.status == 0 else "feasible"),
                   value=int(x.sum()), x=x,
                   lower=int(np.ceil(lbd - 1e-6)) if lbd is not None and np.isfinite(lbd) else None)
    else:
        lbd = getattr(res, "mip_dual_bound", None)
        out.update(status="unknown", value=None,
                   lower=int(np.ceil(lbd - 1e-6)) if lbd is not None and np.isfinite(lbd) else None)
    return out


# --------------------------------------------------------------------------- BB term orders
def check_order_from_terms(code, ctype, row, terms):
    """Data-column order of check `row` when its CNOTs follow term order `terms` (0,1,2=A1..A3, 3,4,5=B1..B3)."""
    n2 = code.n2
    out = []
    for t in terms:
        M = code.Aterms[t] if t < 3 else code.Bterms[t - 3]
        if ctype == "X":   # HX = [A | B]
            j = int(np.nonzero(M[row])[0][0]); out.append(j if t < 3 else n2 + j)
        else:              # HZ = [B^T | A^T]
            j = int(np.nonzero(M[:, row])[0][0]); out.append(n2 + j if t < 3 else j)
    assert sorted(out) == code.check_support(ctype, row)
    return out


def term_order_classes(code, ctype):
    """Group the 720 term orders by the single-check (row 0) residual-column class."""
    H, L = code.det(ctype)
    M0 = np.vstack([H, L]).astype(np.uint8)
    datacols = {np.ascontiguousarray(M0[:, j]).tobytes() for j in range(M0.shape[1])}
    groups = {}
    for perm in itertools.permutations(range(6)):
        o = check_order_from_terms(code, ctype, 0, perm)
        key = set()
        for S in suffixes(o):
            c = (M0[:, list(S)].sum(1) % 2).astype(np.uint8)
            if c.any() and c.tobytes() not in datacols:
                key.add(c.tobytes())
        groups.setdefault(frozenset(key), []).append(perm)
    return sorted([sorted(v) for v in groups.values()])
