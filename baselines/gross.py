"""E-002: IBM gross code [[144,12,12]] baseline (arXiv:2308.07915).

  uv run python -m baselines.gross --config experiments/E-002-gross-baseline.yaml [--stage ...]

Stages (default: all, in order):
  verify    code parameters (n, k via GF(2) rank, HX HZ^T = 0), BP-OSD code-distance upper bound,
            schedule validation, noiseless determinism (both bases, detectors='both')
  smoke     few-round, few-shot sinter run to check the pipeline
  distance  circuit-level distance upper bounds: stim search_for_undetectable_logical_errors
            (small round counts) + BP-OSD random-logical method of the paper (Eq. 12)
  sample    sinter + BP-OSD at the yaml p values, both memory bases, with CPU-budget guard
  analyze   per-round logical error rates + CIs, comparison with paper fit (Table 6)

Per-round conversion (paper Sec. 3):  pL = 1 - (1 - PL(Nc))^(1/Nc),  Nc = rounds.
Combined X+Z (the paper counts a failure if either the X or Z decoding fails, decoded
independently):  PL_comb = 1 - (1 - PL_Zmem)(1 - PL_Xmem)  (independence approximation).
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import yaml

from baselines.bb_code import BBCode, gf2_rank, distance_upper_bound_bposd
from baselines.circuit import memory_circuit, check_deterministic
from baselines.schedule import SCHEDULES, bb_term_schedule

RESULTS = Path("results")

DECODER_KW = dict(max_bp_iters=10000, bp_method="min_sum", osd_order=7, osd_method="osd_cs",
                  ms_scaling_factor=0)   # IBM repo decoder_run.py settings

NOISE_DOC = ("uniform circuit-level depolarizing: DEPOLARIZE2(p) after every CX; X_ERROR(p) after R / "
             "Z_ERROR(p) after RX; measurement result flip p (M(p)/MX(p)); DEPOLARIZE1(p) on every qubit "
             "idle in a layer (in the IBM schedule only data qubits ever idle: 2n = 288 locations/cycle). "
             "Initial data reset and final data readout are noisy; no noiseless closing cycle.")


def parse_poly(terms):
    return [t.replace(" ", "") for t in terms]


def load(cfg_path):
    cfg = yaml.safe_load(open(cfg_path))
    cc = cfg["code"]
    code = BBCode(cc["l"], cc["m"], parse_poly(cc["A"]), parse_poly(cc["B"]))
    sched = SCHEDULES[cfg["schedule"]](code)
    out = RESULTS / cfg["id"]
    out.mkdir(parents=True, exist_ok=True)
    return cfg, code, sched, out


def circuits(code, sched, rounds, basis, p, detectors="basis"):
    L = code.logical_z() if basis == "Z" else code.logical_x()
    return memory_circuit(sched, code.HX, code.HZ, L, rounds, basis, p, detectors)


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))


# ----------------------------------------------------------------------------- stages

def stage_verify(cfg, code, sched, out):
    t0 = time.process_time()
    HX, HZ = code.HX, code.HZ
    res = {
        "n": code.n, "k": code.k, "rank_HX": gf2_rank(HX), "rank_HZ": gf2_rank(HZ),
        "HX_HZt_zero": bool(not ((HX.astype(int) @ HZ.T.astype(int)) % 2).any()),
        "row_weights": sorted(set(HX.sum(1).tolist()) | set(HZ.sum(1).tolist())),
        "col_weights_HX": sorted(set(HX.sum(0).tolist())),
    }
    LX, LZ = code.logical_x(), code.logical_z()
    res["logical_pairing_rank"] = gf2_rank((LX.astype(int) @ LZ.T.astype(int)) % 2)
    seed = cfg.get("seed", 0)
    dmin, vals = distance_upper_bound_bposd(code, trials=200, seed=seed)
    res["code_distance_upper_bound_bposd"] = dmin
    res["code_distance_bposd_hist"] = {int(v): vals.count(v) for v in sorted(set(vals))}
    sched.validate(HX, HZ)
    res["schedule_valid"] = True
    res["schedule_layers"] = sched.depth
    res["cnot_layers"] = sum(1 for L in sched.layers if L.cnots)
    res["cnots_per_cycle"] = sum(len(L.cnots) for L in sched.layers)
    det = {}
    for basis in "ZX":
        for r in (1, 2, 3, cfg["rounds"]):
            c = circuits(code, sched, r, basis, 0.0, detectors="both")
            det[f"{basis}_r{r}"] = check_deterministic(c)
    res["noiseless_determinism"] = det
    # negative control: a shuffled X order that should break commutation
    bad = bb_term_schedule(code, [None, 0, 4, 3, 5, 1, 2], [0, 2, 3, 4, 5, 1, None], "neg_control")
    try:
        bad.validate(HX, HZ)
        c = memory_circuit(bad, HX, HZ, LZ, 2, "Z", 0.0, "both")
        r = check_deterministic(c)
        res["negative_control"] = {"raised": False, **r}
    except Exception as e:  # noqa: BLE001
        res["negative_control"] = {"raised": True, "error": str(e)[:200]}
    c12 = circuits(code, sched, cfg["rounds"], "Z", 0.003)
    res["dem_Z_r12"] = {"detectors": c12.num_detectors,
                        "errors": c12.detector_error_model().num_errors,
                        "ticks": sum(1 for i in c12.flattened() if i.name == "TICK")}
    c12x = circuits(code, sched, cfg["rounds"], "X", 0.003)
    res["dem_X_r12"] = {"detectors": c12x.num_detectors, "errors": c12x.detector_error_model().num_errors}
    res["cpu_seconds"] = time.process_time() - t0
    (out / "schedule_ibm_depth8.json").write_text(sched.to_json())
    (out / "circuit_Z_r12_p0.003.stim").write_text(str(c12))
    dump(out / "verify.json", res)
    print(json.dumps({k: v for k, v in res.items()}, indent=1, default=str))
    return res


def _sinter_tasks(cfg, code, sched, bases, ps, rounds):
    import sinter
    tasks = []
    for basis in bases:
        for p in ps:
            c = circuits(code, sched, rounds, basis, p)
            tasks.append(sinter.Task(circuit=c, json_metadata={"basis": basis, "p": p, "rounds": rounds,
                                                               "schedule": sched.name}))
    return tasks


def _decoders():
    from stimbposd import SinterDecoder_BPOSD
    return {"bposd": SinterDecoder_BPOSD(**DECODER_KW)}


def stage_smoke(cfg, code, sched, out):
    import sinter
    tasks = _sinter_tasks(cfg, code, sched, "ZX", [0.005], rounds=3)
    stats = sinter.collect(num_workers=min(5, cfg["budget"]["num_workers"]), tasks=tasks,
                           decoders=["bposd"], custom_decoders=_decoders(), max_shots=200, max_errors=50,
                           save_resume_filepath=str(out / "smoke.csv"))
    for s in stats:
        print(s.json_metadata, s.shots, s.errors, f"{s.seconds:.1f}s")
    return stats


def stage_distance(cfg, code, sched, out, rounds_list=(1, 2, 3), bposd_trials=2000):
    """Circuit-level distance upper bounds."""
    import stim  # noqa: F401
    res = {"stim_search": [], "bposd_eq12": []}
    path = out / "circuit_distance.json"
    for basis in "ZX":
        for r in rounds_list:
            c = circuits(code, sched, r, basis, 0.001)
            # (4, 6) was tried first: >4.5 GB RSS within 1 min at rounds=1 -> killed; keep the search pruned.
            for deg, size in ((3, 4), (4, 4)):
                t0 = time.process_time()
                try:
                    errs = c.search_for_undetectable_logical_errors(
                        dont_explore_detection_event_sets_with_size_above=size,
                        dont_explore_edges_with_degree_above=deg,
                        dont_explore_edges_increasing_symptom_degree=False,
                        canonicalize_circuit_errors=True)
                    w = len(errs)
                except ValueError as e:   # nothing found within the pruned search
                    w, errs = None, str(e)[:120]
                dt = time.process_time() - t0
                row = {"basis": basis, "rounds": r, "max_degree": deg, "max_event_set": size,
                       "weight_found": w, "cpu_s": round(dt, 1)}
                res["stim_search"].append(row)
                print(row, flush=True)
                dump(path, res)
    # paper's method (Eq. 12) on stim DEM: min |xi| s.t. D xi = 0, eta.xi = 1, eta = random
    # combination of observable rows + detector rows. Unit weights (count faults).
    from ldpc import BpOsdDecoder
    from stimbposd.dem_to_matrices import detector_error_model_to_check_matrices
    rng = np.random.default_rng(cfg.get("seed", 0))
    for basis in "ZX":
        for r in sorted(set(rounds_list) | {cfg["rounds"]}):
            c = circuits(code, sched, r, basis, 0.001)
            m = detector_error_model_to_check_matrices(c.detector_error_model(), allow_undecomposed_hyperedges=True)
            D = m.check_matrix.tocsr().astype(np.uint8)
            Lm = m.observables_matrix.tocsr().astype(np.uint8)
            t0 = time.process_time()
            best, hist = None, {}
            ntr = bposd_trials if r <= 3 else bposd_trials // 4
            for _ in range(ntr):
                a = rng.integers(0, 2, Lm.shape[0])
                if not a.any():
                    a[rng.integers(Lm.shape[0])] = 1
                b = rng.integers(0, 2, D.shape[0])
                eta = ((a @ Lm) + (b @ D)) % 2
                import scipy.sparse as sp
                H = sp.vstack([D, sp.csr_matrix(eta.astype(np.uint8))]).tocsr()
                syn = np.zeros(H.shape[0], dtype=np.uint8)
                syn[-1] = 1
                dec = BpOsdDecoder(H, error_rate=0.01, max_iter=100, bp_method="minimum_sum",
                                   osd_method="osd_cs", osd_order=10)
                xi = dec.decode(syn)
                w = int(xi.sum())
                # sanity: xi is undetectable and flips some observable
                assert not ((D @ xi) % 2).any() and ((Lm @ xi) % 2).any()
                hist[w] = hist.get(w, 0) + 1
                best = w if best is None else min(best, w)
            row = {"basis": basis, "rounds": r, "trials": ntr, "min_weight": best,
                   "hist": {int(k): v for k, v in sorted(hist.items())},
                   "cpu_s": round(time.process_time() - t0, 1)}
            res["bposd_eq12"].append(row)
            print(row, flush=True)
            dump(path, res)
    return res


def stage_sample(cfg, code, sched, out, budget_cpu_s, only_p=None, max_shots=None):
    """Run points from high p to low p; each sinter.collect call is one (basis,p) point.
    Budget guard: stop when cumulative decoder CPU seconds (sinter `seconds`) exceed budget."""
    import sinter
    nw = min(5, cfg["budget"]["num_workers"])
    ps = sorted(only_p or cfg["noise"]["p"], reverse=True)
    rounds = cfg["rounds"]
    csv = out / "stats.csv"
    used = 0.0
    log = []
    for p in ps:
        for basis in "ZX":
            if used > budget_cpu_s:
                print(f"BUDGET STOP before basis={basis} p={p}: used {used:.0f}s", flush=True)
                log.append({"basis": basis, "p": p, "skipped": "budget"})
                continue
            tasks = _sinter_tasks(cfg, code, sched, basis, [p], rounds)
            st = sinter.collect(num_workers=nw, tasks=tasks, decoders=["bposd"], custom_decoders=_decoders(),
                                max_shots=int(max_shots or cfg.get("max_shots", 100_000)),
                                max_errors=int(cfg.get("max_errors", 100)),
                                save_resume_filepath=str(csv))
            # collect() also returns stats resumed from the CSV for OTHER tasks -> select ours
            s = next(x for x in st if x.json_metadata == tasks[0].json_metadata and x.decoder == "bposd")
            used += s.seconds
            row = {"basis": basis, "p": p, "shots": s.shots, "errors": s.errors, "discards": s.discards,
                   "decoder_seconds": round(s.seconds, 1), "cumulative_decoder_seconds": round(used, 1)}
            log.append(row)
            print(row, flush=True)
            dump(out / "sample_log.json", log)
    return log


def clopper_pearson(k, n, alpha=0.05):
    from scipy.stats import beta
    lo = 0.0 if k == 0 else beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - alpha / 2, k + 1, n - k)
    return lo, hi


def per_round(P, N):
    return 1 - (1 - P) ** (1 / N)


def paper_fit(p):
    """arXiv:2308.07915 Table 6 for [[144,12,12]], d'_circ = 10: pL = p^5 exp(c0 + c1 p + c2 p^2)."""
    return p ** 5 * math.exp(18.04 + 1337 * p - 96007 * p * p)


def stage_analyze(cfg, code, sched, out):
    import sinter
    stats = sinter.read_stats_from_csv_files(str(out / "stats.csv"))
    agg = {}
    for s in stats:
        key = (s.json_metadata["basis"], s.json_metadata["p"])
        agg[key] = s if key not in agg else agg[key] + s
    N = cfg["rounds"]
    rows = []
    for p in sorted(cfg["noise"]["p"]):
        r = {"p": p, "paper_fit_pL": paper_fit(p)}
        Ps = {}
        for basis in "ZX":
            s = agg.get((basis, p))
            if s is None:
                continue
            P = s.errors / s.shots
            lo, hi = clopper_pearson(s.errors, s.shots)
            Ps[basis] = (P, lo, hi)
            r[basis] = {"shots": s.shots, "errors": s.errors, "PL": P, "PL_ci95": [lo, hi],
                        "pL_per_round": per_round(P, N), "pL_ci95": [per_round(lo, N), per_round(hi, N)],
                        "decoder_seconds": round(s.seconds, 1)}
        if len(Ps) == 2:
            comb = lambda a, b: 1 - (1 - a) * (1 - b)  # noqa: E731
            Pc = comb(Ps["Z"][0], Ps["X"][0])
            lo = comb(Ps["Z"][1], Ps["X"][1])
            hi = comb(Ps["Z"][2], Ps["X"][2])
            r["combined"] = {"PL": Pc, "pL_per_round": per_round(Pc, N),
                             "pL_ci95_conservative": [per_round(lo, N), per_round(hi, N)],
                             "ratio_to_paper_fit": per_round(Pc, N) / paper_fit(p)}
        rows.append(r)
    dump(out / "summary.json", {"rounds": N, "decoder": DECODER_KW, "noise": NOISE_DOC, "points": rows})
    for r in rows:
        print(json.dumps(r, default=float))
    _plot(rows, out / "pL_vs_p.png")
    return rows


def _plot(rows, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5, 4))
    pp = np.linspace(0.0025, 0.0065, 50)
    ax.plot(pp, [paper_fit(x) for x in pp], "k--", lw=1, label="paper fit (Table 6, arXiv:2308.07915)")
    for key, mk, lab in (("Z", "o", "Z-memory"), ("X", "s", "X-memory"), ("combined", "D", "X+Z combined")):
        xs, ys, lo, hi = [], [], [], []
        for r in rows:
            if key not in r:
                continue
            d = r[key]
            ci = d.get("pL_ci95") or d.get("pL_ci95_conservative")
            xs.append(r["p"]); ys.append(d["pL_per_round"]); lo.append(d["pL_per_round"] - ci[0]); hi.append(ci[1] - d["pL_per_round"])
        if xs:
            ax.errorbar(xs, ys, yerr=[lo, hi], fmt=mk, ms=4, capsize=2, label=lab)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("physical error rate p"); ax.set_ylabel("logical error rate per cycle pL")
    ax.set_title("[[144,12,12]] IBM schedule, 12 cycles, BP-OSD")
    ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(path, dpi=130)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--stage", default="all", choices=["all", "verify", "smoke", "distance", "sample", "analyze"])
    ap.add_argument("--p", type=float, nargs="*", default=None, help="sample only these p (subset of yaml)")
    ap.add_argument("--max-shots", type=int, default=None, help="override per-point shot cap (budget)")
    ap.add_argument("--sample-budget-cpu-s", type=float, default=None,
                    help="decoder CPU-second budget for the sample stage (default: 70%% of yaml budget)")
    a = ap.parse_args()
    cfg, code, sched, out = load(a.config)
    budget = a.sample_budget_cpu_s or 0.7 * cfg["budget"]["cpu_hours"] * 3600
    stages = ["verify", "smoke", "distance", "sample", "analyze"] if a.stage == "all" else [a.stage]
    for st in stages:
        print(f"=== stage {st} ===", flush=True)
        if st == "verify":
            stage_verify(cfg, code, sched, out)
        elif st == "smoke":
            stage_smoke(cfg, code, sched, out)
        elif st == "distance":
            stage_distance(cfg, code, sched, out)
        elif st == "sample":
            stage_sample(cfg, code, sched, out, budget, a.p, a.max_shots)
        elif st == "analyze":
            stage_analyze(cfg, code, sched, out)


if __name__ == "__main__":
    main()
