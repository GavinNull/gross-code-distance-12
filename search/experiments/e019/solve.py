"""E-019 stage 4: exact single-round circuit distance of one family member / basis, plus injected witnesses.

usage: uv run python -m search.experiments.e019.solve <key> <basis> [--timeout_pos S]
Needs inst/inst_<key>_<basis>_T4_r1.{txt,pkl} (instance.py) and ec/dist_<key>.json (endcycle.py).

1. exhaustive adfs at W = d_end - 1 (all orbit cases). If a solution exists, descend: exhaustive at (found weight - 1)
   until none -> exact minimum d1 < d_end.
2. else: positive control at W = d_end (stop at first solution, per-case timeout), so d1 = d_end exactly
   when found (otherwise the lower bound d_end stands and the upper bound comes from step 3).
3. every found solution is lifted to concrete pure sd6 faults (X for Z memory, Z for X memory) and injected with
   probability 1 into the noiseless T = 4 circuit annotated with all derived detectors and observables;
   the end-cycle minimum-weight logical (from endcycle.py) is injected after the reset layer of rounds 1..4.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import time

import numpy as np
import stim

from search.experiments.e019.common import get_code, logicals, memory, spec
from search.experiments.e019.dfsrun import run_all_cases

RES = "/Users/ephemeral/Desktop/qec-ai-search/results/E-019-morphing-family"


def annotated(key, basis, T=4):
    """Noiseless T-round circuit (Circ object) + stim annotation with the derived detectors/observables."""
    name, hom, variant = key.split("_")
    code = get_code(name)
    gates, meas, _, _ = spec(code, hom, variant)
    C = memory(code, gates, meas, T, basis)
    return code, C


def inject_check(C, ann, items):
    """items: list of (tick_index, qubit, pauli). Returns (detectors fired, observables flipped)."""
    base = C.stim()
    ins = {}
    for tk, q, p in items:
        ins.setdefault(tk, []).append((q, p))
    newc = stim.Circuit()
    tick = 0
    for inst in base.flattened():
        if inst.name == "TICK":
            for q, p in ins.get(tick, []):
                newc.append(f"{p}_ERROR", [q], 1.0)
            tick += 1
        newc.append(inst)
    newc += ann
    det, obs = newc.compile_detector_sampler().sample(2, separate_observables=True)
    return int(det[0].sum()), int(obs[0].sum()), newc.num_detectors


def lift(sol, P, want):
    faults = P["faults"]
    chosen = []
    for col in sol:
        cand = [i for i in P["cols"][P["keys"][col]] if set(faults[i][4]) <= {want, "I"}]
        assert cand, ("no pure fault for column", col)
        chosen.append(faults[cand[0]])
    items = []
    for (r, li, kind, qs, pp, comp) in chosen:
        tk = li - 1 if kind == "meas" else li
        for q, p in zip(qs, pp):
            if p != "I":
                items.append((tk, q, p))
    desc = [dict(round=r, layer=li, kind=kind, qubits=list(qs), pauli=pp) for (r, li, kind, qs, pp, comp) in chosen]
    return items, desc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("basis")
    ap.add_argument("--timeout_pos", type=float, default=1800)
    ap.add_argument("--npar", type=int, default=6)
    ap.add_argument("--no_posctl", action="store_true", help="skip the W = d_end search (upper bound then rests "
                    "on the injected end-cycle logical only)")
    a = ap.parse_args()
    key, basis = a.key, a.basis
    tag = f"{key}_{basis}_T4"
    t0 = time.time()
    info = json.load(open(f"{RES}/inst/info_{tag}.json"))
    P = pickle.load(open(f"{RES}/inst/inst_{tag}_r1.pkl", "rb"))
    ann = stim.Circuit(open(f"{RES}/inst/ann_{tag}.stim").read())
    ec = json.load(open(f"{RES}/ec/dist_{key}.json"))
    d_end = ec["d"]
    inst = info["inst_path"]
    norb = info["sym_round1"]["n_orbits"]
    outdir = f"{RES}/dfs"
    os.makedirs(outdir, exist_ok=True)
    want = "X" if basis == "Z" else "Z"
    code, C = annotated(key, basis, 4)
    rep = dict(key=key, basis=basis, d_end=d_end, checks={k: info.get(k) for k in (
        "stim_eq_mine", "locality_violations", "weight1_logicals", "all_rounds_equivalent", "fold_ok",
        "sparse_basis", "inst_rows")}, sym=info["sym_round1"], runs=[])
    cpu = 0.0
    # step 1
    W = d_end - 1
    best = None
    while W >= 1:
        res = run_all_cases(inst, W, norb, outdir, npar=a.npar)
        assert all(r["complete"] for r in res), "incomplete DFS"
        cpu += sum(r["sec"] for r in res)
        sols = [s for r in res for s in r["found"]]
        rep["runs"].append(dict(W=W, exhaustive=True, nodes=sum(r["nodes"] for r in res),
                                sec=round(sum(r["sec"] for r in res), 1), found=len(sols)))
        print(key, basis, "W", W, rep["runs"][-1], flush=True)
        if not sols:
            break
        best = min(sols, key=len)
        W = len(best) - 1
    if best is not None:
        rep["d_circ"] = len(best)
        rep["status"] = "exact (< d_end)"
        wit = best
    else:
        rep["lower_bound"] = d_end
        res = [] if a.no_posctl else run_all_cases(inst, d_end, norb, outdir, npar=a.npar, timeout=a.timeout_pos)
        cpu += sum(r["sec"] for r in res)
        sols = [s for r in res for s in r["found"]]
        if not a.no_posctl:
            rep["runs"].append(dict(W=d_end, exhaustive=False, posctl=True, found=len(sols),
                                    sec=round(sum(r["sec"] for r in res), 1),
                                    cases_found=[r["case"] for r in res if r["found"]]))
            print(key, basis, "posctl W", d_end, rep["runs"][-1], flush=True)
        wit = sols[0] if sols else None
        rep["d_circ"] = d_end
        rep["status"] = "exact (= d_end)"
    # step 3: injections
    inj = {}
    if wit is not None:
        items, desc = lift(wit, P, want)
        dets, obs, nd = inject_check(C, ann, items)
        inj["dfs_witness"] = dict(weight=len(wit), cols=wit, faults=desc, detectors_fired=dets,
                                  observables_flipped=obs, n_detectors=nd, ok=dets == 0 and obs > 0)
    # end-cycle logical: code at start of round t (first_c = 0: round t contracts c=(t-1)%2, previous p=1-c)
    typ = want
    ecl = []
    for t in range(1, 5):
        p = 1 - ((t - 1) % 2)
        sup = ec["detail"][f"c{p}_{typ}"]["witness"]
        li = 8 * (t - 1)          # reset layer of round t; tick li = right after it
        dets, obs, nd = inject_check(C, ann, [(li, q, typ) for q in sup])
        ecl.append(dict(t=t, weight=len(sup), detectors_fired=dets, observables_flipped=obs, ok=dets == 0 and obs > 0))
    inj["end_cycle_logical"] = ecl
    rep["injections"] = inj
    ub_ok = all(e["ok"] for e in ecl)
    if best is None and wit is None:
        rep["status"] = "exact (= d_end; upper bound by injected end-cycle logical)" if ub_ok else "lower bound only"
        rep["d_circ"] = d_end if ub_ok else None
    rep["dfs_cpu_sec"] = round(cpu, 1)
    rep["wall_sec"] = round(time.time() - t0, 1)
    json.dump(rep, open(f"{RES}/solve_{tag}.json", "w"), indent=1, default=str)
    print("RESULT", key, basis, rep["status"], "d_circ", rep.get("d_circ"), "d_end", d_end,
          "wit_ok", inj.get("dfs_witness", {}).get("ok"), "ec_ok", ub_ok, "cpu", round(cpu, 1), flush=True)


if __name__ == "__main__":
    main()
