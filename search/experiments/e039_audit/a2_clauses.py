"""E-039 audit a2: soundness (and per-basis completeness) of E-039's finite-R CNF on sampled N(S) schedules.

Bookkeeping only from E-039: I rebuild its CNF with its own encoder (finite_static's loop, replicated choice by choice
so that every pattern clause is tagged with (pattern, reader choice)); the rebuilt DIMACS must have the published
sha256, otherwise the run is void.  Everything that JUDGES uses my own code (fcore: own stim circuit, own exact search,
own legality, own injection):
  * every pattern clause falsified by a schedule must be a real witness: inject the slot faults (D: relevant Pauli
    on q just before the chosen reader's CNOT in round r, or before the final readout for r = R; H: ancilla Pauli right
    after the last CNOT of the spreader that is NOT in U, after checking U is the time suffix; M: ancilla Pauli just
    before the reader's measurement) into a noiseless copy of MY circuit -> no detector may fire and some observable
    must flip;  the residual must be a non-trivial logical by my own GF(2);
  * per basis: (some clause of that basis falsified) vs (my exact DEM min weight <= 3), and the smallest falsified
    pattern size vs my min weight;
  * legality: every schedule of my own sampler must satisfy E-039's legality+definition part.
usage: uv run python -m search.experiments.e039_audit.a2_clauses --R 1 --S 7 --n 40 [--types ...] [--sha <prefix>]"""
import argparse
import hashlib
import itertools
import json
import random
import time

from pysat.solvers import Solver

from search.experiments.e039_audit import fcore as F
from search.experiments.e039_audit.samp import Sampler

OUT = "results/E-039-audit"


def build(S, R, types):
    from search.experiments.e038.enc import Enc
    from search.experiments.e039 import finite
    from search.experiments.e039.finite_static import patterns
    from search.experiments.e039.static import multisets
    E = Enc("bb18", "N", S)
    PE = finite.FinitePE(E, R)
    tags = {}            # clause index -> (pattern, choice)
    for b in ("Z", "X"):
        rev = PE.rev[b]
        for m in multisets("bb18", b, set(types)):
            for pat in patterns(b, m, R):
                choices = [rev[s[1]] for s in pat[1] if s[0] == "D"]
                outs = []
                for ch in itertools.product(*choices):
                    c = PE.clauses_for_choice(pat, ch)
                    if c is not None:
                        outs.append((c, ch))
                for c, ch in outs:
                    n0 = len(E.cl)
                    E.add(c)
                    assert len(E.cl) == n0 + 1 and E.cl[-1]
                    tags[n0] = (pat, ch)
    return E, tags


def dimacs_sha(E):
    h = hashlib.sha256()
    h.update(f"p cnf {E.nv} {len(E.cl)}\n".encode())
    for c in E.cl:
        h.update((" ".join(map(str, c)) + " 0\n").encode())
    return h.hexdigest()


def inject_list(tau, S, R, pat, ch):
    b, slots = pat
    P = S + 2
    pa = "X" if b == "Z" else "Z"
    inj = []
    di = 0
    e = [0] * F.ND
    for s in slots:
        if s[0] == "D":
            _, q, r = s
            fs = ch[di]
            di += 1
            assert F.SUPP[fs[0]][fs[1]] == q
            layer = R * P if r == R else r * P + tau[fs]
            inj.append((layer, "pre", q, pa))
            e[q] ^= 1
        elif s[0] == "H":
            _, k, U, r = s
            order = sorted(range(6), key=lambda a: tau[(k, a)])
            p = 6 - len(U)
            if set(order[p:]) != set(U):
                return None, None
            inj.append((r * P + tau[(k, order[p - 1])], "post", F.ND + F.KS.index(k), pa))
            for a in U:
                e[F.SUPP[k][a]] ^= 1
        else:
            _, c, r = s
            inj.append((r * P + S + 1, "pre", F.ND + F.KS.index(c), "X" if c[0] == "Z" else "Z"))
    return inj, e


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--S", type=int, default=7)
    ap.add_argument("--R", type=int, default=1)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--types", default="HH,HHM,DDH,DHH,HHH")
    ap.add_argument("--sha", default=None, help="expected sha256 of the rebuilt DIMACS")
    ap.add_argument("--seed", type=int, default=1027)
    ap.add_argument("--maxphys", type=int, default=400)
    ap.add_argument("--noreset", action="store_true", help="judge with my NO-RESET circuit (own distance + injection)")
    ap.add_argument("--neg", type=int, default=300, help="random NON-falsified tagged clauses injected per schedule")
    ap.add_argument("--extra", default="", help="comma list of schedule json files (E-038 Sched.to_json or spec)")
    a = ap.parse_args()
    import numpy as np
    t0 = time.time()
    E, tags = build(a.S, a.R, a.types.split(","))
    sha = dimacs_sha(E)
    print(json.dumps({"vars": E.nv, "clauses": len(E.cl), "pattern_clauses": len(tags), "sha256": sha,
                      "sha_ok": (a.sha is None) or sha.startswith(a.sha), "build_s": round(time.time() - t0)}), flush=True)
    if a.sha and not sha.startswith(a.sha):
        raise SystemExit("sha mismatch: run void")
    defs = [c for i, c in enumerate(E.cl) if i not in tags]
    sol = Solver(name="cd15", bootstrap_with=defs)
    rng = random.Random(a.seed)
    sp = Sampler(a.S, seed=a.seed)
    scheds = []
    for path in [p for p in a.extra.split(",") if p]:
        d = json.load(open(path))
        if "sched" in d:
            d = d["sched"]
        tau = {}
        for row in d["checks"]:
            k = tuple(row["check"])
            for i, t in enumerate(row["tau"]):
                tau[(k, i)] = t - row["prep"]
        scheds.append((path, tau))
    for i in range(a.n):
        scheds.append((f"sample{i}", sp.sample()))
    tot = {"S": a.S, "R": a.R, "types": a.types, "noreset": a.noreset, "schedules": 0, "legal_rejected": 0, "falsified": 0,
           "phys_checked": 0, "phys_fail": 0, "resid_fail": 0, "basis_agree": 0, "basis_disagree": 0,
           "minw_agree": 0, "minw_disagree": 0, "only_unencoded": 0,
           "neg_checked": 0, "neg_fired": 0, "neg_nonsuffix": 0, "neg_undetected_logical": 0}
    tagkeys = list(tags)
    out = open(f"{OUT}/a2_R{a.R}_S{a.S}{'_noreset' if a.noreset else ''}.jsonl", "a")
    for name, tau in scheds:
        assert F.legal(tau, a.S), name
        units = []
        for e, iv in E.tau.items():
            for t, v in iv.u.items():
                units.append(v if tau[e] <= t else -v)
        if not sol.solve(assumptions=units):
            tot["legal_rejected"] += 1
            print("LEGALITY REJECTS", name, flush=True)
            continue
        mod = set(sol.get_model())
        fal = {"Z": [], "X": []}
        for ci, (pat, ch) in tags.items():
            if all(-l in mod for l in E.cl[ci]):
                fal[pat[0]].append((pat, ch))
        tot["schedules"] += 1
        rec = {"name": name}
        for b in "ZX":
            w = F.dist(tau, a.S, b, a.R, reset=not a.noreset)
            fl = fal[b]
            tot["falsified"] += len(fl)
            mins = min((len(p[1]) for p, _ in fl), default=None)
            agree = (w is not None) == bool(fl)
            if agree:
                tot["basis_agree"] += 1
            else:
                tot["basis_disagree"] += 1
                if w is not None and not fl:
                    tot["only_unencoded"] += 1
            if fl:
                if mins == w:
                    tot["minw_agree"] += 1
                else:
                    tot["minw_disagree"] += 1
            sample = fl if len(fl) <= a.maxphys else rng.sample(fl, a.maxphys)
            nf = 0
            for pat, ch in sample:
                inj, e = inject_list(tau, a.S, a.R, pat, ch)
                if inj is None:
                    nf += 1
                    continue
                c, _ = F.circuit(tau, a.S, b, a.R, inject=inj, reset=not a.noreset)
                det, obs = F.fires(c)
                if det or not obs:
                    nf += 1
                    print("PHYS FAIL", name, b, pat, ch, det, obs, flush=True)
                if not F.is_logical_residual(np.array(e, np.uint8), b):
                    tot["resid_fail"] += 1
                tot["phys_checked"] += 1
            tot["phys_fail"] += nf
            rec[b] = {"w_mine": w, "n_falsified": len(fl), "min_pattern": mins, "phys": len(sample), "phys_fail": nf}
        fset = set(id(x) for b in "ZX" for x in fal[b])
        falsified_ci = {ci for ci in tags if all(-l in mod for l in E.cl[ci])}
        appl = []
        for ci in tagkeys:
            if ci in falsified_ci:
                continue
            pat, ch = tags[ci]
            inj, e = inject_list(tau, a.S, a.R, pat, ch)
            if inj is None:
                tot["neg_nonsuffix"] += 1
            else:
                appl.append((ci, inj))
        for ci, inj in rng.sample(appl, min(a.neg, len(appl))):
            pat, ch = tags[ci]
            c, _ = F.circuit(tau, a.S, pat[0], a.R, inject=inj, reset=not a.noreset)
            det, obs = F.fires(c)
            tot["neg_checked"] += 1
            tot["neg_fired"] += det
            if not det and obs:
                tot["neg_undetected_logical"] += 1
                print("NEG UNDETECTED (clause not falsified but physical witness)", name, pat, ch, flush=True)
        out.write(json.dumps(rec) + "\n")
        out.flush()
        print(json.dumps(rec), flush=True)
    tot["sec"] = round(time.time() - t0)
    print(json.dumps(tot), flush=True)
    with open(f"{OUT}/a2_summary.jsonl", "a") as f:
        f.write(json.dumps(tot) + "\n")
