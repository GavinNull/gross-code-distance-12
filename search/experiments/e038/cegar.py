"""E-038 pattern-CEGAR: is there a legal schedule of a class with no bulk undetectable logical of weight <= d-1?

Loop: SAT model -> schedule -> exact bulk search (model.bulk_min, both bases, weight <= d-1, faults in W rounds) ->
every witness is abstracted to its PATTERN (basis; slots D(q, r) / H(k, U, r) / M(c, r) with rounds relative to the
earliest slot; the reader f* that fixes a data cut is NOT part of the pattern) -> for every choice of f* per data
slot, one clause
        not [ suffix(k, U) for every H slot ]  OR  OR_{detectors (c, j)} [ parity of contributions to (c, j) is 1 ]
where a contribution of a data error / hook event g on qubit u to reader f is the indicator
"first instance of f after g is j0" = LT(g, f, j0) & ~LT(g, f, j0 - 1) (model.py), and constants for f = f* and M.
Soundness: if a schedule makes the clause false for some choice, the slots exist in it (H: U is a suffix; D: the
cut just before f* exists; M always), their detector masks cancel, and the residual (fixed by the pattern) is the
same non-trivial logical -> bulk witness of weight <= |pattern|.  No literal of the found schedule is reused, so one
pattern excludes all schedules in which that fault combination cancels.

usage: uv run python -m search.experiments.e038.cegar N 7 [--variant bb18] [--d 4] [--dump]
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import time

from pysat.solvers import Solver

from search.experiments.e036_audit.core import checks, support
from search.experiments.e038.enc import Enc, neg
from search.experiments.e038.model import Sched, bulk_min, legal

OUT = "results/E-038-bb18-d4"
DIRECT = False


def pattern_of(basis, tags):
    rmin = min(t[-1] for t in tags)
    slots = []
    for t in tags:
        if t[0] == "D":
            slots.append(("D", t[1], t[3] - rmin))
        elif t[0] == "H":
            slots.append(("H", t[1], tuple(sorted(t[2])), t[3] - rmin))
        else:
            slots.append(("M", t[1], t[2] - rmin))
    return (basis, tuple(sorted(slots, key=repr)))


class PatternEncoder:
    def __init__(self, E: Enc):
        self.E = E
        self.rev = {}
        for b in ("Z", "X"):
            rv = {q: [] for q in range(18)}
            for k in E.ks:
                if k[0] == b:
                    for a, q in enumerate(support(k)):
                        rv[q].append((k, a))
            self.rev[b] = rv

    def first(self, g, f, j0):
        E = self.E
        return E.AND([E.LT(g, f, j0), neg(E.LT(g, f, j0 - 1))])

    def contrib(self, dets, g, f, r):
        for j0 in range(-2, 4):
            ind = self.first(g, f, j0)
            if ind is False:
                continue
            dets.setdefault((f[0], r + j0), []).append(ind)

    def clauses(self, pat):
        """list of clauses (each a list of literals) for the pattern; [] clause = schedule-independent witness."""
        basis, slots = pat
        rev = self.rev[basis]
        choices = [rev[s[1]] for s in slots if s[0] == "D"]
        out = []
        for ch in itertools.product(*choices):
            if getattr(self, "direct", False):
                out += self.direct_clauses_for_choice(pat, ch)
                continue
            cl = self.clauses_for_choice(pat, ch)
            if cl is not None:
                out.append(cl)
        return out

    def direct_clauses_for_choice(self, pat, ch, nmax=14):
        """same exclusion as clauses_for_choice, without XOR auxiliaries: one clause per assignment of the indicator
        literals under which every detector parity is 0 (falls back to the XOR clause if > nmax literals)."""
        dets, cond = self._dets(pat, ch)
        if dets is None:
            return []
        neg_cond = [neg(c) for c in cond if c is not True]
        lists = []
        for key in sorted(dets, key=repr):
            const = 0
            ls = []
            for l in dets[key]:
                if l is True:
                    const ^= 1
                elif l is False:
                    continue
                else:
                    ls.append(l)
            if not ls:
                if const:
                    return []
                continue
            lists.append((const, ls))
        base = sorted({abs(l) for _, ls in lists for l in ls})
        if len(base) > nmax:
            cl = self.clauses_for_choice(pat, ch)
            return [] if cl is None else [cl]
        pos = {v: i for i, v in enumerate(base)}
        out = []
        for m in range(1 << len(base)):
            ok = True
            for const, ls in lists:
                par = const
                for l in ls:
                    val = (m >> pos[abs(l)]) & 1
                    par ^= val if l > 0 else 1 - val
                if par:
                    ok = False
                    break
            if ok:
                out.append(neg_cond + [(-v if (m >> pos[v]) & 1 else v) for v in base])
        return out

    def _dets(self, pat, ch):
        E = self.E
        basis, slots = pat
        rev = self.rev[basis]
        cond = []
        dets = {}
        di = 0
        for s in slots:
            if s[0] == "H":
                _, k, U, r = s
                for x in range(6):
                    if x in U:
                        continue
                    for u in U:
                        cond.append(E.LT((k, x), (k, u), 0))
                for a in U:
                    g = (k, a)
                    for f in rev[support(k)[a]]:
                        self.contrib(dets, g, f, r)
            elif s[0] == "D":
                _, q, r = s
                fs = ch[di]
                di += 1
                for f in rev[q]:
                    if f == fs:
                        dets.setdefault((f[0], r), []).append(True)
                    else:
                        self.contrib(dets, fs, f, r)
            else:
                _, c, r = s
                dets.setdefault((c, r), []).append(True)
                dets.setdefault((c, r + 1), []).append(True)
        if any(c is False for c in cond):
            return None, None
        return dets, cond

    def clauses_for_choice(self, pat, ch):
        """the clause for one choice of f* (one reader event per data slot), or None if trivially satisfied."""
        E = self.E
        basis, slots = pat
        rev = self.rev[basis]
        cond = []
        dets = {}
        di = 0
        for s in slots:
            if s[0] == "H":
                _, k, U, r = s
                for x in range(6):
                    if x in U:
                        continue
                    for u in U:
                        cond.append(E.LT((k, x), (k, u), 0))
                for a in U:
                    g = (k, a)
                    for f in rev[support(k)[a]]:
                        self.contrib(dets, g, f, r)
            elif s[0] == "D":
                _, q, r = s
                fs = ch[di]
                di += 1
                for f in rev[q]:
                    if f == fs:
                        dets.setdefault((f[0], r), []).append(True)
                    else:
                        self.contrib(dets, fs, f, r)
            else:
                _, c, r = s
                dets.setdefault((c, r), []).append(True)
                dets.setdefault((c, r + 1), []).append(True)
        if any(c is False for c in cond):
            return None
        cl = [neg(c) for c in cond if c is not True]
        for key in sorted(dets, key=repr):
            y = E.XOR(dets[key])
            if y is True:
                return None
            if y is False:
                continue
            cl.append(y)
        return cl


def load_patterns(path):
    out = []
    for b, slots in json.load(open(path)):
        sl = []
        for x in slots:
            if x[0] == "D":
                sl.append(("D", x[1], x[2]))
            elif x[0] == "H":
                sl.append(("H", tuple(x[1]), tuple(x[2]), x[3]))
            else:
                sl.append(("M", tuple(x[1]), x[2]))
        out.append((b, tuple(sl)))
    return out


def expand(pat):
    """variants of a pattern with each data slot's round shifted by -1, 0, +1 (each variant is itself a pattern)."""
    b, slots = pat
    opts = []
    for x in slots:
        if x[0] == "D":
            opts.append([("D", x[1], x[2] + dr) for dr in (-1, 0, 1)])
        else:
            opts.append([x])
    out = []
    for comb in itertools.product(*opts):
        rmin = min(y[-1] for y in comb)
        norm = []
        for y in comb:
            norm.append(y[:-1] + (y[-1] - rmin,))
        out.append((b, tuple(sorted(norm, key=repr))))
    return out


def save_patterns(path, pats):
    with open(path, "w") as f:
        json.dump([[p[0], [list(map(_js, sl)) for sl in p[1]]] for p in pats], f)


class ExtSolver:
    """CaDiCaL 3.0.1 binary, from scratch on every call (no time limit).  Writes the DIMACS and a DRAT proof."""

    def __init__(self, tag):
        self.cnf = f"{OUT}/cur_{tag}.cnf"
        self.proof = f"{OUT}/cur_{tag}.drat"

    def solve(self, E):
        import subprocess
        with open(self.cnf, "w") as f:
            f.write(f"p cnf {E.nv} {len(E.cl)}\n")
            for c in E.cl:
                f.write(" ".join(map(str, c)) + " 0\n")
        r = subprocess.run(["tools/cadical/build/cadical", "-q", "--binary=false", self.cnf, self.proof],
                           capture_output=True, text=True)
        model = []
        st = None
        for line in r.stdout.splitlines():
            if line.startswith("s "):
                st = line[2:].strip()
            elif line.startswith("v "):
                model += [int(x) for x in line[2:].split() if x != "0"]
        assert st in ("SATISFIABLE", "UNSATISFIABLE"), r.stdout[-500:] + r.stderr[-500:]
        return st == "SATISFIABLE", model


def run(variant, cls, arg, d, W, limit, max_iter, dump, tag, solver_name="cd15", external=False, resume=None,
        do_expand=False, delta=None):
    E = Enc(variant, cls, arg, delta)
    PE = PatternEncoder(E)
    PE.direct = DIRECT
    pats = {}
    if resume:
        for pat in load_patterns(resume):
            cls_ = PE.clauses(pat)
            pats[pat] = len(cls_)
            for c in cls_:
                E.add(c)
    if external:
        xs = ExtSolver(tag)
    else:
        s = Solver(name=solver_name, bootstrap_with=E.cl)
    ptr = len(E.cl)
    t0 = time.time()
    res = None
    log = open(f"{OUT}/cegar_{tag}.log", "a")
    for it in range(max_iter):
        ts = time.time()
        if external:
            sat, model = xs.solve(E)
        else:
            for c in E.cl[ptr:]:
                s.add_clause(c)
            ptr = len(E.cl)
            sat = s.solve()
            model = s.get_model() if sat else None
        tsolve = time.time() - ts
        if not sat:
            res = {"result": "UNSAT", "iters": it, "patterns": len(pats)}
            break
        sch = E.decode(model)
        ok, why = legal(sch)
        assert ok, why
        w, wits = bulk_min(sch, d - 1, W=W, want_all=True, limit=limit)
        if w is None:
            w2, wits2 = bulk_min(sch, d - 1, W=12, want_all=True, limit=limit)
            if w2 is None:
                res = {"result": "FOUND", "iters": it, "patterns": len(pats), "sched": sch.to_json()}
                with open(f"{OUT}/found_{tag}_{it}.json", "w") as f:
                    json.dump(sch.to_json(), f)
                break
            wits, w = wits2, w2
        new = 0
        for b, tags in wits:
            base = pattern_of(b, tags)
            for pat in (expand(base) if do_expand else [base]):
                if pat in pats:
                    continue
                cls_ = PE.clauses(pat)
                if any(len(c) == 0 for c in cls_):
                    res = {"result": "UNSAT(schedule-independent pattern)", "pattern": repr(pat)}
                    break
                pats[pat] = len(cls_)
                for c in cls_:
                    E.add(c)
                new += 1
            if res:
                break
        if res:
            break
        if new == 0:
            raise RuntimeError("no new pattern: the abstraction failed to exclude the current schedule")
        msg = json.dumps([it, len(pats), E.nv, len(E.cl), w, round(tsolve, 1), round(time.time() - t0, 1)])
        log.write(msg + "\n")
        log.flush()
        if it % 20 == 0:
            print(msg, flush=True)
            save_patterns(f"{OUT}/cegar_{tag}_patterns.json", pats)
    else:
        res = {"result": "MAXITER", "iters": max_iter, "patterns": len(pats)}
    res.update({"variant": variant, "cls": cls, "arg": arg, "d": d, "W": W, "limit": limit, "expand": do_expand,
                "vars": E.nv, "clauses": len(E.cl), "sec": round(time.time() - t0, 1)})
    print(json.dumps(res), flush=True)
    log.write(json.dumps(res) + "\n")
    with open(f"{OUT}/cegar.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")
    save_patterns(f"{OUT}/cegar_{tag}_patterns.json", pats)
    if dump:
        with open(f"{OUT}/cegar_{tag}.cnf", "w") as f:
            f.write(f"p cnf {E.nv} {len(E.cl)}\n")
            for c in E.cl:
                f.write(" ".join(map(str, c)) + " 0\n")
    return res, E, pats


def _js(x):
    if isinstance(x, tuple):
        return [_js(y) for y in x]
    return x


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cls")
    ap.add_argument("arg", type=int)
    ap.add_argument("--variant", default="bb18")
    ap.add_argument("--d", type=int, default=4)
    ap.add_argument("--W", type=int, default=6)
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--max-iter", type=int, default=100000)
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--solver", default="cd15")
    ap.add_argument("--external", action="store_true")
    ap.add_argument("--expand", action="store_true")
    ap.add_argument("--resume")
    ap.add_argument("--tag", default="")
    ap.add_argument("--direct", action="store_true")
    ap.add_argument("--delta", type=int)
    a = ap.parse_args()
    DIRECT = a.direct
    tag = f"{a.variant}_{a.cls}{a.arg}_d{a.d}{a.tag}" + (f"_delta{a.delta}" if a.delta is not None else "")
    run(a.variant, a.cls, a.arg, a.d, a.W, a.limit, a.max_iter, a.dump, tag, a.solver, a.external, a.resume,
        a.expand, a.delta)
