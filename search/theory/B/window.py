"""Window lemma check: is the evaluator's finite-R memory circuit a window of the bulk (no clamping of step indices)?

For each check the evaluator's unroll() gives start[anc] (layer of instance-0 prep) and the CNOT offsets.  Readers'
instances t = 0..R-1 exist, the final data readout acts as instance R reading every qubit at the end.  The finite step
index of a deposit at time u on q for reader z is  min{t in 0..R-1 : read_t(q) > u}  else R;  the bulk one uses all
integers t.  The window property:
  (Wb)  every hypothetical reader instance -1 reads before any fault can happen:  start_z + off_z(q) - D <= 0;
  (Wt)  every hypothetical reader instance R reads after the end:  start_z + off_z(q) + D R > last layer,
and then the finite step index equals the bulk one for every deposit of every existing writer instance and every data
fault, so a finite-R undetected fault set is a bulk undetected fault set with the same columns.  We check (Wb), (Wt)
(R-independent) and, as a direct test, equality of the two indices for R = 1..Rmax.

  uv run python -m search.theory.B.window --code gross --spec search/experiments/e032/u11_spec.json
"""
from __future__ import annotations

import argparse
import json
import sys

from search.theory.B.bulk import ROOT, code_mats, load_spec

for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)


def get_code(name):
    if name.startswith("kunlun-"):
        from search.experiments.e036.common import code
        return code(name.split("-", 1)[1])
    from evaluators.tasks import build_code, get_task
    task = {"gross": "gross-dcirc", "bb90": "bb90-dcirc", "bb108": "bb108-dcirc", "bb72": "bb72-dcirc"}[name]
    return build_code(get_task(task), None)[0]


def check(code_name, spec_d, Rmax=3):
    from evaluators import candidate as cand
    code = get_code(code_name)
    spec = cand.parse_schedule(spec_d)
    out = {}
    for R in range(1, Rmax + 1):
        U = cand.unroll(spec, code, R)
        lay = cand.layout_for(code)
        D = spec.period
        last = U.num_layers - 1
        for basis in ("Z", "X"):
            W, Rd = ((spec.x_checks, lay.x_anc), (spec.z_checks, lay.z_anc)) if basis == "Z" else \
                ((spec.z_checks, lay.z_anc), (spec.x_checks, lay.x_anc))
            reads = {}      # q -> list of (z, start + off)
            for z, (c, a) in enumerate(zip(*Rd)):
                dm, offs = c.offsets(D)
                for o, col in offs:
                    reads.setdefault(col, []).append((z, U.start[a] + o))
            wb = all(r - D <= 0 for lst in reads.values() for _, r in lst)
            wt = all(r + D * R > last for lst in reads.values() for _, r in lst)
            bad = 0

            def sig_fin(r, u):
                for t in range(R):
                    if r + D * t > u:
                        return t
                return R

            def sig_bulk(r, u):
                import math
                return math.floor((u - r) / D) + 1
            # writer deposits
            for c, a in zip(*W):
                dm, offs = c.offsets(D)
                for j in range(R):
                    for o, col in offs:
                        u = U.start[a] + o + D * j
                        for z, r in reads[col]:
                            if sig_fin(r, u) != sig_bulk(r, u):
                                bad += 1
            # data faults at half-integer times in (0, last+1)
            for q, lst in reads.items():
                for u2 in range(1, 2 * (last + 1), 2):
                    u = u2 / 2
                    for z, r in lst:
                        if sig_fin(r, u) != sig_bulk(r, u):
                            bad += 1
            out[(R, basis)] = {"Wb": wb, "Wt": wt, "mismatch": bad}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--Rmax", type=int, default=3)
    a = ap.parse_args()
    res = check(a.code, load_spec(a.spec), a.Rmax)
    print(json.dumps({"spec": a.spec, **{f"R{k[0]}{k[1]}": v for k, v in res.items()}}))


if __name__ == "__main__":
    main()
