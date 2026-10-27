"""E-039 audit a6: soundness of E-039's bulk static CNFs for the pipelined classes (W(P), merged Mg(P)) inside the
synchronized subclasses, by physical injection into MY periodic circuit (pcore).

Bookkeeping from E-039 only: the CNF is rebuilt with E-039's own encoder in dump_static's order, every pattern
clause tagged with (pattern, choice); the DIMACS sha256 must equal the published one (else void).  Schedules are
sampled from E-039's legality part (random phases; subclass fixed by pi units) and must pass MY legality (pcore);
every falsified pattern clause must be a physical undetectable logical in my noiseless periodic circuit (no detector,
observable flipped, residual non-trivial by my GF(2)); random applicable NON-falsified clauses are injected as a
negative control (must fire, else the CNF is incomplete there -- harmless for UNSAT but reported).
usage: uv run python -m search.experiments.e039_audit.a6_wclass W 8 --types DDH2 --sha 2466a310 --sub X=0 --n 20"""
import argparse
import hashlib
import itertools
import json
import random
import time

import numpy as np
from pysat.solvers import Solver

from search.experiments.e039_audit import fcore as F
from search.experiments.e039_audit import pcore as PC


def build(cls, P, types):
    from search.experiments.e038.cegar import PatternEncoder
    from search.experiments.e039.scegar import make_enc
    from search.experiments.e039.static import multisets, patterns_of
    E = make_enc(cls, P)
    PE = PatternEncoder(E)
    tags = {}
    for b in ("Z", "X"):
        rev = PE.rev[b]
        for m in multisets("bb18", b, set(types)):
            for pat in patterns_of(b, m):
                outs = []
                for ch in itertools.product(*[rev[s[1]] for s in pat[1] if s[0] == "D"]):
                    c = PE.clauses_for_choice(pat, ch)
                    if c is not None:
                        outs.append((c, ch))
                for c, ch in outs:
                    n0 = len(E.cl)
                    E.add(c)
                    assert len(E.cl) == n0 + 1
                    tags[n0] = (pat, ch)
    for k in E.ks:
        for v in range(E.pi[k].lo, E.pi[k].hi + 1):
            E.pi[k].eq(v)
    return E, tags


def sha_of(E):
    h = hashlib.sha256()
    h.update(f"p cnf {E.nv} {len(E.cl)}\n".encode())
    for c in E.cl:
        h.update((" ".join(map(str, c)) + " 0\n").encode())
    return h.hexdigest()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cls")
    ap.add_argument("P", type=int)
    ap.add_argument("--types", default="DDH2")
    ap.add_argument("--sha", default=None)
    ap.add_argument("--sub", default="", help="X=0 / Z=d / '' (free)")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--neg", type=int, default=200)
    ap.add_argument("--maxphys", type=int, default=300)
    ap.add_argument("--extra", default="", help="schedule json (checks/prep/meas/tau) to evaluate (positive control)")
    a = ap.parse_args()
    t0 = time.time()
    E, tags = build(a.cls, a.P, a.types.split(","))
    sha = sha_of(E)
    head = {"cls": a.cls, "P": a.P, "types": a.types, "sub": a.sub, "vars": E.nv, "clauses": len(E.cl),
            "pattern_clauses": len(tags), "sha256": sha, "sha_ok": a.sha is None or sha.startswith(a.sha),
            "build_s": round(time.time() - t0)}
    print(json.dumps(head), flush=True)
    if a.sha and not sha.startswith(a.sha):
        raise SystemExit("sha mismatch: void")
    defs = [c for i, c in enumerate(E.cl) if i not in tags]
    sol = Solver(name="cd15", bootstrap_with=defs)
    rng = random.Random(a.seed)
    sub = []
    if a.sub:
        lhs, v = a.sub.split("=")
        for k in E.ks:
            if k[0] == lhs:
                l = E.pi[k].eq(int(v))
                assert l is not False
                if l is not True:
                    sub.append(l)
    merged = a.cls == "Mg"
    tot = dict(head, schedules=0, my_legal_fail=0, falsified=0, phys=0, phys_fail=0, resid_fail=0,
               neg=0, neg_fired=0, neg_undetected=0, bases_with_falsified=0)
    tagkeys = list(tags)
    todo = []
    if a.extra:
        d = json.load(open(a.extra))
        pi = {tuple(r["check"]): r["prep"] for r in d["checks"]}
        mu = {tuple(r["check"]): r["meas"] for r in d["checks"]}
        tau = {(tuple(r["check"]), i): t for r in d["checks"] for i, t in enumerate(r["tau"])}
        todo.append(("extra", (pi, mu, tau)))
    for i in range(a.n):
        todo.append((f"s{i}", None))
    for name, given in todo:
        if given is None:
            ev = list(E.tau)
            ass = list(sub)
            for e in rng.sample(ev, 1):
                l = E.tau[e].eq(rng.randint(E.tau[e].lo, E.tau[e].hi))
                if l not in (True, False):
                    ass.append(l)
            sol.set_phases([v if rng.random() < 0.5 else -v for v in range(1, E.nv + 1)])
            if not sol.solve(assumptions=ass):
                continue
            s = E.decode(sol.get_model())
            pi, mu, tau = s.pi, s.mu, s.tau
            mod = set(sol.get_model())
        else:
            pi, mu, tau = given
            units = []
            for e, iv in E.tau.items():
                units += [v if tau[e] <= t else -v for t, v in iv.u.items()]
            for k in E.ks:
                units += [v if pi[k] <= t else -v for t, v in E.pi[k].u.items()]
                units += [v if mu[k] <= t else -v for t, v in E.mu[k].u.items()]
            assert sol.solve(assumptions=units), "E-039 legality rejects the given schedule"
            mod = set(sol.get_model())
        if not PC.legal(a.P, pi, mu, tau, merged=merged):
            tot["my_legal_fail"] += 1
            print("MY LEGALITY REJECTS", name, flush=True)
            continue
        tot["schedules"] += 1
        fal = [ci for ci in tagkeys if all(-l in mod for l in E.cl[ci])]
        tot["falsified"] += len(fal)
        tot["bases_with_falsified"] += len({tags[ci][0][0] for ci in fal})
        nf = 0
        for ci in (fal if len(fal) <= a.maxphys else rng.sample(fal, a.maxphys)):
            pat, ch = tags[ci]
            inj, R, e = PC.inject_bulk(a.P, pi, mu, tau, pat, ch)
            if inj is None:
                nf += 1
                print("NONSUFFIX but falsified", name, pat, flush=True)
                continue
            c = PC.circuit(a.P, pi, mu, tau, pat[0], R, inj)
            det, obs = F.fires(c)
            tot["phys"] += 1
            if det or not obs:
                nf += 1
                print("PHYS FAIL", name, pat, ch, det, obs, flush=True)
            if not F.is_logical_residual(e, pat[0]):
                tot["resid_fail"] += 1
        tot["phys_fail"] += nf
        fs = set(fal)
        appl = []
        for ci in rng.sample(tagkeys, min(len(tagkeys), 40 * a.neg)):
            if ci in fs:
                continue
            pat, ch = tags[ci]
            inj, R, e = PC.inject_bulk(a.P, pi, mu, tau, pat, ch)
            if inj is not None:
                appl.append((pat, inj, R))
            if len(appl) >= a.neg:
                break
        for pat, inj, R in appl:
            c = PC.circuit(a.P, pi, mu, tau, pat[0], R, inj)
            det, obs = F.fires(c)
            tot["neg"] += 1
            tot["neg_fired"] += det
            if not det and obs:
                tot["neg_undetected"] += 1
        print(json.dumps({"name": name, "falsified": len(fal), "phys_fail": nf, "pi": sorted(set(pi.values()))}), flush=True)
    tot["sec"] = round(time.time() - t0)
    print(json.dumps(tot), flush=True)
    with open("results/E-039-audit/a6_summary.jsonl", "a") as f:
        f.write(json.dumps(tot) + "\n")
