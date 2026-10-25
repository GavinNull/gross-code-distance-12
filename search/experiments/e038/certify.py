"""E-038: certify d_circ of a found schedule, three ways, both bases.
  (1) evaluator template: candidate.parse/validate_schedule, memory_circuit + noise sd6 (p = 1e-3), exact MITM
      min weight <= 3 (e036_audit.core.min_weight_le) for R = 1..Rmax; weight-4 witness (e036.common.min_weight, w = 4)
      for R = 1, 2 as the upper bound;
  (2) own periodic stim circuit (model.stim_circuit), R = 1..Rmax;
  (3) for non-wrapping schedules: the auditor's independent code (e036_audit.core: symbolic Sym and its own stim
      circuit with both detector types), reset and no-reset ancillas, R = 1..Rmax.
Any R (non-wrapping): a weight-w undetectable logical has faults in <= w rounds and fault-free rounds can be deleted
(E-036 audit, Sec. "任意 R"), so R = 1..3 decide weight <= 3 for all R; a fault-free round can be prepended, so an
R = 1 weight-4 witness bounds every R.
usage: uv run python -m search.experiments.e038.certify search/experiments/e038/n8_found.json --Rmax 6
"""
import argparse
import json
import time

from search.experiments.e036_audit import core as A
from search.experiments.e038.model import Sched, bulk_min, legal, stim_circuit, stim_mechs
from search.experiments.e038.validate_model import evaluator_check


def main(path, Rmax, out):
    s = Sched.from_json(json.load(open(path)))
    res = {"path": path, "P": s.P, "legal": legal(s)[0], "bulk_W12": bulk_min(s, 3, W=12)[0], "rows": []}
    nonwrap = all(s.pi[k] == 0 and s.mu[k] == s.P - 1 for k in s.ks)
    res["nonwrap"] = nonwrap
    from evaluators import candidate as cand
    from search.experiments.e036.common import code, min_weight
    spec = cand.parse_schedule(s.spec())
    res["validate_problems"] = cand.validate_schedule(spec, code(s.variant))
    edges = set()
    for k in s.ks:
        for q in A.support(k):
            edges.add((k, q))
    res["n_couplers_used"] = len(edges)
    for R in range(1, Rmax + 1):
        for b in ("Z", "X"):
            t0 = time.time()
            row = {"R": R, "basis": b}
            _, ec = evaluator_check(s, b, R)
            em = stim_mechs(ec)
            row["eval"] = A.min_weight_le(em, 3)[0]
            if R <= 2:
                w4, wit = min_weight([(d, o) for d, o in em], 4)
                row["eval_w4_upper"] = w4
            row["own"] = A.min_weight_le(stim_mechs(stim_circuit(s, b, R)[0]), 3)[0]
            if nonwrap:
                S = s.P - 2
                T = {k: [s.tau[(k, a)] for a in range(6)] for k in s.ks}
                row["audit_legal"] = A.legal(T, s.variant, S)[0]
                for reset in (True, False):
                    row[f"audit_sym_reset{int(reset)}"] = A.min_weight_le(A.Sym(s.variant, b, T, R, reset=reset).mechs(), 3)[0]
                    row[f"audit_stim_reset{int(reset)}"] = A.min_weight_le(
                        A.stim_mechs(A.stim_circuit(T, S, s.variant, b, R, reset=reset)), 3)[0]
            row["sec"] = round(time.time() - t0, 1)
            res["rows"].append(row)
            print(json.dumps(row), flush=True)
    bad = [r for r in res["rows"] if any(v is not None for k, v in r.items() if k not in ("R", "basis", "sec", "eval_w4_upper", "audit_legal"))]
    res["any_weight_le3"] = len(bad)
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}))
    with open(out, "a") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--Rmax", type=int, default=6)
    ap.add_argument("--out", default="results/E-038-bb18-d4/certify.jsonl")
    a = ap.parse_args()
    main(a.path, a.Rmax, a.out)
