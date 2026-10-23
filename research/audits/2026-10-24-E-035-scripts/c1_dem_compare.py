"""Auditor E-035 c1: own NA circuit (na_mine) vs the experimenter's na_noisy (evaluator template + na_noise).
For 5 circuits x 2 bases x models at the sampled R: DEM columns keyed by detector set (XOR-merged prior): set equality,
max relative prior difference, observable map existence (one invertible GF(2) map).  Also own per-round quantities
(R vs R-1): fault mass, move/readout counts, time, Rydberg pulses, unpaired exposures (two definitions), and a
translation-invariance check (each (type, monomial) group occurs in exactly one layer per period).
  PYTHONPATH=.:tests uv run python research/audits/2026-10-24-E-035-scripts/c1_dem_compare.py [models]"""
import sys, json
sys.path[:0] = ["/Users/ephemeral/Desktop/qec-ai-search", "/Users/ephemeral/Desktop/qec-ai-search/tests",
                "/Users/ephemeral/Desktop/qec-ai-search/research/audits/2026-10-24-E-035-scripts"]
from collections import defaultdict
import numpy as np
import na_mine as nm

ROOT = "/Users/ephemeral/Desktop/qec-ai-search/"


def cols(c):
    out = {}
    for ins in c.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True).flattened():
        if ins.type != "error":
            continue
        ds = frozenset(t.val for t in ins.targets_copy() if t.is_relative_detector_id())
        ob = 0
        for t in ins.targets_copy():
            if t.is_logical_observable_id():
                ob ^= 1 << t.val
        pr = ins.args_copy()[0]
        if ds in out:
            q, o = out[ds]
            out[ds] = (q * (1 - pr) + pr * (1 - q), o if o == ob else None)
        else:
            out[ds] = (pr, ob)
    return out


def mass(c):
    return sum(i.args_copy()[0] for i in c.detector_error_model(decompose_errors=False,
               approximate_disjoint_errors=True).flattened() if i.type == "error")


def gf2_map_exists(pairs, k):
    lib = nm.LIB["gross"]
    A = np.array([[(a >> i) & 1 for i in range(k)] for a, b in pairs], np.uint8)
    B = np.array([[(b >> i) & 1 for i in range(k)] for a, b in pairs], np.uint8)
    _, piv = lib.rref(np.concatenate([A, B], 1))
    return (not any(p >= k for p in piv)), lib.rank(A)


def ti_check(name):
    fam, d = nm.spec(name)
    lib = nm.LIB[fam]
    P = d["period"]
    where = defaultdict(set)
    for typ, key, q0 in (("X", "x_checks", lib.QX0), ("Z", "z_checks", lib.QZ0)):
        for i, ch in enumerate(d[key]):
            for col, t in ch["cnots"]:
                where[nm.group_of(lib, typ, i, col)].add(t % P)
    return dict(n_groups=len(where), groups_single_layer=all(len(v) == 1 for v in where.values()),
                max_layers_per_group=max(len(v) for v in where.values()))


def main():
    from search.experiments.e035.common import na_noisy
    models = sys.argv[1].split(",") if len(sys.argv) > 1 else ["cur", "proj", "curx0.5", "cur_par", "cur_slow",
                                                               "proj_t2par", "cur_par_unp", "cur_cz"]
    res = {"dem": [], "per_round": {}, "ti": {}}
    for name in ("u11", "ibm", "fig12", "c11", "ibm90"):
        fam, _ = nm.spec(name)
        R = nm.RNDS[fam]
        k = 12 if fam == "gross" else 8
        res["ti"][name] = ti_check(name)
        print(name, res["ti"][name], flush=True)
        for model in models:
            for b in "ZX":
                mine, _ = nm.build(name, b, R, model)
                theirs = na_noisy(name, b, R, model)
                assert mine.num_detectors == theirs.num_detectors
                cm, ct = cols(mine), cols(theirs)
                same = set(cm) == set(ct)
                rel = max(abs(cm[x][0] - ct[x][0]) / ct[x][0] for x in ct) if same else None
                pairs = [(ct[x][1], cm[x][1]) for x in ct if same and ct[x][1] is not None and cm[x][1] is not None]
                okT, rk = gf2_map_exists(pairs, k) if same else (False, None)
                r = dict(circ=name, model=model, basis=b, ndet=mine.num_detectors, ncols=len(cm), same_cols=same,
                         max_rel=rel, obs_map=okT, obs_rank=int(rk) if rk is not None else None)
                print(r, flush=True)
                res["dem"].append(r)
        # per-round own quantities
        pr = {}
        for model in ("cur", "cur_par", "proj", "proj_t2par", "cur_slow", "cur_par_unp", "cur_unp"):
            row = {}
            for b in "ZX":
                c2, s2 = nm.build(name, b, R, model)
                c1, s1 = nm.build(name, b, R - 1, model)
                row["mass_" + b] = mass(c2) - mass(c1)
                if b == "Z":
                    for key in ("moves", "readouts", "pulses_par", "pulses", "unp", "unp_probe", "time_move",
                                "time_wait"):
                        row[key] = s2[key] - s1[key]
            pr[model] = row
            print(name, model, {k_: (round(v, 4) if isinstance(v, float) else v) for k_, v in row.items()}, flush=True)
        res["per_round"][name] = pr
    json.dump(res, open(ROOT + "results/E-035-audit/c1_dem_compare" + (("_" + sys.argv[1].replace(",", "_")) if len(sys.argv) > 1 else "") + ".json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
