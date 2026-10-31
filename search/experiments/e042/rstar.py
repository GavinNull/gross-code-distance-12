"""E-042: the single round count R* at which a finite lift certificate implies "no bulk lift" (Theorem 4 hypothesis).

Bulk compression lemma (proof in the journal, Sec. 2).  Assume the window conditions (Wb)(Wt).  Let F be a bulk
undetected fault set with at most 11 faults (an extended logical of weight 10 plus at most one readout flip, or one
of weight 11).  Pair equal step indices at every reader; the faults joined by pairs form components, each component
is itself undetected and can be shifted by whole periods independently; the union of the index intervals of a
component has length <= sum over its faults of (max index - min index).  Hence F can be moved so that every index
lies in [1, 1 + S] with S <= sum of per-fault spreads, and then (existence conditions below) every fault exists in
the R-round circuit for R >= S + 2, with finite indices equal to bulk indices (window lemma).  So a bulk lift exists
iff a lift exists at R* = S_max + 2.

This script computes, from the evaluator's unroll (the same start times the finite circuit uses):
  * per-fault index spreads (max - min of the reduced (reader, index) items) of every data error (all half-integer
    times of one period; spreads are P-periodic), every hook (writer, suffix start k = 2..6 and the k = 1 full
    residual, instance 0) and the readout flip (spread 1);
  * existence conditions: a hook of writer instance j whose items all lie in [1, R-1] has 0 <= j <= R-1
    (<=> min item of instance 0 <= 1 and max item of instance 0 >= 0); a data error whose items lie in [1, R-1] lies
    at a time in (0, last] (<=> every instance-0 read time >= 0; the upper side holds because instance R-1 exists);
  * (Wb), (Wt) and finite == bulk index for every deposit, R = 1..4 and R*.

    uv run python -m search.experiments.e042.rstar [SPEC] > results/E-042-g10-cert/rstar.json
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

SPEC = "search/experiments/e040/g10_d12_spec.json"


def timing(spec, code, R, basis):
    from evaluators import candidate as cand
    lay = cand.layout_for(code)
    U = cand.unroll(spec, code, R)
    D = spec.period
    W, Rd = ((spec.x_checks, lay.x_anc), (spec.z_checks, lay.z_anc)) if basis == "Z" else \
        ((spec.z_checks, lay.z_anc), (spec.x_checks, lay.x_anc))
    reads = {}                         # q -> [(reader index z, instance-0 read time)]
    for z, (c, a) in enumerate(zip(*Rd)):
        _, offs = c.offsets(D)
        for o, col in offs:
            reads.setdefault(col, []).append((z, U.start[a] + o))
    writes = []                        # writer -> [(instance-0 CNOT time, q)] in time order
    for c, a in zip(*W):
        _, offs = c.offsets(D)
        writes.append(sorted((U.start[a] + o, col) for o, col in offs))
    return D, U.num_layers - 1, reads, writes


def blk(r, u, D):
    return math.floor((u - r) / D) + 1


def reduce(items):
    c = Counter(items)
    return sorted(it for it, m in c.items() if m % 2)


def analyse(spec_path=SPEC, Rcheck=(1, 2, 3, 4)):
    from evaluators import candidate as cand
    from search.theory.B_audit.common import get_code
    code = get_code("gross")
    spec = cand.parse_schedule(json.loads((ROOT / spec_path).read_text()))
    assert not cand.validate_schedule(spec, code)
    out = {"spec": spec_path}
    smax = 0
    for basis in ("Z", "X"):
        D, last, reads, writes = timing(spec, code, 3, basis)
        # data errors: spread over one period of half-integer times (P-periodic)
        sd = Counter()
        for q, l in reads.items():
            for u2 in range(1, 2 * D + 1, 2):
                u = 100 * D + u2 / 2
                its = [blk(r, u, D) for _, r in l]
                sd[max(its) - min(its)] += 1
        # hooks: suffix k..6 (k = 1 is the full residual, zero signature by Lemma 2, included anyway)
        sh, exist_bad, empty = Counter(), 0, 0
        for w in writes:
            for k in range(1, 7):
                its = []
                for t, q in w[k - 1:]:
                    its += [(z, blk(r, t, D)) for z, r in reads[q]]
                red = reduce(its)
                if not red:
                    empty += 1
                    continue
                vals = [v for _, v in red]
                sh[max(vals) - min(vals)] += 1
                if k >= 2 and not (min(vals) <= 1 and max(vals) >= 0):
                    exist_bad += 1
        rho_min = min(r for l in reads.values() for _, r in l)
        s_b = max(max(sd), max(sh), 1)
        smax = max(smax, s_b)
        out[basis] = {"data_spread_hist": dict(sd), "hook_spread_hist": dict(sh), "hooks_with_empty_items": empty,
                      "hook_existence_violations": exist_bad, "min_instance0_read_time": rho_min, "s_max": s_b}
    S10 = 10 * smax + 1          # weight-10 item + one flip
    S11 = 11 * smax              # weight-11 item
    Rstar = max(S10, S11) + 2
    out.update(S_w10_flip=S10, S_w11=S11, R_star=Rstar)
    # window conditions and finite == bulk for every deposit
    win = {}
    for R in sorted(set(Rcheck) | {Rstar}):
        for basis in ("Z", "X"):
            D, last, reads, writes = timing(spec, code, R, basis)
            rr = [r for l in reads.values() for _, r in l]
            wb = all(r - D <= 0 for r in rr)
            wt = all(r + D * R > last for r in rr)
            fin = lambda r, u: sum(1 for t in range(R) if r + D * t < u)
            bad = 0
            for w in writes:
                for j in range(R):
                    for t, q in w:
                        bad += sum(fin(r, t + D * j) != blk(r, t + D * j, D) for _, r in reads[q])
            for q, l in reads.items():
                for u2 in range(1, 2 * (last + 1) + 1, 2):
                    bad += sum(fin(r, u2 / 2) != blk(r, u2 / 2, D) for _, r in l)
            # instance R-1 of every reader reads at or before the last layer (upper existence side)
            top = all(r + D * (R - 1) <= last for r in rr)
            win[f"R{R}{basis}"] = {"Wb": wb, "Wt": wt, "index_mismatches": bad, "inst_R-1_inside": top}
    out["window"] = win
    out["ok"] = all(v["Wb"] and v["Wt"] and v["index_mismatches"] == 0 and v["inst_R-1_inside"] for v in win.values()) \
        and all(out[b]["hook_existence_violations"] == 0 and out[b]["min_instance0_read_time"] >= 0 for b in "ZX")
    return out


if __name__ == "__main__":
    print(json.dumps(analyse(*(sys.argv[1:2] or [SPEC])), indent=1))
