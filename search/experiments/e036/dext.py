"""E-036 step 3: maximum extended-code distance d_ext over ALL per-check CNOT orders (SBB Cor. 1 cap for
non-interleaved single-ancilla circuits).

Side X (X-type data errors, seen by Z checks, logical effect via Z logicals): columns = 18 data columns + hook
residues of the measured X checks.  A check with order o realises the residues of the suffixes of length 2, 3, 4;
mod the check itself these are P3 (last pair), T (first triple ~ its complement) and P1 (first pair).  A per-check
"type" = (P1, T-class, P3); 90 types per check.  Side Z symmetric with Z checks / X logicals.

Exact method: enumerate every set S of <= t-1 pool columns (data + all 15 pairs + 10 triple classes of every
measured check) whose sum is a nontrivial logical of that side; then "d_ext >= t" <=> no S is fully realised.
SAT over one-hot type variables (complete: S ranges over all potential columns).  Also reports uniform assignments
(same type for every check) and the per-check type values.
"""
import argparse
import itertools
import json

import numpy as np
from pysat.solvers import Cadical153

from search.experiments.e036.common import OUT, TERMS, checks, code, full_H, term_col


def rank2(M):
    M = (np.array(M, np.uint8) % 2).copy()
    r = 0
    for c in range(M.shape[1]):
        p = [i for i in range(r, M.shape[0]) if M[i, c]]
        if not p:
            continue
        M[[r, p[0]]] = M[[p[0], r]]
        for i in range(M.shape[0]):
            if i != r and M[i, c]:
                M[i] ^= M[r]
        r += 1
    return r


def types_for_check(kind, c):
    """distinct (P1, Tclass, P3) over all 720 orders; each as frozensets of data columns; returns list + orders."""
    out = {}
    for perm in itertools.permutations(range(6)):
        cols = [term_col(kind, c, t) for t in perm]
        P1 = frozenset(cols[:2])
        T = frozenset(cols[:3])
        Tc = frozenset(cols[3:])
        Tcls = min(T, Tc, key=lambda s: sorted(s))
        P3 = frozenset(cols[4:])
        key = (frozenset([P1, P3]), Tcls)  # reversal swaps P1/P3 -> same column set
        out.setdefault(key, perm)
    return out


def analyse(variant, side, tmax):
    c = code(variant)
    xs, zs = checks(variant)
    # side X: hooks from X checks, syndrome by HZ, stabilizers HX
    hook_kind, hook_checks = ("X", xs) if side == "X" else ("Z", zs)
    Hsyn, Hstab = (c.HZ, c.HX) if side == "X" else (c.HX, c.HZ)
    rk = rank2(Hstab)
    # pool
    pool = []  # (label, vec) ; label None for data
    for q in range(18):
        v = np.zeros(18, np.uint8)
        v[q] = 1
        pool.append((None, v))
    hook_index = {}
    for ch in hook_checks:
        supp = [term_col(hook_kind, ch, t) for t in range(6)]
        for pr in itertools.combinations(sorted(supp), 2):
            key = (ch, frozenset(pr))
            v = np.zeros(18, np.uint8)
            v[list(pr)] = 1
            hook_index[key] = len(pool)
            pool.append((key, v))
        for tr in itertools.combinations(sorted(supp), 3):
            comp = frozenset(set(supp) - set(tr))
            Tcls = min(frozenset(tr), comp, key=lambda s: sorted(s))
            if frozenset(tr) != Tcls:
                continue
            key = (ch, Tcls)
            v = np.zeros(18, np.uint8)
            v[list(tr)] = 1
            hook_index[key] = len(pool)
            pool.append((key, v))
    synd = [tuple((Hsyn @ v % 2).tolist()) for _, v in pool]
    zero = tuple([0] * Hsyn.shape[0])

    def is_logical(v):
        if (Hsyn @ v % 2).any():
            return False
        return rank2(np.vstack([Hstab, v])) > rk

    forb = {t: set() for t in range(2, tmax + 1)}  # forb[t] = minimal hook sets S making a logical of weight <= t-1
    data_logicals = {}
    P = len(pool)
    for w in range(1, tmax):
        for S in itertools.combinations(range(P), w):
            s = np.zeros(Hsyn.shape[0], np.uint8)
            for i in S:
                s ^= np.array(synd[i], np.uint8)
            if s.any():
                continue
            v = np.zeros(18, np.uint8)
            for i in S:
                v ^= pool[i][1]
            if not is_logical(v):
                continue
            hooks = frozenset(pool[i][0] for i in S if pool[i][0] is not None)
            if not hooks:
                data_logicals.setdefault(w, 0)
                data_logicals[w] += 1
            for t in range(w + 1, tmax + 1):
                forb[t].add(hooks)
    # types
    T = {ch: list(types_for_check(hook_kind, ch).items()) for ch in hook_checks}
    res = {"variant": variant, "side": side, "n_types_per_check": {ch: len(v) for ch, v in T.items()},
           "data_logicals_below": data_logicals}
    for t in range(2, tmax + 1):
        if any(len(S) == 0 for S in forb[t]):
            res[f"dext>={t}"] = "impossible (code logical of weight < t)"
            continue
        # SAT
        var = {}
        nv = 0

        def nvar():
            nonlocal nv
            nv += 1
            return nv
        tv = {}
        for ch, lst in T.items():
            tv[ch] = [nvar() for _ in lst]
        rv = {k: nvar() for k in hook_index}
        s = Cadical153()
        for ch, lst in T.items():
            s.add_clause(tv[ch])
            for a, b in itertools.combinations(tv[ch], 2):
                s.add_clause([-a, -b])
            for (cols, Tcls), _perm in []:
                pass
            for j, ((pairs, Tcls), perm) in enumerate(lst):
                for pr in pairs:
                    s.add_clause([-tv[ch][j], rv[(ch, pr)]])
                s.add_clause([-tv[ch][j], rv[(ch, Tcls)]])
        for S in forb[t]:
            s.add_clause([-rv[h] for h in S])
        sat = s.solve()
        out = {"n_forbidden_sets": len(forb[t]), "sat": sat}
        if sat:
            m = set(x for x in s.get_model() if x > 0)
            out["example_orders"] = {ch: "".join(TERMS[i] for i in T[ch][j][1]) for ch in T for j in range(len(T[ch]))
                                     if tv[ch][j] in m}
            # count all solutions (small?) up to a cap
            cnt = 0
            s2 = s
            while s2.solve() and cnt < 200000:
                mm = set(x for x in s2.get_model() if x > 0)
                cl = [-tv[ch][j] for ch in T for j in range(len(T[ch])) if tv[ch][j] in mm]
                s2.add_clause(cl)
                cnt += 1
            out["n_type_assignments"] = cnt if cnt < 200000 else ">=200000"
        # uniform assignments: types are matched across checks by order class (use the term-label permutation)
        uni = 0
        uni_list = []
        perms0 = {}
        for ch, lst in T.items():
            for j, (key, perm) in enumerate(lst):
                pass
        # uniform: every check uses the same label order (up to the type equivalence) -> test each of 720 orders
        seen = set()
        for perm in itertools.permutations(range(6)):
            ok = True
            real = set()
            for ch in hook_checks:
                cols = [term_col(hook_kind, ch, tt) for tt in perm]
                P1, P3 = frozenset(cols[:2]), frozenset(cols[4:])
                Tm = min(frozenset(cols[:3]), frozenset(cols[3:]), key=lambda s_: sorted(s_))
                real |= {(ch, P1), (ch, P3), (ch, Tm)}
            if any(S <= real for S in forb[t]):
                continue
            uni += 1
            uni_list.append("".join(TERMS[i] for i in perm))
        out["uniform_orders_ok"] = uni
        out["uniform_examples"] = uni_list[:12]
        res[f"dext>={t}"] = out
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("variant")
    ap.add_argument("--tmax", type=int, default=4)
    a = ap.parse_args()
    allr = []
    for side in ("X", "Z"):
        r = analyse(a.variant, side, a.tmax)
        print(json.dumps(r, default=str, indent=None)[:3000], flush=True)
        allr.append(r)
    (OUT / f"dext_{a.variant}.json").write_text(json.dumps(allr, default=str, indent=1))
