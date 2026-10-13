"""Regenerate the final clause sets of the unsatisfiable CEGAR / SAT instances behind the optimality statements of the
paper (SM S10) and re-solve them from scratch with independent SAT solvers; write DIMACS + variable map + logs into
release/zenodo/certificates/.

    PYTHONPATH=.:tests uv run python scripts/zenodo/build_certificates.py <job>
jobs:
  gsat:P:nowrap            colour-symmetric family, primary encoding (search/experiments/e024b/gsat.py, run unchanged
                           except that its output directory is a scratch dir); nowrap=1: common frame
  timesat:P:sub[:extra]    second encoding (search/experiments/e024a/cegar.py, --tighten 0, as in the original runs and
                           the audit re-runs); sub = generators of the translation subgroup ("1,2;0,3" = all 24)
                           extra = "w14X0" / "w14Z2": CNOT window of that class <= 14 (P = 24, explanation only)
  uniq                     order-class uniqueness: the audit's replay CNFs (research/audits/2026-10-11-E-024b-scripts/
                           u1_dext.py, run unchanged except its output path), 24 colourings x 2 sides
The encoding solver is CaDiCaL 1.5.3 through PySAT; every clause given to it is recorded (Recorder).  The clause count
at the first solve() call separates the family encoding from the CEGAR nogoods.
"""
import gzip
import hashlib
import json
import os
import runpy
import sys
import time
from pathlib import Path

import pysat.solvers as PSV
from pysat.solvers import Cadical153, Glucose4, Minisat22

CERT = Path("release/zenodo/certificates")
SCRATCH = Path(os.environ.get("ZSCRATCH", "/tmp/zenodo_cert_scratch"))
SCRATCH.mkdir(parents=True, exist_ok=True)
RECS = []


class Recorder(Cadical153):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.cl, self.nfam, self.nsolve = [], None, 0
        RECS.append(self)

    def add_clause(self, cl, no_return=True):
        self.cl.append([int(x) for x in cl])
        return super().add_clause(cl, no_return)

    def solve(self, assumptions=[]):
        if self.nfam is None:
            self.nfam = len(self.cl)
        self.nsolve += 1
        assert not assumptions, "assumptions are not part of a clause-set certificate"
        return super().solve()


PSV.Cadical153 = Recorder


def resolve(clauses, nvars, budgets=(None, 5_000_000, 2_000_000)):
    out = {}
    for (nm, Sv), bud in zip((("cadical153", Cadical153), ("glucose4", Glucose4), ("minisat22", Minisat22)), budgets):
        t1 = time.process_time()
        with Sv(bootstrap_with=clauses) as s:
            if bud is None:
                r = s.solve()
            else:
                s.conf_budget(bud)
                r = s.solve_limited()
            st = s.accum_stats() if hasattr(s, "accum_stats") else {}
        out[nm] = {"result": {True: "SAT", False: "UNSAT", None: f"UNKNOWN (conflict budget {bud})"}[r],
                   "cpu_sec": round(time.process_time() - t1, 2), "conflict_budget": bud,
                   "stats": {k: int(v) for k, v in (st or {}).items()}}
        print(nm, out[nm]["result"], out[nm]["cpu_sec"], flush=True)
    return out


def write(sub, name, clauses, nfam, varmap, meta):
    d = CERT / sub
    d.mkdir(parents=True, exist_ok=True)
    nvars = max((abs(x) for c in clauses for x in c), default=0)
    head = [f"c {name}: {meta.get('what', '')}",
            f"c clauses 1..{nfam}: family encoding; clauses {nfam + 1}..{len(clauses)}: CEGAR nogoods" if nfam is not None
            else "c see README in this directory",
            f"p cnf {nvars} {len(clauses)}"]
    body = "\n".join(head) + "\n" + "\n".join(" ".join(map(str, c)) + " 0" for c in clauses) + "\n"
    with gzip.open(d / f"{name}.cnf.gz", "wt") as f:
        f.write(body)
    if varmap is not None:
        with gzip.open(d / f"{name}.varmap.json.gz", "wt") as f:
            json.dump(varmap, f, separators=(",", ":"))
    log = dict(meta, name=name, variables=nvars, clauses=len(clauses), family_clauses=nfam,
               sha256_uncompressed_cnf=hashlib.sha256(body.encode()).hexdigest())
    # independent re-solves: full budgets for the three instances re-solved in the paper (P = 12, 17 pipelined and
    # P = 20 common frame, primary encoding), reduced conflict budgets elsewhere (CPU budget); CaDiCaL always complete
    cited = meta.get("family") == "colour-symmetric" and (meta["P"], meta["common_frame"]) in ((12, False), (17, False), (20, True))
    log["resolve"] = resolve(clauses, nvars, (None, 5_000_000, 2_000_000) if cited else (None, 300_000, 200_000))
    if nfam is not None:
        with Glucose4(bootstrap_with=clauses[:nfam]) as s3:
            log["family_only"] = "SAT" if s3.solve() else "UNSAT"
    json.dump(log, open(d / f"{name}.log.json", "w"), indent=1)
    print(name, json.dumps({k: v for k, v in log.items() if k != "resolve"}), flush=True)


LAST = {}
NOTE_GSAT = ("variable id -> encoder object (repr). ('x', i, v): CNOT item i at time v (one-hot, v = 1..2P-2, or "
             "1..P-2 for the common frame); ('ge', i, k): t_i >= k; ('D', i, j, M): t_j - t_i >= M; ('s', unit, w): "
             "unit starts at w; ('rev', unit): the unit's order is reversed. items[i] = (check type, class, term "
             "label 0..5 = A1 A2 A3 B1 B2 B3).")
NOTE_TIMESAT = ("variable id -> encoder object (repr). Absolute CNOT times t_i in 0..2P-4. ('g', i, v): t_i >= v; "
                "('e', i, v): t_i = v; ('m', i, r): t_i = r mod P; ('le', a, b, M): one-way literal implying "
                "t_a - t_b <= M; ('fge', a, b, m): t_a - t_b >= m (reified); ('rev', unit): reversed order; "
                "('TRUE',): constant. items[i] = (check type, class, term label 0..5 = A1 A2 A3 B1 B2 B3).")


def enc_recorder(cls):
    class EncRec(cls):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            LAST["enc"] = self
    return EncRec


def varmap():
    e = LAST["enc"]
    F = getattr(e, "F", None)
    return {"note": NOTE_TIMESAT if hasattr(e, "TM") else NOTE_GSAT,
            "variables": {str(v): repr(o) for o, v in e.pool.obj2id.items()},
            "items": [repr(x) for x in getattr(F, "items", [])]}


job = sys.argv[1].split(":")
t0 = time.process_time()
if job[0] == "gsat":
    P, nowrap = int(job[1]), int(job[2])
    import search.experiments.e024b.gsat as G
    import search.experiments.e024b.common as GC
    G.Cadical153 = Recorder
    G.Enc = enc_recorder(G.Enc)
    G.OUT = SCRATCH
    GC.OUT = SCRATCH
    X = "A1A2A3B3B1B2,A1A2A3B1B2B3,A1A3A2B3B1B2"; Z = "A1A3A2B3B1B2,A1A2A3B1B2B3,A1A2A3B3B1B2"
    sys.argv = ["gsat", "--col", "3,1,1", "--x", X, "--z", Z, "--P", str(P), "--nowrap", str(nowrap),
                "--max_sec", "3600", "--tag", f"zen_P{P}_{nowrap}"]
    G.main()
    lg = json.load(open(SCRATCH / f"zen_P{P}_{nowrap}.json"))
    assert lg["status"] == "UNSAT" and lg["ncand"] == 0, lg["status"]
    R = RECS[-1]
    name = f"P{P:02d}_{'common_frame' if nowrap else 'pipelined'}"
    assert LAST["enc"].S is R
    write("min_period_primary_encoding", name, R.cl, R.nfam, varmap(),
          {"what": f"colour-symmetric family (Fig. 12 order class, colouring (a+b) mod 3), period {P}, "
                   f"{'common frame' if nowrap else 'pipelined'}; primary encoding; UNSAT",
           "family": "colour-symmetric", "P": P, "common_frame": bool(nowrap), "cegar_iterations": lg["iters"],
           "nogoods": lg["nogoods"], "cegar_status": lg["status"], "cpu_sec_generation": round(time.process_time() - t0, 1)})
elif job[0] == "timesat":
    P, sub = int(job[1]), job[2]
    extra = job[3] if len(job) > 3 else ""
    import search.experiments.e024a.cegar as CG
    CG.Cadical153 = Recorder
    CG.TimeSAT = enc_recorder(CG.TimeSAT)
    CG.OUT = SCRATCH
    tag = f"zen_P{P}_{sub.replace(',', '').replace(';', '_')}_{extra}"
    sys.argv = ["cegar", "--P", str(P), "--sub", sub, "--tighten", "0", "--max_sec", "5400", "--tag", tag]
    if extra:
        sys.argv += ["--maxwin", "14", "--winunits", {"w14X0": "X0", "w14Z2": "Z2"}[extra]]
    CG.main()
    lg = json.load(open(SCRATCH / f"{tag}.json"))
    assert lg["status"] == "UNSAT" and lg["candidates"] == 0, lg["status"]
    R = RECS[-1]
    H = lg["H"]
    if extra:
        sub_dir, name = "window_explanation", f"P{P:02d}_window14_{extra[3:]}"
        what = f"colour-symmetric pipelined, period {P}, CNOT window of class {extra[3:]} <= 14; second encoding; UNSAT"
    elif H == 24:
        sub_dir, name = "min_period_second_encoding", f"P{P:02d}_pipelined"
        what = f"colour-symmetric pipelined family, period {P}; second encoding (absolute times); UNSAT"
    else:
        sub_dir = "less_symmetry"
        name = f"P{P:02d}_subgroup_{sub.replace(',', '_').replace(';', '__')}"
        what = f"pipelined schedules invariant under the translation subgroup <{sub}> (order {H}), period {P}; UNSAT"
    assert LAST["enc"].S is R
    write(sub_dir, name, R.cl, R.nfam, varmap(),
          {"what": what, "P": P, "subgroup_generators": sub, "subgroup_order": H, "cegar_iterations": lg["iterations"],
           "cegar_status": lg["status"], "cpu_sec_generation": round(time.process_time() - t0, 1)})
elif job[0] == "uniq":
    src = open("research/audits/2026-10-11-E-024b-scripts/u1_dext.py").read()
    src = src.replace('"results/E-024b-audit/u1_dext.json"', repr(str(SCRATCH / "u1_dext.json")))
    path = SCRATCH / "u1_replay.py"
    path.write_text(src)
    sys.path.insert(0, "tests")
    import pysat.formula as PF
    POOLS = []

    class PoolRec(PF.IDPool):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            POOLS.append(self)
    PF.IDPool = PoolRec
    G = runpy.run_path(str(path), run_name="__main__")
    cols = {nm: colv for nm, colv, _ in G["colourings"]()}
    info = json.load(open(SCRATCH / "u1_dext.json"))
    assert info["all_unsat"] and info["all_witness_ok"] and info["all_blocked_fig12"]
    names = list(info["replay"])
    assert len(RECS) == len(names) == len(POOLS) == 48, (len(RECS), len(names), len(POOLS))
    LAB = ["A1", "A2", "A3", "B1", "B2", "B3"]
    for R, pool, nm in zip(RECS, POOLS, names):
        st = info["replay"][nm]
        colouring, kind = nm.rsplit("_", 1)
        mykeys = list(G["MYTYPES"][kind])
        vm = {}
        for o, v in pool.obj2id.items():
            if o[0] == "x":
                vm[str(v)] = {"colour": o[1], "type": o[2],
                              "type_representative_order": "".join(LAB[l] for l in G["MYTYPES"][kind][mykeys[o[2]]])}
            else:
                b = list(o[1])
                vm[str(v)] = {"column_present": {"H": [i for i in range(72) if b[i]],
                                                 "L": [i for i in range(len(b) - 72) if b[72 + i]]}}
        varmap_u = {"note": "x(colour, type): the checks of this colour use CNOT-order type 'type' (any order of the "
                            "type; a type is a class of orders with the same residual sets up to reversal, given by a "
                            "representative order of term labels for the "
                            + ("X" if kind == "X" else "Z") + " checks); column_present: the extended-code column with "
                            "these H/L rows (H = H" + ("Z" if kind == "X" else "X") + ", L = L" + ("Z" if kind == "X" else "X")
                            + " of data/code/gross_code.json) is present. Each nogood says: not all hook columns of a "
                            "verified weight <= 10 extended logical (or of one of its 72 translates) are present.",
                    "colour_of_check": cols[colouring], "variables": vm}
        write("order_class_uniqueness", f"{colouring.replace(';', '__').replace(',', '_')}_{kind}errors", R.cl, None,
              varmap_u, {"what": f"colouring {colouring} (translation-coset colouring), {kind}-type residuals: one CNOT-order "
                             f"type per colour, every assignment other than translates of Fig. 12 has a verified "
                             f"weight <= 10 extended logical; UNSAT",
                     "colouring": colouring, "residual_type": kind, "witness_records": st["records"],
                     "witnesses_verified": st["witness_ok"], "blocked_fig12_translates": st["blocked"]})
print("generation cpu", round(time.process_time() - t0, 1))
