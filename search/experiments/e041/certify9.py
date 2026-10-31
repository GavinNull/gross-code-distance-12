"""E-041 certification of a period-9 W9 schedule (spec json in e038 Sched format).

(1) legality: e039 legal2 (W, P = 9), evaluator validate_schedule (public entry), coupler set == Kunlun's 84 edges
    (e036_audit.core.kunlun_schedule).
(2) bulk: e038.model.bulk_min (W = 12, both bases) = None, i.e. no bulk undetectable logical of weight <= 3.
(3) window conditions (Wb), (Wt) of theory B lemma 4 on the evaluator unrolling (search/theory/B/window.py) and the
    direct finite-vs-bulk step-index comparison for R = 1..4 -> for the evaluator's (reset) circuit, every finite-R
    undetectable fault set is a bulk one, so d_circ >= 4 for EVERY R (theory B, audited).
(4) independent finite-R exact search, reset AND no-reset ancillas, R = 1..Rmax: my own period-9 circuit (circuit9, fcore
    conventions: own SD6, detectors of the 14 measured checks, own logical basis), and the E-039 auditor's independent
    non-wrapping core fcore (period 10, N8 template, same CNOT layers) -- the period-10 circuit is the period-9 one with
    the CNOT-free layer re-inserted; we check that both give IDENTICAL DEM mechanism sets (detector, observable masks).
    For the non-wrapping period-10 circuit the E-036/E-038 audited "fault-free rounds can be deleted" argument makes
    R = 1..3 decide weight <= 3 for all R (reset and no-reset).
(5) upper bound: a weight-4 data logical injected right after the data reset fires no detector and flips an observable.
usage: uv run python -m search.experiments.e041.certify9 search/experiments/e041/w9_found.json --Rmax 6"""
import argparse
import json
import time

import numpy as np
import stim

from search.experiments.e036_audit import core as A
from search.experiments.e038.model import Sched, bulk_min
from search.experiments.e039.legal2 import legal_any
from search.experiments.e039_audit import fcore as F

ND = 18


def circuit9(s, basis, R, p=0.0, reset=True, inject=()):
    """own SD6 circuit of a periodic schedule s (P, pi, mu, tau absolute for round 0, pi >= 0); fcore conventions."""
    P = s.P
    KS = F.KS
    anc = {k: ND + i for i, k in enumerate(KS)}
    nq = ND + len(KS)
    ev = {}
    for k in KS:
        for j in range(R):
            if reset or j == 0:
                ev.setdefault(s.pi[k] + j * P + 1, []).append(("R", k, j))
            for a in range(6):
                ev.setdefault(s.tau[(k, a)] + j * P + 1, []).append(("C", k, a))
            ev.setdefault(s.mu[k] + j * P + 1, []).append(("M", k, j))
    last = max(ev) + 1        # final readout layer; layer 0 = data reset
    inj = {}
    for (layer, when, q, pa) in inject:
        inj.setdefault((layer, when), []).append((q, pa))
    c = stim.Circuit()
    rec, nm = {}, 0

    def do_inj(layer, when):
        for q, pa in inj.get((layer, when), []):
            c.append("X_ERROR" if pa == "X" else "Z_ERROR", [q], 1.0)
    for t in range(last + 1):
        do_inj(t, "pre")
        used = set()
        if t == last:
            c.append("M" if basis == "Z" else "MX", list(range(ND)), p)
            for q in range(ND):
                rec[("D", q)] = nm
                nm += 1
            do_inj(t, "post")
            break
        if t == 0:
            c.append("R" if basis == "Z" else "RX", list(range(ND)))
            if p:
                c.append("X_ERROR" if basis == "Z" else "Z_ERROR", list(range(ND)), p)
            used |= set(range(ND))
        ops = ev.get(t, [])
        ms = [(k, j) for o, k, j in ops if o == "M"]
        for typ in "XZ":   # measurements before resets in a layer (an ancilla never has both: W class)
            ks = [(k, j) for k, j in ms if k[0] == typ]
            if ks:
                c.append("MX" if typ == "X" else "M", [anc[k] for k, _ in ks], p)
                for kj in ks:
                    rec[kj] = nm
                    nm += 1
                for k, _ in ks:
                    assert anc[k] not in used
                    used.add(anc[k])
        for typ in "XZ":
            qs = [anc[k] for o, k, _ in ops if o == "R" and k[0] == typ]
            if qs:
                assert not (set(qs) & used)
                c.append("RX" if typ == "X" else "R", qs)
                if p:
                    c.append("Z_ERROR" if typ == "X" else "X_ERROR", qs, p)
                used |= set(qs)
        pairs = []
        for o, k, a in ops:
            if o == "C":
                q = F.SUPP[k][a]
                assert q not in used and anc[k] not in used, ("clash", t, k, a)
                pairs += [anc[k], q] if k[0] == "X" else [q, anc[k]]
                used |= {q, anc[k]}
        if pairs:
            c.append("CX", pairs)
            if p:
                c.append("DEPOLARIZE2", pairs, p)
        if p:
            idle = [q for q in range(nq) if q not in used]
            if idle:
                c.append("DEPOLARIZE1", idle, p)
        do_inj(t, "post")
        c.append("TICK")
    readers = [k for k in KS if k[0] == basis]

    def m(key):
        return stim.target_rec(rec[key] - nm)
    for j in range(R):
        for k in readers:
            tg = [m((k, j))]
            if reset and j >= 1:
                tg.append(m((k, j - 1)))
            if not reset and j >= 2:
                tg.append(m((k, j - 2)))
            c.append("DETECTOR", tg)
    for k in readers:
        tg = [m(("D", q)) for q in F.SUPP[k]] + [m((k, R - 1))]
        if not reset and R >= 2:
            tg.append(m((k, R - 2)))
        c.append("DETECTOR", tg)
    for i, v in enumerate(F.logicals(basis)):
        c.append("OBSERVABLE_INCLUDE", [m(("D", q)) for q in np.nonzero(v)[0]], i)
    return c


def weight4_logical(basis):
    from search.experiments.e039.static import valid_table
    V = valid_table("bb18", basis)
    for m in range(1 << 18):
        if bin(m).count("1") == 4 and V[m]:
            return [q for q in range(18) if m >> q & 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--Rmax", type=int, default=6)
    ap.add_argument("--out", default="results/E-041-bb18-p9/certify9.jsonl")
    a = ap.parse_args()
    s = Sched.from_json(json.load(open(a.path)))
    assert s.P == 9
    res = {"path": a.path}
    res["legal_W9"] = legal_any(s, False)[0]
    from evaluators import candidate as cand
    from search.experiments.e036.common import code
    res["validate_problems"] = cand.validate_schedule(cand.parse_schedule(s.spec()), code("bb18"))
    edges = {(k, A.support(k)[a_]) for k in s.ks for a_ in range(6)}
    T, _ = A.kunlun_schedule("bb18")
    kedges = {(k, A.support(k)[a_]) for k in T for a_ in range(6) if T[k][a_] is not None}
    res["couplers"] = len(edges)
    res["couplers_equal_kunlun"] = edges == kedges
    res["max_window"] = max(s.mu[k] - s.pi[k] for k in s.ks)
    res["bulk_W12"] = bulk_min(s, 3, W=12)[0]
    from search.theory.B.window import check as wcheck
    win = wcheck("kunlun-bb18", s.spec(), 4)
    res["window"] = {f"R{k[0]}{k[1]}": v for k, v in win.items()}
    print(json.dumps(res), flush=True)
    # period-10 non-wrapping image (same CNOT layers; requires all tau in 1..8)
    taus = {e: s.tau[e] for e in s.tau}
    assert min(taus.values()) >= 1 and max(taus.values()) <= 8
    res["fcore_legal_N8"] = bool(F.legal(taus, 8))
    rows = []
    for R in range(1, a.Rmax + 1):
        for b in ("Z", "X"):
            for reset in (True, False):
                t0 = time.time()
                m9 = F.dem_mechs(circuit9(s, b, R, p=1e-3, reset=reset))
                c10, _ = F.circuit(taus, 8, b, R, p=1e-3, reset=reset)
                m10 = F.dem_mechs(c10)
                row = {"R": R, "basis": b, "reset": reset, "own9": F.min_weight3(m9), "fcore10": F.min_weight3(m10),
                       "same_mechs": set(m9) == set(m10), "n9": len(m9), "n10": len(m10)}
                if R <= 3:
                    L = weight4_logical(b)
                    cinj = circuit9(s, b, R, p=0.0, reset=reset,
                                    inject=[(0, "post", q, "X" if b == "Z" else "Z") for q in L])
                    row["w4_inject"] = F.fires(cinj)
                row["sec"] = round(time.time() - t0, 1)
                rows.append(row)
                print(json.dumps(row), flush=True)
    res["rows"] = rows
    res["any_le3"] = sum(1 for r in rows if r["own9"] is not None or r["fcore10"] is not None)
    res["all_same_mechs"] = all(r["same_mechs"] for r in rows)
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}), flush=True)
    with open(a.out, "a") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
