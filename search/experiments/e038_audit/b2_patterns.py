"""E-038 audit, claim 3 (N7): soundness of the pattern nogoods, tested from three sides on random legal N7 schedules
drawn from MY legality CNF (npat.NCNF, random phases):
  (i)   my semantics (npat.NSem): every sampled legal schedule must have >= 1 cancelling pattern instance (otherwise
        the UNSAT certificate wrongly excludes it, or my semantics are wrong -> investigate);
  (ii)  physical: cancelling instances are injected as deterministic Paulis into a noiseless stim circuit of the
        schedule: must give 0 detectors and a flipped observable (independent of any fault model);
  (iii) E-038's own final_N7.cnf: rebuilt with E-038's encoder only to know which clause came from which pattern
        (bookkeeping; the rebuild must hash to the published sha256), aux values fixed by solving its non-pattern
        clauses under the schedule's primary literals; the set of patterns with a FALSIFIED clause must equal (and in
        any case be a subset of) the set my semantics says cancel.  A falsified clause whose pattern does not cancel
        = unsound clause.
usage: uv run python -m search.experiments.e038_audit.b2_patterns --n 40 --seed 5 [--phys 30]"""
import argparse
import hashlib
import json
import random
import time

from pysat.solvers import Solver

from search.experiments.e038_audit import npat

PAT = "results/E-038-bb18-d4/final_N7_patterns.json"
CNF = "results/E-038-bb18-d4/final_N7.cnf"


def their_cnf():
    """rebuild final_N7.cnf with E-038's own encoder, recording clause -> pattern index."""
    from search.experiments.e038.cegar import PatternEncoder, load_patterns
    from search.experiments.e038.enc import Enc
    E = Enc("bb18", "N", 7)
    PE = PatternEncoder(E)
    pats = load_patterns(PAT)
    owner = {}
    for i, p in enumerate(pats):
        for c in PE.clauses(p):
            E.add(c)
            owner[len(E.cl) - 1] = i
    txt = f"p cnf {E.nv} {len(E.cl)}\n" + "".join(" ".join(map(str, c)) + " 0\n" for c in E.cl)
    h = hashlib.sha256(txt.encode()).hexdigest()
    return E, owner, h


def their_primary(E, tau_mine):
    """order-encoding literals of E-038's Enc for my schedule (tau keyed by (check, qubit))."""
    from search.experiments.e036_audit.core import support
    lits = []
    for (k, a), iv in E.tau.items():
        t = tau_mine[(k, support(k)[a])]
        for tt, v in iv.u.items():
            lits.append(v if t <= tt else -v)
    return lits


def main(n, seed, phys, cross):
    rng = random.Random(seed)
    sem = npat.NSem(7)
    raw = json.load(open(PAT))
    pats = [npat.norm_pattern(p) for p in raw]
    G = npat.NCNF(7)
    s = Solver(name="cadical195", bootstrap_with=G.cl)
    if cross:
        E, owner, h = their_cnf()
        rep_hash = h
        defs = [c for i, c in enumerate(E.cl) if i not in owner]
        sd = Solver(name="cadical195", bootstrap_with=defs)
        print("rebuilt final_N7 sha256", h, flush=True)
    out = open("results/E-038-audit/b2_patterns.jsonl", "a")
    tot = {"schedules": 0, "no_cancel": 0, "phys_ok": 0, "phys_bad": 0, "cnf_falsified_not_cancel": 0,
           "cancel_not_falsified": 0}
    for it in range(n):
        # random legal schedule: random assumptions on a few events + random phases
        G_ev = G.ev
        ass = []
        for e in rng.sample(G_ev, 6):
            t = rng.randint(1, 7)
            ass.append(G.x[e][t])
        s.set_phases([v if rng.random() < 0.5 else -v for v in range(1, G.nv + 1)])
        if not s.solve(assumptions=ass):
            continue
        tau = G.decode(s.get_model())
        t0 = time.time()
        canc = {}
        for i, p in enumerate(pats):
            ch = sem.cancels(p, tau)
            if ch:
                canc[i] = ch
        rec = {"it": it, "n_cancel_patterns": len(canc), "sem_sec": round(time.time() - t0, 1)}
        tot["schedules"] += 1
        if not canc:
            tot["no_cancel"] += 1
            rec["tau"] = {f"{k}|{q}": v for (k, q), v in tau.items()}
        # physical check of a sample of cancelling instances
        items = [(i, ch) for i, chs in canc.items() for ch in chs]
        rng.shuffle(items)
        bad = []
        for i, ch in items[:phys]:
            nd_, no = npat.physical(pats[i], ch, tau, 7)
            if nd_ == 0 and no > 0:
                tot["phys_ok"] += 1
            else:
                tot["phys_bad"] += 1
                bad.append((i, ch, nd_, no))
        rec["phys_bad"] = [str(b) for b in bad]
        # semantics vs physics on NON-cancelling instances: predicted toggle set must equal the fired set
        mism = 0
        done_ = 0
        for _ in range(200 * phys):
            if done_ >= phys:
                break
            i = rng.randrange(len(pats))
            chs = sem.choices(pats[i])
            ch = rng.choice(chs)
            tg = sem.toggles(pats[i], ch, tau)
            if tg is None:
                continue
            done_ += 1
            fired, _ = npat.physical(pats[i], ch, tau, 7, want_set=True)
            pred = {(k, r + 1) for k, r in tg}
            tot["sem_vs_phys_checked"] = tot.get("sem_vs_phys_checked", 0) + 1
            if fired != pred:
                mism += 1
                tot["sem_vs_phys_mismatch"] = tot.get("sem_vs_phys_mismatch", 0) + 1
        rec["sem_vs_phys_mismatch"] = mism
        if cross:
            prim = their_primary(E, tau)
            assert sd.solve(assumptions=prim), "E-038 legality/defs reject a legal schedule of mine"
            m = set(l for l in sd.get_model() if l > 0)
            fals = set()
            for ci, pi in owner.items():
                c = E.cl[ci]
                if not any((l > 0 and l in m) or (l < 0 and -l not in m) for l in c):
                    fals.add(pi)
            rec["their_falsified"] = len(fals)
            rec["falsified_not_cancel"] = sorted(fals - set(canc))
            rec["cancel_not_falsified"] = sorted(set(canc) - fals)
            tot["cnf_falsified_not_cancel"] += len(rec["falsified_not_cancel"])
            tot["cancel_not_falsified"] += len(rec["cancel_not_falsified"])
        out.write(json.dumps(rec) + "\n")
        out.flush()
        print(json.dumps({k: v for k, v in rec.items() if k != "tau"}), flush=True)
    tot["seed"] = seed
    if cross:
        tot["rebuilt_sha256"] = rep_hash
    print(json.dumps(tot), flush=True)
    out.write(json.dumps({"total": tot}) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--phys", type=int, default=30)
    ap.add_argument("--no-cross", action="store_true")
    a = ap.parse_args()
    main(a.n, a.seed, a.phys, not a.no_cross)
