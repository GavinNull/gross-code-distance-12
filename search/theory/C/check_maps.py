"""Question C: numerical check of Lemma 2 (layer insertion) and Lemma 3 (time reversal) on random legal schedules.
For each random legal W(P) schedule s (SAT on the legality CNF with random assumptions):
  ins  = s with one empty layer inserted before residue beta: period P+1 (a W(P+1) schedule);
         check: legal, bulk mechanism multisets (detector mask, observable mask) IDENTICAL in both bases.
  rev  = time reversal tau -> C - tau, (pi, mu) -> (C - mu, C - pi): check legal and exact min weight (<= 3) per basis,
         number of minimum-weight witnesses (up to 5000) equal.
usage: uv run python -m search.theory.C.check_maps P n seed"""
import random, sys, time
from pysat.solvers import Cadical153
from search.experiments.e038.enc import Enc
from search.experiments.e038.model import Sched, Bulk, legal
from search.experiments.e036_audit.core import min_weight_le

P, n, seed = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
rng = random.Random(seed)
E = Enc("bb18", "W", P)
S = Cadical153(bootstrap_with=E.cl)

def rand_sched():
    while True:
        ass = []
        for k in E.ks[1:]:
            l = E.pi[k].eq(rng.randrange(P))
            if l not in (True, False): ass.append(l)
        for e in rng.sample(E.ev, 20):
            l = E.tau[e].eq(rng.randrange(E.tau[e].lo, E.tau[e].hi + 1))
            if l not in (True, False): ass.append(l)
        rng.shuffle(ass)
        for m in range(len(ass), 0, -1):
            if S.solve(assumptions=ass[:m]):
                return E.decode(S.get_model())

def insert(s, beta):
    f = lambda t: t + (t - beta) // s.P + 1        # number of inserted layers at beta + jP <= t, shifted
    return Sched(s.variant, s.P + 1, {k: f(v) for k, v in s.pi.items()}, {k: f(v) for k, v in s.mu.items()},
                 {e: f(v) for e, v in s.tau.items()})

def reverse(s):
    C = max(s.mu.values()) + 1
    return Sched(s.variant, s.P, {k: C - s.mu[k] for k in s.ks}, {k: C - s.pi[k] for k in s.ks},
                 {e: C - v for e, v in s.tau.items()})

def mw(s, b):
    ms = Bulk(s, b, 6).mechs()
    w, wits = min_weight_le(ms, 3, want_all=True, limit=5000)
    return w, len(wits), sorted((m[0], m[1]) for m in ms)

bad = 0; t0 = time.time()
for it in range(n):
    s = rand_sched(); assert legal(s)[0]
    beta = rng.randrange(P)
    si, sr = insert(s, beta), reverse(s)
    assert legal(si)[0], legal(si); assert legal(sr)[0], legal(sr)
    row = []
    for b in ("Z", "X"):
        w0, c0, m0 = mw(s, b); wi, ci, mi = mw(si, b); wr, cr, mr = mw(sr, b)
        ok = (m0 == mi) and (w0, c0) == (wi, ci) and (w0, c0) == (wr, cr)
        bad += not ok
        row.append(f"{b}: w={w0} n={c0} ins_same_mechs={m0 == mi} rev=(w={wr},n={cr})")
    print(it, "beta", beta, " | ".join(row), flush=True)
print("mismatches", bad, "time", round(time.time() - t0, 1))
