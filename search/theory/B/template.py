"""Translation-invariant BB schedule from a term template (one X timing, one Z timing for all checks).

Labels A1 A2 A3 B1 B2 B3 = the task's A and B term lists in order.  X check i=(a,b) acts on left (a,b)+A_p, right
(a,b)+B_p; Z check on right (a,b)-A_p, left (a,b)-B_p (evaluator bb_matrices convention).

Templates (exactly the per-term timings of the two certified period-11 circuits, Table I of the draft):
  u11 : X prep 0 meas 10, A2@1 A1@2 A3@3 B3@4 B2@5 B1@9;   Z prep 10 meas 9, B1@0 B2@4 B3@5 A3@6 A1@7 A2@8
  c11 : X prep 0 meas 10, B1@1 B3@2 B2@3 A3@4 A1@5 A2@9;   Z prep 10 meas 9, A2@0 A1@4 A3@5 B2@6 B3@7 B1@8
A template's legality and its delta (by term pair) do not depend on the code: on a left qubit the three X CNOTs are
at the A-term steps and the three Z CNOTs at the B-term steps, on a right qubit the other way round.

  uv run python -m search.theory.B.template --code bb72 --template u11 --out results/theoryB/bb72_u11_spec.json
"""
from __future__ import annotations

import argparse
import json
import sys

from search.theory.B.bulk import ROOT

for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

LAB = ["A1", "A2", "A3", "B1", "B2", "B3"]
TEMPLATES = {
    "u11": dict(P=11, X=(0, 10, {"A2": 1, "A1": 2, "A3": 3, "B3": 4, "B2": 5, "B1": 9}),
                Z=(10, 9, {"B1": 0, "B2": 4, "B3": 5, "A3": 6, "A1": 7, "A2": 8})),
    "c11": dict(P=11, X=(0, 10, {"B1": 1, "B3": 2, "B2": 3, "A3": 4, "A1": 5, "A2": 9}),
                Z=(10, 9, {"A2": 0, "A1": 4, "A3": 5, "B2": 6, "B3": 7, "B1": 8})),
}
TASKS = {"bb72": "bb72-dcirc", "bb90": "bb90-dcirc", "bb108": "bb108-dcirc", "gross": "gross-dcirc",
         "bb120": "bb120-dcirc"}


def code_params(name):
    from evaluators.tasks import get_task, _mono_exponents
    fx = get_task(TASKS[name]).code_family["fixed"]
    l, m = fx["l"], fx["m"]
    A = [_mono_exponents(t, l, m) for t in fx["A"]]
    B = [_mono_exponents(t, l, m) for t in fx["B"]]
    return l, m, A, B


def make(name, tpl, relabel=None):
    """relabel: optional dict template-label -> code-label (to move the template onto other terms)."""
    l, m, A, B = code_params(name)
    N2 = l * m
    idx = lambda a, b: (a % l) * m + (b % m)
    T = TEMPLATES[tpl] if isinstance(tpl, str) else tpl
    rl = relabel or {x: x for x in LAB}
    xs, zs = [], []
    for i in range(N2):
        a, b = divmod(i, m)
        colX, colZ = {}, {}
        for p in range(3):
            colX[f"A{p+1}"] = idx(a + A[p][0], b + A[p][1])
            colX[f"B{p+1}"] = N2 + idx(a + B[p][0], b + B[p][1])
            colZ[f"A{p+1}"] = N2 + idx(a - A[p][0], b - A[p][1])
            colZ[f"B{p+1}"] = idx(a - B[p][0], b - B[p][1])
        px, mx, tx = T["X"]
        pz, mz, tz = T["Z"]
        xs.append({"prep": px, "meas": mx, "cnots": sorted([colX[rl[k]], s] for k, s in tx.items())})
        zs.append({"prep": pz, "meas": mz, "cnots": sorted([colZ[rl[k]], s] for k, s in tz.items())})
    return {"format": "qec-schedule/v1", "period": T["P"], "x_checks": xs, "z_checks": zs,
            "name": f"theoryB template {tpl} on {name} relabel={relabel}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--relabel", default="", help="e.g. A1=A2,A2=A1 (template label = code label)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rl = None
    if a.relabel:
        rl = {x: x for x in LAB}
        for kv in a.relabel.split(","):
            k, v = kv.split("=")
            rl[k] = v
    spec = make(a.code, a.template, rl)
    from evaluators import candidate as cand
    from evaluators.tasks import build_code, get_task
    code = build_code(get_task(TASKS[a.code]), None)[0]
    probs = cand.validate_schedule(cand.parse_schedule(spec), code)
    (ROOT / a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(spec, open(ROOT / a.out, "w"))
    print(json.dumps({"out": a.out, "validate_problems": probs}))


if __name__ == "__main__":
    main()
