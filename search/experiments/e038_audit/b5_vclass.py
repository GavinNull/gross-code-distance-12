"""E-038 audit, claim 3 (V classes): independent re-derivation of "V(P, delta) has no d_circ = 4 schedule".
(1) sample random legal V(P, delta) schedules from MY legality CNF (gcnf.vclass); for each: stim determinism of the
    noiseless periodic circuit (my legality is physically right), my semantics: >= 1 cancelling pattern of E-038's
    pattern file, physical injection check of cancelling instances + semantics-vs-physics on random instances;
(2) my CNF (my legality + my translation of E-038's V(P, delta) patterns) -> tools/cadical with DRAT -> drat-trim.
usage: uv run python -m search.experiments.e038_audit.b5_vclass P delta [--n 30] [--solve]"""
import argparse
import hashlib
import json
import os
import random
import subprocess
import time

from pysat.solvers import Solver

from search.experiments.e038_audit import gcnf, gpat, npat

OUT = "results/E-038-audit"


def main(P, d, n, solve, seed, patfile=None):
    pf = patfile or f"results/E-038-bb18-d4/cegar_bb18_V{P}_d4_delta{d}_patterns.json"
    pats = [npat.norm_pattern(p) for p in json.load(open(pf))]
    G = gcnf.vclass(P, d)
    sem = gpat.GSem(P)
    rng = random.Random(seed)
    rep = {"P": P, "delta": d, "patterns": len(pats), "pattern_file": pf, "samples": 0, "nondet": 0, "illegal": 0,
           "no_cancel": 0, "phys_ok": 0, "phys_bad": 0, "sem_phys_checked": 0, "sem_phys_mismatch": 0}
    s = Solver(name="cadical195", bootstrap_with=G.cl)
    ks = G.ks
    pi = {k: 0 if k[0] == "X" else d for k in ks}
    mu = {k: (P - 1) if k[0] == "X" else d + P - 1 for k in ks}
    for it in range(n):
        ass = [G.x[e][rng.choice(list(G.x[e]))] for e in rng.sample(G.ev, 5)]
        s.set_phases([v if rng.random() < 0.5 else -v for v in range(1, G.nv + 1)])
        if not s.solve(assumptions=ass):
            continue
        tau = G.decode(s.get_model())
        rep["samples"] += 1
        ok, why = gpat.legal(P, pi, mu, tau)
        if not ok:
            rep["illegal"] += 1
        det_ok, msg = gpat.deterministic(P, pi, mu, tau)
        if not det_ok:
            rep["nondet"] += 1
        canc = [(i, ch) for i, p in enumerate(pats) for ch in sem.cancels(p, tau)]
        if not canc:
            rep["no_cancel"] += 1
        rng.shuffle(canc)
        for i, ch in canc[:10]:
            fired, no = gpat.physical(pats[i], ch, P, pi, mu, tau)
            if not fired and no:
                rep["phys_ok"] += 1
            else:
                rep["phys_bad"] += 1
        done = 0
        for _ in range(2000):
            if done >= 10:
                break
            i = rng.randrange(len(pats))
            ch = rng.choice(sem.choices(pats[i]))
            tg = sem.toggles(pats[i], ch, tau)
            if tg is None:
                continue
            done += 1
            fired, _ = gpat.physical(pats[i], ch, P, pi, mu, tau)
            rep["sem_phys_checked"] += 1
            if fired != tg:
                rep["sem_phys_mismatch"] += 1
        print(it, len(canc), flush=True)
    if solve:
        for p in pats:
            for c in G.pattern_clauses(sem.readers, p):
                G.cl.append(c)
        cnf = f"{OUT}/my_V{P}_delta{d}.cnf"
        with open(cnf, "w") as f:
            f.write(f"p cnf {G.nv} {len(G.cl)}\n")
            for c in G.cl:
                f.write(" ".join(map(str, c)) + " 0\n")
        t0 = time.time()
        r = subprocess.run(["tools/cadical/build/cadical", "-q", cnf, cnf[:-4] + ".drat"], capture_output=True, text=True)
        st = [l for l in r.stdout.splitlines() if l.startswith("s ")]
        rep["my_cnf"] = {"vars": G.nv, "clauses": len(G.cl), "sha256": hashlib.sha256(open(cnf, "rb").read()).hexdigest(),
                         "cadical": st[0] if st else r.stdout[-200:], "solve_sec": round(time.time() - t0, 1)}
        if st and st[0] == "s UNSATISFIABLE":
            v = subprocess.run(["tools/drat-trim/drat-trim", cnf, cnf[:-4] + ".drat", "-t", "40000"], capture_output=True,
                               text=True)
            rep["my_cnf"]["drat_verified"] = "s VERIFIED" in v.stdout
            rep["my_cnf"]["proof_sha256"] = hashlib.sha256(open(cnf[:-4] + ".drat", "rb").read()).hexdigest()
            os.remove(cnf[:-4] + ".drat")
        rep["my_cnf"]["total_sec"] = round(time.time() - t0, 1)
    print(json.dumps(rep), flush=True)
    with open(f"{OUT}/b5_vclass.jsonl", "a") as f:
        f.write(json.dumps(rep) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("P", type=int)
    ap.add_argument("delta", type=int)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--solve", action="store_true")
    ap.add_argument("--patfile")
    a = ap.parse_args()
    main(a.P, a.delta, a.n, a.solve, a.seed, a.patfile)
