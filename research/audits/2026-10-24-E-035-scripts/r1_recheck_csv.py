"""Auditor E-035 r1: re-aggregate the experimenter's raw sinter csvs with the csv module (no sinter / analyze.py),
check that every main task has exactly the pre-registered N shots (shots.json at commit bd030c5), that no sens task
exceeds N, recompute per-round eps and Jeffreys 95% ratio intervals (own MC, seed 7, 200000 draws), and the
per-strong_id row structure (each strong_id must map to one json_metadata; no duplicated task under 2 files).
    uv run python research/audits/2026-10-24-E-035-scripts/r1_recheck_csv.py"""
import csv, json, subprocess
from collections import defaultdict
import numpy as np

ROOT = "/Users/ephemeral/Desktop/qec-ai-search/"
D = ROOT + "results/E-035-neutral-atom-ler/direct/"
shots = json.loads(subprocess.check_output(["git", "-C", ROOT, "show", "bd030c5:search/experiments/e035/shots.json"]))

agg = defaultdict(lambda: [0, 0, 0.0])
sid = defaultdict(set)
for f in ("main.csv", "sens.csv"):
    with open(D + f) as fh:
        rd = csv.reader(fh)
        hdr = [h.strip() for h in next(rd)]
        for row in rd:
            r = dict(zip(hdr, [x.strip() for x in row]))
            m = json.loads(r["json_metadata"])
            k = (f, m["fam"], m["model"], r["decoder"], m["circ"], m["basis"], m["R"])
            agg[k][0] += int(r["shots"]); agg[k][1] += int(r["errors"]); agg[k][2] += float(r["seconds"])
            assert int(r["discards"]) == 0
            sid[r["strong_id"]].add((f,) + k[1:])
assert all(len(v) == 1 for v in sid.values()), "strong_id maps to several tasks/files"
bad = []
for k, (n, e, s) in sorted(agg.items()):
    N = shots[f"{k[1]}|{k[2]}|{k[3]}"]["N"]
    if k[0] == "main.csv" and n != N:
        bad.append((k, n, N))
    if k[0] == "sens.csv" and n > N:
        bad.append((k, n, N))
print("tasks", len(agg), "shot-count violations:", bad)
tot = defaultdict(float)
for k, v in agg.items():
    tot[k[0]] += v[2]
print("sinter seconds (h):", {f: round(s / 3600, 2) for f, s in tot.items()})

rng = np.random.default_rng(7)
NS = 200000
def draws(fam, model, dec, circ):
    out, pt, info = 0.0, 0.0, []
    for b in "ZX":
        ks = [k for k in agg if k[1:6] == (fam, model, dec, circ, b)]
        assert len(ks) == 1, (fam, model, dec, circ, b, ks)
        n, e, _ = agg[ks[0]]; R = ks[0][6]
        P = rng.beta(e + 0.5, n - e + 0.5, NS)
        out = out + (1 - (1 - P) ** (1 / R)); pt += 1 - (1 - e / n) ** (1 / R); info.append(f"{e}/{n}")
    return out, pt, info

res = []
pairs = {"gross": [("u11", "ibm"), ("u11", "fig12")], "bb90": [("c11", "ibm90")]}
models = ("cur", "curx0.5", "proj", "cur_cz", "cur_par", "cur_slow", "proj_t2par", "cur_par_unp")
for fam, prs in pairs.items():
    for model in models:
        for dec in ("bposd", "relay5"):
            for a, b in prs:
                try:
                    da, pa, ia = draws(fam, model, dec, a); db, pb, ib = draws(fam, model, dec, b)
                except AssertionError:
                    continue
                q = da / db
                lo, hi = np.quantile(q, [0.025, 0.975])
                res.append(dict(fam=fam, model=model, dec=dec, pair=f"{a}/{b}", ratio=pa / pb, lo=lo, hi=hi,
                                num=ia, den=ib))
                print(f"{fam:5s} {model:11s} {dec:6s} {a}/{b:6s} {pa/pb:.3f} [{lo:.3f}, {hi:.3f}]  {ia} vs {ib}")
json.dump(dict(violations=[str(b) for b in bad], ratios=res), open(ROOT + "results/E-035-audit/r1_recheck.json", "w"),
          indent=1, default=float)
