"""E-038 audit: controls for my CNF translations.  (a) N8 (d_circ = 4) as assumptions in my NCNF(8) and my GCNF N(8),
each with ALL of E-038's non-wrapping pattern files: must be SAT (no clause may exclude a distance-4 schedule).
(b) Kunlun (S = 7) as assumptions in NCNF(7) / GCNF N(7) + final_N7 patterns: must be UNSAT (it has weight-3 witnesses).
usage: uv run python -m search.experiments.e038_audit.b4c_cnf_controls"""
import glob
import json

from pysat.solvers import Solver

from search.experiments.e038_audit import acore as C
from search.experiments.e038_audit import gcnf, gpat, npat
from search.experiments.e038_audit.b1_certify import kunlun_spec

files = sorted(f for f in glob.glob("results/E-038-bb18-d4/*_patterns.json")
               if any(s in f for s in ("_N6_", "_N7_", "_N8_", "final_N7", "seed_N7")) and "full" not in f)
pats = {}
for f in files:
    for p in json.load(open(f)):
        pats[json.dumps(p)] = npat.norm_pattern(p)
pats = list(pats.values())
out = {"n_patterns": len(pats)}
for name, spec, S in (("n8", "search/experiments/e038/bb18_n8_d4_spec.json", 8), ("kunlun", kunlun_spec(), 7)):
    P, sch = C.parse_spec(spec)
    tau = {(k, q): t for k, r in sch.items() for q, t in r["cx"].items()}
    use = pats if name == "n8" else [npat.norm_pattern(p) for p in json.load(open("results/E-038-bb18-d4/final_N7_patterns.json"))]
    G1 = npat.NCNF(S)
    sem1 = npat.NSem(S)
    for p in use:
        G1.cl += G1.pattern_clauses(sem1, p)
    s1 = Solver(name="cadical195", bootstrap_with=G1.cl)
    r1 = s1.solve(assumptions=[G1.x[e][tau[e]] for e in G1.ev])
    G2 = gcnf.nclass(S)
    sem2 = gpat.GSem(S + 2)
    for p in use:
        G2.cl += G2.pattern_clauses(sem2.readers, p)
    s2 = Solver(name="cadical195", bootstrap_with=G2.cl)
    r2 = s2.solve(assumptions=[G2.x[e][tau[e]] for e in G2.ev])
    out[name] = {"NCNF_sat": r1, "GCNF_sat": r2, "patterns_used": len(use)}
    print(name, out[name], flush=True)
json.dump(out, open("results/E-038-audit/b4c_cnf_controls.json", "w"), indent=1)
