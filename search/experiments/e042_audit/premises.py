"""E-042 audit, item 1: premises of the bulk compression lemma, computed from the stim circuit (own parser).

For circuit CNAME and both bases:
  * per-fault bulk index spans (data errors over one period, hooks k = 1..6, flips), zero-image hooks, empty hooks;
  * s = max span, m = max #faults (given), R* = s*m + 2;
  * existence, done directly (no E1/E2 reasoning): every bulk single fault (data error at any half-integer time in
    a wide range, hook of any writer instance j in [-5, R*+5], flip) whose bulk items all lie in [1, R*-1] exists in
    the R*-round circuit with finite items == bulk items, and its (detectors, L) signature is a term of the SD6 DEM;
  * window: finite index == bulk index for every deposit of every existing fault, R = 1..RMAX;
  * own model == DEM signature sets at R*; DEM per-term index-span histogram at R* (all terms / interior terms).

    uv run python -m search.experiments.e042_audit.premises g10 11 [RMAX]
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter

from search.experiments.e042_audit.model import ROOT, Model, dem_sigs, red

OUT = ROOT / "results/E-042-audit"


def spans(M):
    P = M.P
    j0 = M.R // 2
    sd = Counter()
    for q in range(M.n):
        for u2 in range(1, 2 * P + 1, 2):
            u = j0 * P + u2 / 2 + 0.0
            b = M.bulk(q, u)
            f = M.fin(q, u)
            assert b == f, "middle data error: finite != bulk"
            v = [x for _, x in b]
            sd[max(v) - min(v)] += 1
    sh, empty, zero_img, e1_bad = Counter(), Counter(), 0, 0
    z0 = M.image([])
    for c, insts in enumerate(M.writers):
        cx0 = insts[0]
        cxj = insts[j0]
        assert all(t1 - t0 == j0 * P for (t0, _), (t1, _) in zip(cx0, cxj))
        for k in range(1, 7):
            suf = cx0[k - 1:]
            its = []
            for tt, q in suf:
                its += M.bulk(q, tt)
            r = red(its)
            if k >= 2 and M.image([q for _, q in suf]) == z0:
                zero_img += 1
            if not r:
                empty[k] += 1
                continue
            v = [x for _, x in r]
            sh[(k, max(v) - min(v))] += 1
            if k >= 2 and not (min(v) <= 1 and max(v) >= 0):
                e1_bad += 1
    return sd, sh, empty, zero_img, e1_bad


def existence(Mr, D):
    """Mr: model at R*.  every bulk fault with items in [1, R*-1] exists, finite == bulk, signature in DEM D."""
    R, P = Mr.R, Mr.P
    lo, hi = 1, R - 1
    ok = lambda its: all(lo <= x <= hi for _, x in its)
    cnt = Counter()
    bad = []
    finsig = {}
    for kind, ident, its, res in Mr.finite_faults():
        finsig.setdefault((kind, ident), (its, res))
    for q in range(Mr.n):
        for u2 in range(-10 * P, 2 * (R + 5) * P):
            u = u2 / 2 if u2 % 2 else None
            if u is None:
                continue
            b = red(Mr.bulk(q, u))
            if not b or not ok(b):
                continue
            cnt["data"] += 1
            if not (0 < u < Mr.last + 1):
                bad.append(("data_outside", q, u)); continue
            f = red(Mr.fin(q, u))
            if f != b:
                bad.append(("data_index", q, u)); continue
            if (b, Mr.lobs([q])) not in D:
                bad.append(("data_notin_dem", q, u))
    for c, insts in enumerate(Mr.writers):
        cx0 = insts[0]
        for j in range(-5, R + 6):
            for k in range(2, 7):
                suf = [(t + j * P, q) for t, q in cx0[k - 1:]]
                its = []
                for tt, q in suf:
                    its += Mr.bulk(q, tt)
                b = red(its)
                if not b or not ok(b):
                    continue
                cnt["hook"] += 1
                if not (0 <= j < R):
                    bad.append(("hook_instance_outside", c, j, k)); continue
                assert [x for x, _ in suf] == [x for x, _ in insts[j][k - 1:]]
                f, resq = finsig[("h", (c, j, k))]
                if f != b:
                    bad.append(("hook_index", c, j, k)); continue
                if (b, Mr.lobs(resq)) not in D:
                    bad.append(("hook_notin_dem", c, j, k))
    for r in range(Mr.nreaders):
        for t in range(-5, R + 5):
            if lo <= t and t + 1 <= hi:
                cnt["flip"] += 1
                if not (0 <= t < R):
                    bad.append(("flip_outside", r, t))
    return dict(cnt), bad


def window(cname, basis, Rs):
    out = {}
    for R in Rs:
        M = Model(cname, R, basis)
        mism = 0
        for q in range(M.n):
            for u2 in range(1, 2 * (M.last + 1) + 1, 2):
                mism += M.fin(q, u2 / 2) != M.bulk(q, u2 / 2)
        for insts in M.writers:
            for cx in insts:
                for tt, q in cx:
                    mism += M.fin(q, tt) != M.bulk(q, tt)
        out[R] = mism
    return out


def main():
    cname, m = sys.argv[1], int(sys.argv[2])
    rmax = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    res = {"circuit": cname, "m": m}
    for basis in ("Z", "X"):
        Mb = Model(cname, 12, basis)
        sd, sh, empty, zi, e1 = spans(Mb)
        s = max([max(sd), max(v for _, v in sh), 1])
        Rstar = s * m + 2
        Mr = Model(cname, Rstar, basis)
        D = dem_sigs(Mr.circ)
        model = {(its, Mr.lobs(res_)) for _, _, its, res_ in Mr.finite_faults()}
        model.discard((frozenset(), frozenset()))
        cnt, bad = existence(Mr, D)
        # DEM term spans
        dsp, dsp_int = Counter(), Counter()
        for dets, _ in D:
            if not dets:
                continue
            v = [x for _, x in dets]
            dsp[max(v) - min(v)] += 1
            if min(v) >= 1 and max(v) <= Rstar - 1:
                dsp_int[max(v) - min(v)] += 1
        win = window(cname, basis, range(1, rmax + 1))
        res[basis] = {"P": Mb.P, "data_span_hist": dict(sd), "hook_span_hist": {f"k{k}_s{v}": c for (k, v), c in sorted(sh.items())},
                      "empty_hooks_by_k": dict(empty), "zero_image_hooks_k2to6": zi, "E1_violations": e1, "s": s,
                      "R_star": Rstar, "model_eq_dem_at_Rstar": model == D, "model": len(model), "dem": len(D),
                      "existence_counts": cnt, "existence_failures": len(bad), "existence_fail_examples": bad[:5],
                      "dem_span_hist_all": dict(dsp), "dem_span_hist_interior": dict(dsp_int),
                      "window_mismatches_R1toRmax": win}
        print(json.dumps({basis: res[basis]}), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "premises.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
