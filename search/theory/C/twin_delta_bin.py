"""Question C: like twin_delta but with the CaDiCaL binary and a hard wall-clock limit (-t).
S given as the checks to DROP (names), e.g. 'X3,Z2'.  usage: ... W8.pkl r DROP tmax"""
import os, subprocess, sys, time
from search.theory.C.project import load
from search.theory.C.solve_rel import rel_clauses, name
D = load(sys.argv[1]); ks = D["ks"]; r = int(sys.argv[2]); drop = set(sys.argv[3].split(",")) - {""}
tmax = int(sys.argv[4])
S = {i for i, k in enumerate(ks) if name(k) not in drop}
ix, iz = ks.index(("X", r)), ks.index(("Z", r))
cl = list(D["base"]) + [c for tag, t, c in D["tagged"] if tag <= S]
print("S size", len(S), "clauses", len(cl), flush=True)
os.makedirs("results/theory-C/tmp", exist_ok=True)
for d in range(8):
    extra, nv = rel_clauses(D, [(ix, iz, d)], D["nv"])
    fn = f"results/theory-C/tmp/td_{r}_{d}.cnf"
    with open(fn, "w") as f:
        f.write(f"p cnf {nv} {len(cl) + len(extra)}\n")
        for c in cl + extra: f.write(" ".join(map(str, c)) + " 0\n")
    t0 = time.time()
    p = subprocess.run(["tools/cadical/build/cadical", "-q", "-n", "-t", str(tmax), fn], capture_output=True, text=True)
    st = [l for l in p.stdout.splitlines() if l.startswith("s ")]
    print("delta", d, st[0] if st else "s UNKNOWN(timeout)", round(time.time() - t0, 1), flush=True)
    os.remove(fn)
