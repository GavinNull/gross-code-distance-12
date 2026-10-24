"""Recompute every logical-error-rate number of SM S7 and S8 from the shipped sampling statistics, and check that the
sampled circuits are the circuits of this package.

Data (data/ler/, sinter CSV files; one row per (task, decoder) batch, task = circuit + noise + memory basis):
  sd6_lambda_bb90/     [[90,8,10]]: c11, c13, c16 vs IBM's depth-8 circuit, R = 10, SD6 with p_idle = lambda p
  sd6_lambda_gross/    gross: u11 vs Fig. 12 and IBM's depth-8 circuit, R = 12 (earlier/: the identical tasks of an
                       earlier sampling of Fig. 12 and IBM's circuit, pooled as in the paper)
  neutral_atom/        both codes, neutral-atom model of SM S8 (main.csv: sets cur, cur x 0.5, proj; sens.csv:
                       sensitivity variants), gross R = 12, [[90,8,10]] R = 10
  independent_resampling/  the second, independently written sampling pipeline (own circuits, noise and decoder
                       calls), per-job counts and its summaries; the paper's pooled values combine both pipelines
Per round: eps = eps_Z + eps_X, eps_b = 1 - (1 - P_b)^(1/R), P_b = failures / shots of basis b; 95% Jeffreys intervals
by beta-posterior Monte Carlo (40000 draws, seed 1), ratios from the same draws.  The recomputed rows must equal the
shipped summaries (summary.json) to 1e-12.

    python code/ler/tables.py                      # recompute, compare with summary.json, print the paper's ratios
    python code/ler/tables.py --verify-circuits N  # also rebuild N sampled tasks per data set (all: N = 0) with the
                                                   # package's template and noise models and compare sinter's task hash
                                                   # (strong_id: hash of circuit text, DEM, decoder and metadata)
"""
import argparse
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_cli import Verdict                      # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "ler"
NS = 40000


def read(files):
    import sinter
    out = []
    for f in files:
        out += list(sinter.read_stats_from_csv_files(f))
    return out


def sd6_bb90():
    R, PERIOD = 10, {"c11": 11, "c12": 12, "c13": 13, "c16": 16, "ibm": 8}
    agg = defaultdict(lambda: [0, 0, 0.0])
    for s in read(sorted(f for f in glob.glob(str(D / "sd6_lambda_bb90" / "*.csv")) if not f.endswith("timing.csv"))):
        m = s.json_metadata
        if m["R"] != R:
            continue
        k = (m["noise"], m["circ"], m["p"], s.decoder, m["basis"])
        agg[k][0] += s.shots; agg[k][1] += s.errors; agg[k][2] += s.seconds
    rng = np.random.default_rng(1)
    rows = {}
    for (nz, c, p, dec) in sorted({k[:4] for k in agg}):
        if not all((nz, c, p, dec, b) in agg for b in "ZX"):
            continue
        draws = 0; row = {"noise": nz, "circ": c, "p": p, "dec": dec}
        for b in "ZX":
            n, k, sec = agg[(nz, c, p, dec, b)]
            P = rng.beta(k + 0.5, n - k + 0.5, NS)
            draws = draws + (1 - (1 - P) ** (1 / R))
            row[b] = dict(shots=n, errors=k, eps=1 - (1 - k / n) ** (1 / R), sinter_s=round(sec))
        pt = row["Z"]["eps"] + row["X"]["eps"]
        lo, hi = np.quantile(draws, [0.025, 0.975])
        row.update(eps=pt, lo=float(lo), hi=float(hi), per_layer=pt / PERIOD[c], draws=draws)
        rows[(nz, c, p, dec)] = row
    out = []
    for key, r in sorted(rows.items(), key=lambda x: (x[0][0], x[0][3], -x[0][2], x[0][1])):
        nz, c, p, dec = key
        for nm in ("ibm", "c11"):
            ref = rows.get((nz, nm, p, dec))
            if ref is None or nm == c or c == "ibm":
                continue
            rr = r["draws"] / ref["draws"]
            pt = r["eps"] / ref["eps"] if ref["eps"] > 0 else None
            r[f"ratio_vs_{nm}"] = [pt, float(np.quantile(rr, 0.025)), float(np.quantile(rr, 0.975))]
            f = PERIOD[nm] / PERIOD[c]
            r[f"ratio_per_layer_vs_{nm}"] = [pt * f if pt is not None else None, float(np.quantile(rr * f, 0.025)),
                                             float(np.quantile(rr * f, 0.975))]
        out.append({k: v for k, v in r.items() if k != "draws"})
    return out


def sd6_gross():
    R, PERIOD = 12, {"u11": 11, "fig12": 8, "ibm": 8}
    src = {"new": sorted(glob.glob(str(D / "sd6_lambda_gross" / "*.csv"))),
           "old": sorted(glob.glob(str(D / "sd6_lambda_gross" / "earlier" / "*.csv")))}
    agg = defaultdict(lambda: {"new": [0, 0], "old": [0, 0], "sec": 0.0})
    for tag, files in src.items():
        for s in read(files):
            m = s.json_metadata
            if m.get("R") != R or m["circ"] not in PERIOD:
                continue
            nz = m.get("noise", "lam1")
            nz = "lam1" if nz == "sd6" else nz
            k = (nz, m["circ"], m["p"], s.decoder, m["basis"])
            agg[k][tag][0] += s.shots; agg[k][tag][1] += s.errors
            if tag == "new":
                agg[k]["sec"] += s.seconds
    rng = np.random.default_rng(1)
    rows = {}
    for (nz, c, p, dec) in sorted({k[:4] for k in agg}):
        if not all((nz, c, p, dec, b) in agg for b in "ZX"):
            continue
        draws = 0; row = {"noise": nz, "circ": c, "p": p, "dec": dec}
        for b in "ZX":
            a = agg[(nz, c, p, dec, b)]
            n = a["new"][0] + a["old"][0]; k = a["new"][1] + a["old"][1]
            P = rng.beta(k + 0.5, n - k + 0.5, NS)
            draws = draws + (1 - (1 - P) ** (1 / R))
            row[b] = dict(shots=n, errors=k, new=a["new"], old=a["old"], eps=1 - (1 - k / n) ** (1 / R))
        pt = row["Z"]["eps"] + row["X"]["eps"]
        lo, hi = np.quantile(draws, [0.025, 0.975])
        row.update(eps=pt, lo=float(lo), hi=float(hi), draws=draws)
        rows[(nz, c, p, dec)] = row
    out = []
    for key, r in sorted(rows.items(), key=lambda x: (x[0][0], x[0][3], -x[0][2], x[0][1])):
        nz, c, p, dec = key
        for num, den in (("u11", "ibm"), ("u11", "fig12"), ("fig12", "ibm")):
            if c != num or (nz, den, p, dec) not in rows:
                continue
            ref = rows[(nz, den, p, dec)]
            rr = r["draws"] / ref["draws"]
            pt = r["eps"] / ref["eps"] if ref["eps"] > 0 else None
            r[f"ratio_vs_{den}"] = [pt, float(np.quantile(rr, 0.025)), float(np.quantile(rr, 0.975))]
            f = PERIOD[den] / PERIOD[num]
            r[f"ratio_per_layer_vs_{den}"] = [pt * f if pt is not None else None, float(np.quantile(rr, 0.025)) * f,
                                              float(np.quantile(rr, 0.975)) * f]
        out.append({k: v for k, v in r.items() if k != "draws"})
    return out


def neutral_atom():
    PAIRS = {"gross": (("u11", "ibm"), ("u11", "fig12"), ("fig12", "ibm")), "bb90": (("c11", "ibm90"),)}
    ORDER = ("cur", "curx0.5", "proj", "cur_cz", "cur_par", "cur_slow", "proj_t2par", "cur_par_unp")
    agg = defaultdict(lambda: [0, 0, 0.0])
    meta = {}
    for s in read([str(D / "neutral_atom" / "main.csv"), str(D / "neutral_atom" / "sens.csv")]):
        m = s.json_metadata
        k = (m["fam"], m["model"], s.decoder, m["circ"], m["basis"])
        agg[k][0] += s.shots; agg[k][1] += s.errors; agg[k][2] += s.seconds
        meta[k[:4]] = m["R"]
    rng = np.random.default_rng(1)
    rows = {}
    for key, R in sorted(meta.items()):
        if not all(key + (b,) in agg for b in "ZX"):
            continue
        draws = 0.0
        r = {"R": R}
        for b in "ZX":
            n, k, sec = agg[key + (b,)]
            P = rng.beta(k + 0.5, n - k + 0.5, NS)
            draws = draws + (1 - (1 - P) ** (1 / R))
            r[b] = dict(shots=n, errors=k, cpu_s=sec)
        r["eps"] = sum(1 - (1 - r[b]["errors"] / r[b]["shots"]) ** (1 / R) for b in "ZX")
        r["lo"], r["hi"] = map(float, np.quantile(draws, [0.025, 0.975]))
        r["_d"] = draws
        rows[key] = r
    out = {"eps": [], "ratios": []}
    for key in sorted(rows, key=lambda k: (k[0], ORDER.index(k[1]), k[2], k[3])):
        r = rows[key]
        out["eps"].append(dict(fam=key[0], model=key[1], dec=key[2], circ=key[3], eps=r["eps"], lo=r["lo"],
                               hi=r["hi"], Z=r["Z"], X=r["X"]))
    for fam, pairs in PAIRS.items():
        for model in ORDER:
            for dec in ("bposd", "relay5"):
                for a, b in pairs:
                    ka, kb = (fam, model, dec, a), (fam, model, dec, b)
                    if ka not in rows or kb not in rows:
                        continue
                    ra, rb = rows[ka], rows[kb]
                    q = ra["_d"] / rb["_d"]
                    lo, hi = np.quantile(q, [0.025, 0.975])
                    pt = ra["eps"] / rb["eps"] if rb["eps"] > 0 else float("nan")
                    fa = ra["Z"]["errors"] + ra["X"]["errors"]; fb = rb["Z"]["errors"] + rb["X"]["errors"]
                    out["ratios"].append(dict(fam=fam, model=model, dec=dec, num=a, den=b, ratio=pt, lo=float(lo),
                                              hi=float(hi), p_lt1=float((q < 1).mean()), fails=[fa, fb]))
    return out


def same(a, b, tol=1e-12):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k], tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        if a is None or b is None:
            return a is b
        return abs(a - b) <= tol * max(1.0, abs(a), abs(b)) or (a != a and b != b)
    return a == b


def fmt(r):
    return f"{r[0]:.3g} [{r[1]:.3g}, {r[2]:.3g}]"


def verify_circuits(n_per_set, V):
    """rebuild sampled tasks with the package code and compare sinter's strong_id (needs sinter)."""
    import sinter
    import stim
    from ler import circuits as LC, noise as LN, na_noise as NA
    sets = [("sd6_lambda_bb90", "bb90", sorted(glob.glob(str(D / "sd6_lambda_bb90" / "*.csv")))),
            ("sd6_lambda_gross", "gross", sorted(glob.glob(str(D / "sd6_lambda_gross" / "*.csv")) +
                                                 glob.glob(str(D / "sd6_lambda_gross" / "earlier" / "*.csv")))),
            ("neutral_atom", None, [str(D / "neutral_atom" / "main.csv"), str(D / "neutral_atom" / "sens.csv")])]
    for tag, fam, files in sets:
        tasks = {}
        for s in read(files):
            tasks.setdefault((s.strong_id, s.decoder), s.json_metadata)
        keys = sorted(tasks)
        if n_per_set:
            keys = keys[:: max(1, len(keys) // n_per_set)][:n_per_set]
        ok = 0
        for sid, dec in keys:
            m = tasks[(sid, dec)]
            if tag == "neutral_atom":
                f = m["fam"]
                nl = LC.noiseless(f, m["circ"], m["basis"], m["R"])
                l_, mm = LC.GRID[f]
                cd = LC.code(f)
                circ = NA.apply(nl, NA.get_params(m["model"]), NA.Roles(cd.n, cd.HX.shape[0], cd.HZ.shape[0], l_, mm))
                md = dict(circ=m["circ"], basis=m["basis"], R=m["R"], model=m["model"], fam=m["fam"])
            else:
                nl = LC.noiseless(fam, m["circ"], m["basis"], m["R"])
                circ = LN.noisy_from(nl, "lam1" if m["noise"] == "sd6" else m["noise"], m["p"])
                md = dict(circ=m["circ"], basis=m["basis"], p=m["p"], R=m["R"], noise=m["noise"])
            # sinter sends the circuit to its workers as text: the sampled circuit is the text round trip (the
            # probabilities of the neutral-atom dephasing channels are printed with finite precision)
            circ = stim.Circuit(str(circ))
            try:
                dem = circ.detector_error_model(decompose_errors=True, approximate_disjoint_errors=True)
            except ValueError:
                dem = circ.detector_error_model(approximate_disjoint_errors=True)
            t = sinter.Task(circuit=circ, decoder=dec, detector_error_model=dem, json_metadata=md)
            ok += t.strong_id() == sid
        V(ok == len(keys), f"[{tag}] {ok}/{len(keys)} sampled tasks rebuilt from data/circuits with the package template "
                           f"and noise model have the recorded sinter strong_id (identical circuit, DEM, decoder)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-circuits", type=int, default=None)
    a = ap.parse_args()
    V = Verdict()
    b90 = sd6_bb90()
    ref = json.load(open(D / "sd6_lambda_bb90" / "summary.json"))
    V(same(b90, ref["rows"]), f"[sd6_lambda_bb90] {len(b90)} rows recomputed = summary.json")
    gr = sd6_gross()
    ref = json.load(open(D / "sd6_lambda_gross" / "summary.json"))
    V(same(gr, ref["rows"]), f"[sd6_lambda_gross] {len(gr)} rows recomputed = summary.json")
    na = neutral_atom()
    ref = json.load(open(D / "neutral_atom" / "summary.json"))
    V(same(na, ref), f"[neutral_atom] {len(na['eps'])} rates and {len(na['ratios'])} ratios recomputed = summary.json")
    # the paper's headline numbers (SM S7, S8)
    g = {(r["noise"], r["circ"], r["p"], r["dec"]): r for r in b90}
    h = {(r["noise"], r["circ"], r["p"], r["dec"]): r for r in gr}
    print("SM S7, [[90,8,10]] c11 / IBM, per round (this pipeline):")
    for nz in ("lam0", "lam0.1", "lam1"):
        for dec in ("bposd", "relay5"):
            s = [f"p={p:g}: {fmt(g[(nz, 'c11', p, dec)]['ratio_vs_ibm'])}" for p in (0.002, 0.003, 0.004, 0.005)
                 if (nz, "c11", p, dec) in g and "ratio_vs_ibm" in g[(nz, "c11", p, dec)]]
            print(f"  {nz:6s} {dec:6s} " + "; ".join(s))
    print("SM S7, gross u11 / Fig. 12 and u11 / IBM, per round (this pipeline, pooled with the earlier sampling):")
    for nz in ("lam0", "lam0.1", "lam1"):
        for dec in ("bposd", "relay5"):
            for den in ("fig12", "ibm"):
                s = [f"p={p:g}: {fmt(h[(nz, 'u11', p, dec)]['ratio_vs_' + den])}" for p in (0.002, 0.003, 0.004, 0.005)
                     if (nz, "u11", p, dec) in h and ("ratio_vs_" + den) in h[(nz, "u11", p, dec)]
                     and h[(nz, "u11", p, dec)]["ratio_vs_" + den][0] is not None]
                if s:
                    print(f"  {nz:6s} {dec:6s} u11/{den:5s} " + "; ".join(s))
    print("SM S8 (Table of ratios), period-11 circuit / IBM's depth-8 circuit:")
    for r in na["ratios"]:
        if r["den"] in ("ibm", "ibm90") and r["num"] in ("u11", "c11"):
            print(f"  {r['fam']:5s} {r['model']:12s} {r['dec']:6s} {r['ratio']:.2f} [{r['lo']:.2f}, {r['hi']:.2f}]  "
                  f"failures {r['fails'][0]} / {r['fails'][1]}")
    # independent pipeline and pooled values
    ind = D / "independent_resampling"
    pr = []
    for fam, f, rows_, key, num in (("bb90", "bb90_sd6_lambda", g, ("lam0", "c11", 0.003, "bposd"), "ratio"),
                                    ("gross", "gross_sd6_lambda", h, ("lam0", "u11", 0.003, "bposd"), "u11/ibm")):
        S = json.load(open(ind / f"{f}_summary.json"))
        c2 = S["counts"]
        R = 10 if fam == "bb90" else 12
        cn, cd = key[1], "ibm"
        eps = {}
        for c in (cn, cd):
            r1 = rows_[(key[0], c, key[2], key[3])]
            eps[c] = sum(1 - (1 - (r1[x]["errors"] + c2[f"{c}_{x}"][1]) / (r1[x]["shots"] + c2[f"{c}_{x}"][0])) ** (1 / R)
                         for x in "ZX")
        pooled = eps[cn] / eps[cd]
        rec = S["pooled_with_first_pipeline"][num]
        pr.append(abs(pooled - rec[0]) < 1e-9)
        print(f"SM S7, {cn} / IBM at lambda = 0, p = 3e-3, BP-OSD: second, independent pipeline "
              f"{fmt(S['second_pipeline'][num])}; pooled over both pipelines {fmt(rec)} (point estimate recomputed "
              f"from the counts: {pooled:.4g})")
    na2 = json.load(open(ind / "neutral_atom_summary.json"))
    for x in na2:
        print(f"SM S8, second pipeline: {x['model']} {x['pair']} BP-OSD {x['ratio']:.3f} [{x['lo']:.3f}, {x['hi']:.3f}]")
    V(all(pr), "pooled point estimates (both pipelines) recomputed from the per-basis counts = the recorded values")
    if a.verify_circuits is not None:
        verify_circuits(a.verify_circuits, V)
    V.exit()


if __name__ == "__main__":
    main()
