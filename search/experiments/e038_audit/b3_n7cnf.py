"""E-038 audit, claim 3: independent re-derivation of "N7 is UNSAT for d_circ = 4".
My CNF (npat.NCNF: one-hot layers, own order variables, own legality, own Tseitin) + my translation of each pattern
of E-038's final_N7_patterns.json into clauses (npat.NCNF.pattern_clauses, from my semantics; the patterns are only
used as hypotheses: each clause is sound iff my semantics are right, which b2/b4 test physically).
Cubes: the layers (t1, t2), t1 != t2, of check Z0's CNOTs on its two lowest-index qubits (42 cubes; a different split
from E-038's X0 cubes).  Each cube: CNF + 2 unit clauses, solved by pysat CaDiCaL 1.9.5 (or by tools/cadical with a
DRAT proof checked by drat-trim, --drat).
usage: uv run python -m search.experiments.e038_audit.b3_n7cnf build
       uv run python -m search.experiments.e038_audit.b3_n7cnf solve --shard i/n [--drat]"""
import argparse
import hashlib
import itertools
import json
import os
import subprocess
import time

from search.experiments.e038_audit import npat

OUT = "results/E-038-audit"
PAT = "results/E-038-bb18-d4/final_N7_patterns.json"
PREFIX = f"{OUT}/my_N7"


def build(extra=None):
    G = npat.NCNF(7)
    sem = npat.NSem(7)
    raw = json.load(open(PAT))
    files = [PAT] + (extra or [])
    seen = set()
    npc = 0
    for f in files:
        for p in json.load(open(f)):
            key = json.dumps(p)
            if key in seen:
                continue
            seen.add(key)
            for c in G.pattern_clauses(sem, npat.norm_pattern(p)):
                G.cl.append(c)
                npc += 1
    k0 = ("Z", 0)
    qs = sorted(q for (k, q) in G.ev if k == k0)[:2]
    cubes = [[G.x[(k0, qs[0])][t1], G.x[(k0, qs[1])][t2]] for t1 in range(1, 8) for t2 in range(1, 8) if t1 != t2]
    with open(PREFIX + ".cnf", "w") as f:
        f.write(f"p cnf {G.nv} {len(G.cl)}\n")
        for c in G.cl:
            f.write(" ".join(map(str, c)) + " 0\n")
    json.dump(cubes, open(PREFIX + "_cubes.json", "w"))
    h = hashlib.sha256(open(PREFIX + ".cnf", "rb").read()).hexdigest()
    info = {"vars": G.nv, "clauses": len(G.cl), "legality_clauses": G.nleg, "pattern_clauses": npc,
            "patterns": len(seen), "cubes": len(cubes), "cube_events": [str(k0), qs], "sha256": h}
    json.dump(info, open(PREFIX + "_info.json", "w"))
    print(json.dumps(info))


def solve(shard, n, drat, only=None):
    from pysat.formula import CNF
    from pysat.solvers import Solver
    cubes = json.load(open(PREFIX + "_cubes.json"))
    out = open(f"{PREFIX}_cubes_{'drat' if drat else 'pysat'}_{shard}of{n}.jsonl", "a")
    if not drat:
        F = CNF(from_file=PREFIX + ".cnf")
    for i, cb in enumerate(cubes):
        if i % n != shard or (only is not None and i not in only):
            continue
        t0 = time.time()
        if drat:
            hdr, body = open(PREFIX + ".cnf").read().split("\n", 1)
            _, _, nv, nc = hdr.split()
            tmp = f"{PREFIX}_tmp{shard}"
            with open(tmp + ".cnf", "w") as f:
                f.write(f"p cnf {nv} {int(nc) + len(cb)}\n{body}")
                for l in cb:
                    f.write(f"{l} 0\n")
            r = subprocess.run(["tools/cadical/build/cadical", "-q", tmp + ".cnf", tmp + ".drat"], capture_output=True,
                               text=True)
            st = [l for l in r.stdout.splitlines() if l.startswith("s ")]
            v = subprocess.run(["tools/drat-trim/drat-trim", tmp + ".cnf", tmp + ".drat", "-t", "40000"],
                               capture_output=True, text=True)
            rec = {"cube": i, "lits": cb, "result": st[0] if st else None, "drat_verified": "s VERIFIED" in v.stdout,
                   "proof_sha256": hashlib.sha256(open(tmp + ".drat", "rb").read()).hexdigest()}
            os.remove(tmp + ".drat")
            os.remove(tmp + ".cnf")
        else:
            s = Solver(name="cadical195", bootstrap_with=F.clauses)
            sat = s.solve(assumptions=cb)
            rec = {"cube": i, "lits": cb, "result": "SAT" if sat else "UNSAT"}
            if sat:
                rec["model_pos"] = [l for l in s.get_model() if l > 0]
            s.delete()
        rec["sec"] = round(time.time() - t0, 1)
        out.write(json.dumps(rec) + "\n")
        out.flush()
        print(json.dumps({k: v for k, v in rec.items() if k != "model_pos"}), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--drat", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    if a.cmd == "build":
        build()
    else:
        sh, n = map(int, a.shard.split("/"))
        solve(sh, n, a.drat, [int(x) for x in a.only.split(",")] if a.only else None)
