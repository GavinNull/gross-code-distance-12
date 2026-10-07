"""Exact decision "d_circ <= d_ext?" for an interleaved circuit whose extended code has d_ext < d (IBM BB72: d_ext = 5).

Argument (per memory basis; Z basis uses the X-type extended code (HZ, LZ), X basis the Z-type one (HX, LX)):
  an undetected logical fault set F has an image (sum of the relevant data parts of its faults, propagated to the
  end) that is an ext logical (telescoping of the detectors of the measured type + observable flip).  If
  |F| = w = d_ext, then (no logical of weight < w exists) the images are w DISTINCT NONZERO columns and they form
  a weight-w ext logical.  Hence every fault of F has its image in U = union of supports of all weight-w ext
  logicals.  Restrict the DEM to error terms having at least one circuit location with image in U and decide
  by an exact meet-in-the-middle enumeration (not CP-SAT; docstring corrected 2026-10-07 per audit) whether <= w of them
  flip no detector and flip an observable.  Infeasible => d_circ >= w+1 for this R.
  Note (audit 2026-10-05): the right half does not reject repeated DEM terms; this can only add false positives,
  so a 0-hit result is unaffected.  Any-R extension: see research/audits/2026-10-05-E-014-E-015.md.
  (Weights < w are already excluded by Prop. 3: d_circ >= d_ext = w.)

    PYTHONPATH=.:tests uv run python search/experiments/e015/ibm_lift.py --code bb72 --task bb72-dcirc --w 5 --R 1 2 3 4 5
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, "tests")
import numpy as np  # noqa: E402
import stim  # noqa: E402

from common import OUT, get_code, now  # noqa: E402
from evaluators.candidate import build_circuits, parse_schedule  # noqa: E402
from evaluators.noise import add_noise  # noqa: E402
from evaluators.tasks import build_code, get_task  # noqa: E402
from schedule_helpers import from_baseline  # noqa: E402
from search.codes.schedule import default_schedule  # noqa: E402
from search.noninterleaved.ext import extended_matrices, orders_from_schedule, residual_supports  # noqa: E402

BIN = str(OUT / "dfs128")


def all_min_logicals(He, Le, w, tag):
    """All ext logicals of weight <= w via dfs128 without symmetry (case j: contains column j, none smaller)."""
    path = OUT / f"inst_nosym_{tag}.txt"
    R, N = He.shape
    with open(path, "w") as f:
        f.write(f"{R} {N} {N}\n")
        for j in range(N):
            hm = sum(1 << int(i) for i in np.nonzero(He[:, j])[0])
            lm = sum(1 << int(i) for i in np.nonzero(Le[:, j])[0])
            f.write(f"{hm & ((1 << 64) - 1)} {hm >> 64} {lm} {j}\n")
        f.write(" ".join(map(str, range(N))) + "\n")
    sols, nodes = [], 0
    for j in range(N):
        out = subprocess.run([BIN, str(path), str(w), str(j)], capture_output=True, text=True, check=True).stdout
        m = re.search(r"nodes=(\d+) found=(\d+)", out)
        nodes += int(m.group(1))
        found = int(m.group(2))
        lines = [l for l in out.splitlines() if l.startswith("FOUND")]
        assert found == len(lines), "more than 50 solutions in one case; raise the print limit"
        for l in lines:
            sols.append(sorted(int(x) for x in l.split("cols:")[1].split()))
    return sols, nodes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="bb72")
    ap.add_argument("--task", default="bb72-dcirc")
    ap.add_argument("--w", type=int, default=5)
    ap.add_argument("--R", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--tl", type=float, default=600)
    ap.add_argument("--lrc", type=int, nargs=4, default=None, help="positive control: two-colour LRC (y parity) x0 x1 z0 z1")
    a = ap.parse_args()
    code = get_code(a.code)
    css, _ = build_code(get_task(a.task), None)
    assert (np.asarray(css.HX) == code.HX).all() and (np.asarray(css.HZ) == code.HZ).all()
    if a.lrc:
        from assemble import build
        sched = build(a.code, "01", a.lrc[:2], a.lrc[2:])[1]
    else:
        sched = default_schedule(code)
    xo, zo = orders_from_schedule(sched)
    spec = parse_schedule(from_baseline(sched)).canonical()
    n = css.n
    res = {"code": a.code, "w": a.w, "per": []}
    for basis in "ZX":
        # Z-basis memory: observable = Z logicals, flipped by X parts -> X-type ext code (HZ, LZ, X-check orders)
        H, L, orders, part = (css.HZ, css.LZ, xo, 0) if basis == "Z" else (css.HX, css.LX, zo, 1)
        H = np.asarray(H, np.int64); L = np.asarray(L, np.int64)
        He, Le, lab = extended_matrices(H, L, [s for o in orders for s in residual_supports(o)])
        sols, nodes = all_min_logicals(He, Le, a.w, f"{a.code}_{basis}")
        Ucols = sorted({j for s in sols for j in s})
        Ukeys = {He[:, j].astype(np.uint8).tobytes() + Le[:, j].astype(np.uint8).tobytes() for j in Ucols}
        print(f"[{now()}] {basis}: ext {He.shape}, {len(sols)} logicals of weight <= {a.w} "
              f"(weights {sorted(set(map(len, sols)))}), |U| = {len(Ucols)} columns, DFS nodes {nodes}", flush=True)
        for R in a.R:
            t0 = time.time()
            circ = add_noise(build_circuits(spec, css, R)[basis], "sd6", 1e-3).flattened()
            ops = list(circ)
            dem = circ.detector_error_model(decompose_errors=False)
            ex = circ.explain_detector_error_model_errors(reduce_to_one_representative_error=False)
            # propagate a Pauli product from after instruction k to the end; return data part (X or Z)
            nq = circ.num_qubits
            cache = {}

            def image(k, prod):
                key = (k, tuple((g.gate_target.value, g.gate_target.is_x_target, g.gate_target.is_z_target,
                                 g.gate_target.is_y_target) for g in prod))
                if key in cache:
                    return cache[key]
                x = np.zeros(nq, bool); z = np.zeros(nq, bool)
                for q, isx, isz, isy in key[1]:
                    if isx or isy:
                        x[q] = True
                    if isz or isy:
                        z[q] = True
                for inst in ops[k + 1:]:
                    nm = inst.name
                    if nm in ("CX", "CNOT"):
                        t = [tt.value for tt in inst.targets_copy()]
                        c = np.array(t[0::2]); g = np.array(t[1::2])
                        x[g] ^= x[c]; z[c] ^= z[g]
                    elif nm in ("R", "RX", "RZ"):
                        t = [tt.value for tt in inst.targets_copy()]
                        x[t] = False; z[t] = False
                    elif nm in ("TICK", "DETECTOR", "OBSERVABLE_INCLUDE", "DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR",
                                "Z_ERROR", "Y_ERROR", "QUBIT_COORDS", "SHIFT_COORDS") or nm.startswith("M"):
                        pass
                    else:
                        raise ValueError(nm)
                v = (x if part == 0 else z)[:n].astype(np.int64)
                kk = ((H @ v) % 2).astype(np.uint8).tobytes() + ((L @ v) % 2).astype(np.uint8).tobytes()
                cache[key] = kk
                return kk
            keep, nloc, other = [], 0, 0
            zero = b"\x00" * (H.shape[0] + L.shape[0])
            for e in ex:
                ok = False
                for loc in e.circuit_error_locations:
                    assert not loc.flipped_measurement.observable_indices if hasattr(loc.flipped_measurement, "observable_indices") else True
                    nloc += 1
                    k = loc.stack_frames[0].instruction_offset
                    kk = image(k, loc.flipped_pauli_product)
                    if kk in Ukeys:
                        ok = True
                    elif kk != zero:
                        other += 1
                if ok:
                    keep.append(e.dem_error_terms)
            # exact meet-in-the-middle over each weight-w ext logical S: pick one DEM term per column of S
            # (terms grouped by the images of their circuit locations); symptoms must cancel, observables must not.
            term_det, term_obs, groups = [], [], {}
            for ti, e in enumerate(ex):
                dm = om = 0
                for t in e.dem_error_terms:
                    if t.dem_target.is_relative_detector_id():
                        dm ^= 1 << t.dem_target.val
                    elif t.dem_target.is_logical_observable_id():
                        om ^= 1 << t.dem_target.val
                term_det.append(dm); term_obs.append(om)
                for loc in e.circuit_error_locations:
                    kk = image(loc.stack_frames[0].instruction_offset, loc.flipped_pauli_product)
                    groups.setdefault(kk, set()).add(ti)
            colkey = [He[:, j].astype(np.uint8).tobytes() + Le[:, j].astype(np.uint8).tobytes() for j in range(He.shape[1])]
            hits, combos = [], 0
            gsizes = []
            for S in sols:
                G = [sorted(groups.get(colkey[j], ())) for j in S]
                gsizes.append([len(g) for g in G])
                h = len(G) // 2
                import itertools
                left = {}
                for c in itertools.product(*G[:h]):
                    if len(set(c)) < len(c):
                        continue
                    dm = om = 0
                    for t in c:
                        dm ^= term_det[t]; om ^= term_obs[t]
                    left.setdefault(dm, []).append((om, c))
                for c in itertools.product(*G[h:]):
                    combos += 1
                    dm = om = 0
                    for t in c:
                        dm ^= term_det[t]; om ^= term_obs[t]
                    for om2, c2 in left.get(dm, ()):
                        if om ^ om2 and not set(c) & set(c2):
                            hits.append({"S": S, "terms": list(c2 + c)})
            rec = {"basis": basis, "R": R, "dem_errors": dem.num_errors, "explained_terms": len(ex),
                   "locations": nloc, "kept_terms": len(keep), "group_sizes_first": gsizes[:3],
                   "max_group": max(max(g) for g in gsizes), "min_group": min(min(g) for g in gsizes),
                   "right_combos": combos, "undetected_logicals_of_weight_w": len(hits), "examples": hits[:3],
                   "sec": round(time.time() - t0, 1)}
            print(f"[{now()}] {basis} R={R}: {rec}", flush=True)
            res["per"].append({**rec, "num_min_logicals": len(sols), "U": len(Ucols)})
            (OUT / f"ibm_lift_{a.code}_w{a.w}{'_lrc' if a.lrc else ''}.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
