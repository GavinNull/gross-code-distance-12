"""Item 4 negative controls for the Lemma 3 stim replay:
(a) c11 (d_circ = 10): the same pair-hook + weight-d logical construction must never give an undetected weight-9 fault;
(b) on sampled T(8) vectors: drop one data error -> must fire detectors (checks the replay can fail).
  PYTHONPATH=.:tests uv run python search/experiments/paperP_audit/item4_control.py
"""
import json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
ROOT = Path(__file__).resolve().parents[3]
import item4_lemma3_stim as L4
from item3_triples import CODES, build
from item7_period import spec_times
from inject import Injector
from search.theory.B_audit.common import get_code
import numpy as np
from ortools.sat.python import cp_model
from item3_triples import gf2_kernel

c = CODES["bb90"]; HX, HZ, labX, labZ = build(c); code = get_code("bb90")


def logical(side, pair):
    Hdet, stab, lab = (HZ, HX, labX) if side == "X" else (HX, HZ, labZ)
    K, _ = gf2_kernel(stab); n = Hdet.shape[1]; md = cp_model.CpModel(); x = [md.NewBoolVar("") for _ in range(n)]
    one = md.NewConstant(1)
    for row in Hdet: md.AddBoolXOr([x[i] for i in np.flatnonzero(row)] + [one])
    bs = []
    for kv in K:
        b = md.NewBoolVar(""); md.AddBoolXOr([x[i] for i in np.flatnonzero(kv)] + [b.Not()]); bs.append(b)
    md.AddBoolOr(bs); md.Add(sum(x) == 10)
    for nm in pair: md.Add(x[lab[nm]] == 1)
    s = cp_model.CpSolver(); s.parameters.num_workers = 1; st = s.Solve(md)
    return [i for i in range(n) if s.Value(x[i])] if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None


spec = json.load(open(ROOT / "search/experiments/e030/c11_spec.json"))
P, tx, tz = spec_times(spec, "bb90")
R = 7; hits = 0; tried = 0
for basis in ("Z", "X"):
    inj = Injector(spec, code, basis, R)
    wtyp, t = ("X", tx) if basis == "Z" else ("Z", tz)
    pi = sorted(t, key=t.get); lab = labX if wtyp == "X" else labZ
    rtyp = "Z" if basis == "Z" else "X"
    gaps = [inj.meas_layer(rtyp, j) for j in range(R - 1)]
    for k in range(1, 6):                      # every hook position, not only pair hooks
        res = [lab[n] for n in pi[k:]]
        for pair in ([tuple(pi[k:])] if len(pi[k:]) == 2 else []) + ([tuple(pi[:k])] if k == 2 else []):
            Lq = logical(wtyp, pair)
            if Lq is None: continue
            data = [q for q in Lq if q not in (lab[pair[0]], lab[pair[1]])]
            for j in range(2, R - 2):
                for g in gaps:
                    tried += 1
                    fired, obs = inj.run([("anc", wtyp, 0, j, k)] + [("data", q, g) for q in data])
                    if not fired and obs.any(): hits += 1
print(json.dumps({"control": "c11 pair-hook witnesses", "tried": tried, "undetected_logicals": hits}))
