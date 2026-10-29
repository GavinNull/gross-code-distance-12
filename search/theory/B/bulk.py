"""Question B (theory): the bulk step-pairing model of a periodic single-ancilla schedule.

Self-contained (reads only qec-schedule/v1 specs and the code matrices).  Conventions, Z-basis memory (X errors):
writers = X checks (ancilla control, an ancilla X after its (k-1)-th CNOT is deposited on q_k..q_6 at the times of
those CNOTs), readers = Z checks (ancilla target; instance t reads data qubit q at rho_z(q) + t P).  X basis: swap.

For a deposit of an error on data qubit q at (possibly half-integer) time u, reader z containing q sees it first in
instance  sigma_z(q, u) = min{t : rho_z(q) + t P > u}.  The measurement of instance t is
m_t = sum of deposits with sigma <= t, so a fault set is undetected in the bulk  <=>  for every reader z the multiset
of all its step indices (one per deposit on supp z, plus {t, t+1} for a flip of instance t) has even multiplicities.

A column realisation is
  ('d', q)        data error on q, free time: options = the cyclic cut patterns {z: sigma_z(q, u)}, u in [0, P) + 1/2;
  ('h', c, k)     hook of writer c after its (k-1)-th CNOT (k = 2..5, 1-based), suffix q_k..q_6; options: one pattern
                  {z: multiset of sigma_z(q, tau_c(q)) over q in suffix and supp z, reduced mod 2}.
Every option carries an integer shift variable x (round of the writer instance / of the data error).
"""
from __future__ import annotations

import itertools
import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]


# ------------------------------------------------------------------ codes
def code_mats(name):
    """(HX, HZ, LX, LZ) as uint8 arrays."""
    import sys
    for p in (str(ROOT), str(ROOT / "tests")):
        if p not in sys.path:
            sys.path.insert(0, p)
    if name in ("gross", "bb90", "bb108", "bb72", "bb288"):
        from evaluators.tasks import build_code, get_task
        task = {"gross": "gross-dcirc", "bb90": "bb90-dcirc", "bb108": "bb108-dcirc", "bb72": "bb72-dcirc",
                "bb288": "bb288-dcirc"}[name]
        c, _ = build_code(get_task(task), None)
    elif name.startswith("kunlun-"):
        from search.experiments.e036.common import code
        c = code(name.split("-", 1)[1])
    else:
        raise KeyError(name)
    f = lambda M: (np.asarray(M, np.int64) % 2).astype(np.uint8)
    return f(c.HX), f(c.HZ), f(c.LX), f(c.LZ)


# ------------------------------------------------------------------ schedule
class Sched:
    def __init__(self, spec: dict, mats, basis="Z"):
        self.P = P = int(spec["period"])
        HX, HZ, LX, LZ = mats
        self.n = HX.shape[1]
        W, Rd = (spec["x_checks"], spec["z_checks"]) if basis == "Z" else (spec["z_checks"], spec["x_checks"])
        self.H, self.L = (HZ, LZ) if basis == "Z" else (HX, LX)
        self.basis = basis

        def unroll(ch):
            p = int(ch["prep"]) % P
            ab = lambda s: p + ((int(s) - p) % P)
            ev = sorted((ab(s), int(q)) for q, s in ch["cnots"])
            assert len({t for t, _ in ev}) == 6 and all(t > p for t, _ in ev)
            m = ab(ch["meas"])
            assert m > ev[-1][0], "measurement before last CNOT"
            return {"prep": p, "meas": m, "order": [q for _, q in ev], "time": {q: t for t, q in ev}}
        self.writers = [unroll(c) for c in W]
        self.readers = [unroll(c) for c in Rd]
        # reader rows must be the rows of H (as sets) -- check
        Hset = {tuple(np.nonzero(r)[0]) for r in self.H}
        for r in self.readers:
            assert tuple(sorted(r["order"])) in Hset, "reader support not a row of H"
        self.zof = defaultdict(list)          # data qubit -> readers containing it
        for zi, r in enumerate(self.readers):
            for q in r["order"]:
                self.zof[q].append(zi)
        self.Hr = np.array([[1 if q in set(r["order"]) else 0 for q in range(self.n)] for r in self.readers],
                           np.uint8)

    def sigma(self, z, q, u):
        rho = self.readers[z]["time"][q]
        return int(np.floor((u - rho) / self.P)) + 1

    # -------- delta cochain
    def delta(self):
        """{(c, z): sorted list of sigma_z(q, tau_c(q)) over shared q}  (instance 0 of writer c)."""
        out = {}
        for c, w in enumerate(self.writers):
            sw = set(w["order"])
            for z, r in enumerate(self.readers):
                Q = sw & set(r["order"])
                if Q:
                    out[(c, z)] = sorted(self.sigma(z, q, w["time"][q]) for q in Q)
        return out

    def pairing_ok(self):
        """Pairing lemma: the trivial fault (writer ancilla error before its first CNOT) must be undetected, i.e. the
        multiset delta(c,z) has even multiplicities for every (c, z)."""
        bad = []
        for k, v in self.delta().items():
            cnt = defaultdict(int)
            for s in v:
                cnt[s] += 1
            if any(x % 2 for x in cnt.values()):
                bad.append((k, v))
        return bad

    # -------- realisations
    def hook_pattern(self, c, k):
        w = self.writers[c]
        suf = w["order"][k - 1:]
        pat = defaultdict(lambda: defaultdict(int))
        for q in suf:
            for z in self.zof[q]:
                pat[z][self.sigma(z, q, w["time"][q])] ^= 1
        return {z: tuple(sorted(s for s, b in d.items() if b)) for z, d in pat.items()
                if any(d.values())}, tuple(sorted(suf))

    def data_patterns(self, q):
        pats = []
        for u2 in range(2 * self.P):          # half-integers in [0, P) and their shifts: collect distinct patterns
            u = u2 / 2.0
            if u2 % 2 == 0:
                continue
            pat = {z: (self.sigma(z, q, u),) for z in self.zof[q]}
            # normalise by global shift: subtract min
            m = min(v[0] for v in pat.values())
            pat = {z: (v[0] - m,) for z, v in pat.items()}
            key = tuple(sorted(pat.items()))
            if key not in [tuple(sorted(p.items())) for p in pats]:
                pats.append(pat)
        return pats

    # -------- extended code
    def key(self, s):
        s = list(s)
        h = (self.H[:, s].sum(1) % 2).astype(np.uint8)
        lv = (self.L[:, s].sum(1) % 2).astype(np.uint8)
        return h.tobytes() + lv.tobytes()

    def ext(self):
        """columns: key -> list of realisations; zero_real = realisations with zero key (zero-image hooks)."""
        cols = defaultdict(list)
        zero = []
        z0 = self.key([])
        for q in range(self.n):
            cols[self.key([q])].append(("d", q))
        for c, w in enumerate(self.writers):
            for k in range(2, 6):
                suf = w["order"][k - 1:]
                kk = self.key(suf)
                if kk == z0:
                    zero.append(("h", c, k))
                else:
                    cols[kk].append(("h", c, k))
        return dict(cols), zero

    def options(self, real):
        if real[0] == "d":
            return self.data_patterns(real[1])
        return [self.hook_pattern(real[1], real[2])[0]]


# ------------------------------------------------------------------ exact bulk lift
class UF:
    def __init__(self, mod=0):
        self.p, self.o, self.mod = {}, {}, mod

    def find(self, a):
        if a not in self.p:
            self.p[a], self.o[a] = a, 0
            return a, 0
        off = 0
        while self.p[a] != a:
            off += self.o[a]
            a = self.p[a]
        return a, off

    def snapshot(self):
        return dict(self.p), dict(self.o)

    def restore(self, s):
        self.p, self.o = dict(s[0]), dict(s[1])

    def union(self, a, oa, b, ob):
        """impose x_a + oa = x_b + ob; return False on conflict."""
        ra, da = self.find(a)
        rb, db = self.find(b)
        # x_a = x_ra + da
        if ra == rb:
            if self.mod:
                return (da + oa - db - ob) % self.mod == 0
            return da + oa == db + ob
        # x_ra + da + oa = x_rb + db + ob  ->  x_ra = x_rb + (db + ob - da - oa)
        self.p[ra], self.o[ra] = rb, db + ob - da - oa
        return True


def _matchings(items):
    if not items:
        yield []
        return
    a = items[0]
    for i in range(1, len(items)):
        rest = items[1:i] + items[i + 1:]
        for m in _matchings(rest):
            yield [(a, items[i])] + m


def bulk_lift(colopts, flips=0, flip_readers=None, want_witness=False, mod=0, ignore=()):
    """colopts: list over columns of a list of options; option = dict reader -> tuple of offsets (relative to the
    column's shift variable).  flips: number of extra reader-instance flips allowed (each: items (t,0),(t,1) on one
    reader, t a fresh variable).  Returns a witness (choices) or None.  Exact for the bulk (unbounded rounds)."""
    ncol = len(colopts)
    touched = defaultdict(set)
    for i, opts in enumerate(colopts):
        for o in opts:
            for z in o:
                touched[z].add(i)
    for z in ignore:
        touched.pop(z, None)
    readers = sorted(touched)
    if flip_readers is None:
        flip_readers = readers
    # columns processed in order; reader z is checked when all columns touching it are chosen
    # greedy order: single-option columns first, then the column completing the most readers (ties: fewer options)
    order, chosen = [], set()
    rem = set(range(ncol))
    while rem:
        def score(i):
            done = sum(1 for z in readers if i in touched[z] and touched[z] - chosen - {i} == set())
            part = sum(1 for z in readers if i in touched[z] and touched[z] & chosen)
            return (-(len(colopts[i]) == 1), -done, -part, len(colopts[i]), i)
        i = min(rem, key=score)
        order.append(i); chosen.add(i); rem.discard(i)
    rank = {i: r for r, i in enumerate(order)}
    last = {z: max(touched[z], key=lambda i: rank[i]) for z in readers}
    due = defaultdict(list)
    for z, i in last.items():
        due[i].append(z)

    def check_reader(z, choice, uf, extra):
        items = []
        for i in touched[z]:
            for off in choice[i].get(z, ()):
                items.append((("c", i), off))
        items += extra.get(z, [])
        if len(items) % 2:
            return []
        out = []
        for m in _matchings(items):
            snap = uf.snapshot()
            ok = all(uf.union(a[0], a[1], b[0], b[1]) for a, b in m)
            if ok:
                out.append(uf.snapshot())
            uf.restore(snap)
        return out

    def rec(pos, choice, uf, extra):
        if pos == ncol:
            return dict(choice=dict(choice), extra=dict(extra))
        i = order[pos]
        entry = uf.snapshot()
        for o in colopts[i]:
            uf.restore(entry)
            choice[i] = o
            states = [uf.snapshot()]
            for z in due[i]:
                new = []
                for st in states:
                    uf.restore(st)
                    new += check_reader(z, choice, uf, extra)
                states = new
                if not states:
                    break
            for st in states:
                uf.restore(st)
                r = rec(pos + 1, choice, uf, extra)
                if r is not None:
                    return r
            del choice[i]
        uf.restore(entry)
        return None

    def with_flips(nf, start, extra):
        if nf == 0:
            return rec(0, {}, UF(mod), extra)
        r = rec(0, {}, UF(mod), extra)
        if r is not None:
            return r
        for zi in range(start, len(flip_readers)):
            z = flip_readers[zi]
            e2 = {k: list(v) for k, v in extra.items()}
            tv = ("t", nf, z)
            e2.setdefault(z, []).extend([(tv, 0), (tv, 1)])
            r = with_flips(nf - 1, zi, e2)
            if r is not None:
                return r
        return None

    return with_flips(flips, 0, {})


def load_spec(path):
    return json.load(open(ROOT / path))
