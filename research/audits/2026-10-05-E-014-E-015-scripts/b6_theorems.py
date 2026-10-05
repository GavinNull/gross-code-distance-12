"""B6: independent re-proof of E-015's positive theorems  d_circ = w  for the ASSEMBLED circuits that were evaluated.

Inputs used from E-015: only the evaluated ScheduleSpec stored in results/E-015-bb-generalization/assembled_*.json
(eval.spec).  Everything else is the auditor's: BB matrices from the polynomials (compared with the evaluator task
code), CNOT orders read off the evaluator's stim circuit, extended codes, logical bases, symmetry group (computed:
translations that are code automorphisms AND preserve every check's order, plus logical-class check), orbits,
dfs128 instance, fault simulator (b_ibm.py) for Table I and for an injection-verified weight-w witness.

usage: b6_theorems.py <claim> build|witness
"""
import json
import sys
import time
from pathlib import Path
from collections import defaultdict
import itertools

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, "tests")
import extx  # noqa: E402
import b_ibm  # noqa: E402
from gf2 import logical_basis, rank  # noqa: E402

OUT = Path("results/E-014-E-015-audit")
E15 = Path("results/E-015-bb-generalization")

CLAIMS = {
    # name: (assembled json, task, (l, m, A exps, B exps), w, d)
    "bb72": ("assembled_bb72_h01_x4_34_z30_0.json", "bb72-dcirc", (6, 6, [(3, 0), (0, 1), (0, 2)], [(0, 3), (1, 0), (2, 0)]), 6, 6),
    "cp126": ("assembled_cp126_uniform_x14_z14.json", "cp126-dcirc", (7, 9, [(0, 0), (1, 1), (2, 4)], [(0, 0), (6, 4), (6, 5)]), 9, 10),
    "bb120p": ("assembled_bb120p_h10_x0_0_z0_0.json", "bb120-dcirc", (20, 3, [(0, 0), (3, 2), (7, 2)], [(0, 0), (16, 1), (9, 1)]), 10, 12),
    "bb124": ("assembled_bb124_h01_x0_0_z0_0.json", None, (31, 2, [(0, 0), (27, 1), (17, 0)], [(0, 0), (30, 1), (12, 1)]), 9, 10),
}


def setup(name):
    from evaluators.candidate import parse_schedule, build_circuits
    from evaluators.codes import CSSCode
    js, task, (l, m, Ae, Be), w, d = CLAIMS[name]
    spec = parse_schedule(json.load(open(E15 / js))["eval"]["spec"]).canonical()
    HX, HZ = b_ibm.bb_mats(l, m, Ae, Be)
    info = {}
    if task:
        from evaluators.tasks import build_code, get_task
        css, _ = build_code(get_task(task), None)
        info["own_matrices_equal_task"] = bool((np.asarray(css.HX) % 2 == HX).all() and (np.asarray(css.HZ) % 2 == HZ).all())
        assert info["own_matrices_equal_task"]
    else:
        sys.path.insert(0, "search/experiments/e015")
        from common import get_code
        c = get_code(name)
        info["own_matrices_equal_e015_code"] = bool((np.asarray(c.HX) % 2 == HX).all() and (np.asarray(c.HZ) % 2 == HZ).all())
        assert info["own_matrices_equal_e015_code"]
        css = CSSCode.from_checks(HX, HZ, name=name)
    n = HX.shape[1]
    info["n"] = n
    info["k"] = int(n - rank(HX) - rank(HZ))
    xo, zo, ncyc = b_ibm.orders_from_circuit(build_circuits(spec, css, 2)["Z"], n, HX, HZ)
    info["cycles_per_check_R2"] = ncyc
    return spec, css, HX, HZ, xo, zo, (l, m), w, d, info


def translations(HX, HZ, xo, zo, l, m):
    n2 = l * m
    out = []
    for a in range(l):
        for b in range(m):
            p = np.array([((i // m + a) % l) * m + (i % m + b) % m for i in range(n2)])
            pd = np.concatenate([p, p + n2])
            if not all((Hm[np.ix_(p, pd)] == Hm).all() for Hm in (HX, HZ)):
                continue
            if all(list(oo[p[i]]) == [int(pd[j]) for j in oo[i]] for oo in (xo, zo) for i in range(n2)):
                out.append(((a, b), pd))
    return out


def build(name):
    spec, css, HX, HZ, xo, zo, (l, m), w, d, info = setup(name)
    LX = logical_basis(HZ, HX); LZ = logical_basis(HX, HZ)
    grp = translations(HX, HZ, xo, zo, l, m)
    info["group_order"] = len(grp)
    for kind, H, L, oo in (("X", HZ, LZ, xo), ("Z", HX, LX, zo)):
        e = extx.build(H, L, oo, HX.shape[1])
        info[f"{kind}_logical_classes_preserved"] = all(extx.logical_transform_ok(H, L, pd) for _, pd in grp)
        orb, reps, _ = extx.orbits(e, [pd for _, pd in grp])
        info[f"{kind}_shape"] = list(e["He"].shape)
        info[f"{kind}_orbits"] = len(reps)
        extx.dump128(e["He"], e["Le"], orb, reps, OUT / f"b6_{name}_{kind}.txt")
        N = e["He"].shape[1]
        extx.dump128(e["He"], e["Le"], np.arange(N), list(range(N)), OUT / f"b6_{name}_nosym_{kind}.txt")
    print(json.dumps(info))
    (OUT / f"b6_{name}_build.json").write_text(json.dumps(info, indent=1))


def witness(name, Rs, found_file_X, found_file_Z):
    """Table I check + realise one DFS-found weight-w ext logical as w circuit faults (one per column, chosen by
    meet in the middle over all faults realising that column) flipping no detector and some observable."""
    from evaluators.candidate import build_circuits
    from evaluators.noise import add_noise
    spec, css, HX, HZ, xo, zo, (l, m), w, d, info = setup(name)
    LX = logical_basis(HZ, HX); LZ = logical_basis(HX, HZ)
    n = HX.shape[1]
    res = []
    for basis, ff in (("Z", found_file_X), ("X", found_file_Z)):
        H, L, oo, part = (HZ, LZ, xo, "X") if basis == "Z" else (HX, LX, zo, "Z")
        e = extx.build(H, L, oo, n)
        He, Le = e["He"], e["Le"]
        colkey = {He[:, j].tobytes() + Le[:, j].tobytes(): j for j in range(He.shape[1])}
        sols = []
        for line in open(ff):
            if line.startswith("FOUND"):
                sols.append([int(x) for x in line.split("cols:")[1].split()])
        for S in sols:
            x = np.zeros(He.shape[1], int); x[S] = 1
            assert not ((He @ x) % 2).any() and ((Le @ x) % 2).any() and len(set(S)) == w
        for R in Rs:
            t0 = time.time()
            circ = add_noise(build_circuits(spec, css, R)[basis], "sd6", 1e-3).flattened()
            ops, faults = b_ibm.enumerate_faults(circ)
            D, O, Xf, Zf = b_ibm.simulate(ops, faults, circ.num_qubits)
            img = (Xf if part == "X" else Zf)[:n].astype(np.int64)
            hk = (H.astype(np.int64) @ img) % 2
            lk = (L.astype(np.int64) @ img) % 2
            exc = 0
            groups = defaultdict(list)
            for f in range(len(faults)):
                if not hk[:, f].any() and not lk[:, f].any():
                    continue
                j = colkey.get(hk[:, f].astype(np.uint8).tobytes() + lk[:, f].astype(np.uint8).tobytes())
                if j is None:
                    exc += 1
                    continue
                groups[j].append(f)
            detv = [int.from_bytes(np.packbits(D[:, f]).tobytes(), "big") for f in range(len(faults))]
            obsv = [int.from_bytes(np.packbits(O[:, f]).tobytes(), "big") for f in range(len(faults))]
            # one representative fault per (column, signature): faults with equal signature are interchangeable
            for j in list(groups):
                seen = {}
                for f in groups[j]:
                    seen.setdefault((detv[f], obsv[f]), f)
                groups[j] = list(seen.values())
            hit = None
            for S in sols:
                G = [groups[j] for j in S]
                h = len(G) // 2
                left = defaultdict(list)
                for c in itertools.product(*G[:h]):
                    dm = om = 0
                    for f in c:
                        dm ^= detv[f]; om ^= obsv[f]
                    left[dm].append((om, c))
                for c in itertools.product(*G[h:]):
                    dm = om = 0
                    for f in c:
                        dm ^= detv[f]; om ^= obsv[f]
                    for om2, c2 in left.get(dm, ()):
                        if om ^ om2:
                            hit = (S, c2 + c)
                            break
                    if hit:
                        break
                if hit:
                    break
            rec = dict(basis=basis, R=R, tableI_exceptions=exc, cols_realised=len(groups), n_cols=He.shape[1],
                       n_candidate_ext_logicals=len(sols), witness_found=hit is not None, sec=round(time.time() - t0, 1))
            if hit:
                fs = hit[1]
                # verify with stim: build the DEM-level check -- distinct DEM terms, XOR of detectors = 0, obs != 0
                sig = {(np.packbits(D[:, f]).tobytes(), np.packbits(O[:, f]).tobytes()) for f in fs}
                rec["witness_faults"] = [(faults[f][0], faults[f][1]) for f in fs]
                rec["witness_distinct_dem_terms"] = len(sig)
                acc_d = 0; acc_o = 0
                for f in fs:
                    acc_d ^= detv[f]; acc_o ^= obsv[f]
                rec["witness_check"] = dict(detectors_flipped=bin(acc_d).count("1"), observables_flipped=bin(acc_o).count("1"))
                # independent stim check: inject the w Pauli faults as deterministic errors into the noiseless circuit
                rec["stim_injection"] = stim_inject(circ, ops, [faults[f] for f in fs])
            print(rec, flush=True)
            res.append(rec)
    (OUT / f"b6_{name}_witness.json").write_text(json.dumps(res, indent=1, default=str))


def stim_inject(noisy_flat, ops, fl):
    """Rebuild the circuit: drop all noise, insert the chosen Paulis as probability-1 errors at their positions;
    sample once with stim and report detector / observable flips."""
    import stim
    at = defaultdict(list)
    for k, pp in fl:
        at[k] += pp
    c = stim.Circuit()
    for k, inst in enumerate(ops):
        if inst.name in ("DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Z_ERROR", "Y_ERROR"):
            for q, P in at.get(k, []):
                c.append(f"{P}_ERROR", [q], 1.0)
            continue
        c.append(inst)
    s = c.compile_detector_sampler()
    det, obs = s.sample(4, separate_observables=True)
    return dict(det_flips=int(det.sum(1).max()), det_flips_min=int(det.sum(1).min()), obs_flips=int(obs[0].sum()),
                obs_consistent=bool((obs == obs[0]).all()))


if __name__ == "__main__":
    name, what = sys.argv[1], sys.argv[2]
    if what == "build":
        build(name)
    else:
        witness(name, [int(x) for x in sys.argv[3].split(",")], sys.argv[4], sys.argv[5])
