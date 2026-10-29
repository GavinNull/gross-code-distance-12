"""Question C: as check_maps but on schedules without weight-2 bulk witnesses (legality + static HH clauses), so that
the comparison is made where it matters (min weight 3 vs >= 4).  usage: ... W8.pkl n seed"""
import random, sys, time
from pysat.solvers import Cadical153
from search.theory.C.project import load
from search.experiments.e038.enc import Enc
from search.experiments.e038.model import legal
from search.theory.C.check_maps_lib import insert, reverse, mw

D = load(sys.argv[1]); n, seed = int(sys.argv[2]), int(sys.argv[3]); rng = random.Random(seed)
E = Enc("bb18", "W", D["P"])           # same variable numbering for the legality part (deterministic construction)
S = Cadical153(bootstrap_with=D["base"] + [c for tag, t, c in D["tagged"] if t == "HH"])
bad = 0; t0 = time.time()
for it in range(n):
    while True:
        ass = [l for k in E.ks[1:] for l in [E.pi[k].eq(rng.randrange(D["P"]))] if l not in (True, False)]
        rng.shuffle(ass); m = len(ass)
        while m and not S.solve(assumptions=ass[:m]): m -= 1
        if m or S.solve(): break
    s = E.decode(S.get_model()); assert legal(s)[0]
    beta = rng.randrange(s.P); si, sr = insert(s, beta), reverse(s)
    assert legal(si)[0] and legal(sr)[0]
    row = []
    for b in ("Z", "X"):
        w0, c0, m0 = mw(s, b); wi, ci, mi = mw(si, b); wr, cr, mr = mw(sr, b)
        ok = m0 == mi and w0 == wi == wr
        bad += not ok
        row.append(f"{b}: w={w0} ins_same={m0 == mi} rev_w={wr}")
    print(it, " | ".join(row), flush=True)
print("mismatches", bad, round(time.time() - t0, 1), "s")
