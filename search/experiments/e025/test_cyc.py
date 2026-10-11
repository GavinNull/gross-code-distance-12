"""E-025 self-test: cycle description == Bellman-Ford frame model (e024a bf_P via e021.nwfull.evaluate_full) on random
legal deterministic circuits of a family (TimeSAT random phases).  usage: test_cyc P "sub" ncirc"""
import random, sys, time
import search.experiments.e021.nwfull as NF
from search.experiments.e021.nwsat import Family, parse_sub
from search.experiments.e024a.cegar import TimeSAT, bf_P
from search.experiments.e025.cyc import rec_cycles, blocked

P = int(sys.argv[1]); sub = sys.argv[2]; nc = int(sys.argv[3])
F = Family(parse_sub(sub) if sub else [(0, 0)])
recs, sk = NF.prepare_full(F, "XZ")
t0 = time.time()
RC = [rec_cycles(F, r) for r in recs]
print("recs", len(recs), "cycles total", sum(len(c) for cl in RC for c in cl), f"{time.time()-t0:.1f}s", flush=True)
M = TimeSAT(F, P)
rng = random.Random(5)
agree = dis = nb = 0
for k in range(nc):
    M.S.set_phases([rng.choice([1, -1]) * v for v in range(1, M.pool.top + 1)])
    t = M.solve()
    NF.bf_general = lambda cons, rank: bf_P(cons, t, P)
    lif = {id(x[0]) for x in NF.evaluate_full(F, recs, None)}
    for r, cl in zip(recs, RC):
        b = blocked(cl, t, P)
        if b == (id(r) not in lif):
            agree += 1; nb += b
        else:
            dis += 1
print(f"P={P} sub={sub!r} circuits={nc}: agree {agree} (blocked {nb}) disagree {dis} {time.time()-t0:.1f}s")
