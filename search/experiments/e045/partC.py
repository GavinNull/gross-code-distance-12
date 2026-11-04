"""E-045 Part C: does any wrapping single-ancilla circuit have circuit distance INCREASING with R?  experimenter.

Exact minimum weight of the evaluator's SD6 DEM (add_noise(memory_circuit(spec, basis, R), "sd6")) at small R, by the
E-043 auditor's DEM builder (search/experiments/e043_audit/direct.py: terms -> columns, the 72 / 45 / 36 check
translations verified term by term with a linear observable action) and the E-032/E-040 auditors' mitmsearch.c
(compiled here into results/E-045-crocker/partC/).  "No solution of weight <= W" <=> d_circ(R) > W (a minimum-weight
undetectable logical has no proper zero-syndrome subset).  min weight = smallest W at which a solution is found,
with "none at W - 1" proven in the same sweep.

Window conditions (Wb)/(Wt) from search/theory/B/window.py logic (theory B audit's window_test.conds).

    uv run python -m search.experiments.e045.partC dmin ctl_p10 X 1 4 9 11      # d(R) for R = 1..4, W from 9 to 11
    uv run python -m search.experiments.e045.partC random bb72 200 20261104       # random wrapping schedules
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
import time
from pathlib import Path

from search.experiments.e043_audit import common as c43
from search.experiments.e043_audit import direct as d43

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results" / "E-045-crocker" / "partC"
OUT.mkdir(parents=True, exist_ok=True)
SRC = ROOT / "search/experiments/e040_audit_circ/mitmsearch.c"

SPECS = {
    "ctl_p10": ("gross", "search/experiments/e032/ctl_p10_spec.json"),
    "fig12": ("gross", "search/experiments/e033/fig12_gross_spec.json"),
    "p18w": ("gross", "search/experiments/e024b/p18w_spec.json"),
    "u16": ("bb90", "search/experiments/e028/u16_spec.json"),
    "ibm90": ("bb90", "search/experiments/e030/ibm90_spec.json"),
}
for k, (c, p) in SPECS.items():
    c43.CIRCS.setdefault(k, (c, p, 0))       # runtime registration only (no file of E-043's is changed)


def exe(nw):
    nw = {1: 2, 2: 2, 3: 4, 4: 4, 5: 5, 6: 6}[nw]
    b = OUT / f"mitm_nw{nw}"
    if not b.exists():
        subprocess.run(["cc", "-O3", "-march=native", f"-DNW={nw}", "-o", str(b), str(SRC)], check=True)
    return b


def search(name, basis, R, W, cache={}):
    key = (name, basis, R)
    if key not in cache:
        keys, errs, nd, K, colperm = d43.build(name, basis, R)
        orb = [-1] * len(keys)
        reps = []
        for j in range(len(keys)):
            if orb[j] < 0:
                for pm in colperm:
                    orb[pm[j]] = len(reps)
                reps.append(j)
        lines = [f"{len(keys)} {nd}"]
        for k in keys:
            lines.append(f"{len(k)} {' '.join(map(str, sorted(k)))} {len(errs[k])} {' '.join(map(str, sorted(errs[k])))}")
        lines += [str(len(reps)), " ".join(map(str, orb)), " ".join(map(str, reps))]
        inp = OUT / f"dem_{name}_{basis}_R{R}.txt"
        inp.write_text("\n".join(lines) + "\n")
        cache[key] = (keys, errs, nd, inp, len(colperm), len(reps))
    keys, errs, nd, inp, ng, nrep = cache[key]
    t = time.time()
    p = subprocess.run([str(exe(-(-nd // 64))), str(W), "decide", "2"], stdin=open(inp), capture_output=True, text=True)
    sols = [list(map(int, l.split()[2:])) for l in p.stdout.splitlines() if l.startswith("SOL")]
    done = [l for l in p.stderr.splitlines() if l.startswith("DONE")]
    assert done, p.stderr[-500:]
    rec = dict(spec=name, basis=basis, R=R, W=W, terms=len(keys), detectors=nd, translations=ng, orbits=nrep,
               found=bool(sols), sec=round(time.time() - t, 1), done=done[-1])
    if sols:
        s = sols[0]
        dd, oo = set(), set()
        for j in s:
            dd ^= set(keys[j]); oo ^= set(errs[keys[j]])
        assert not dd and oo and len(set(s)) == len(s)
        rec["weight"] = len(s)
        rec["witness_terms"] = [[sorted(keys[j]), sorted(errs[keys[j]])] for j in s]
    with open(OUT / "dmin.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def dmin(name, basis, R, wlo, whi):
    """smallest W in [wlo, whi] with a solution (None if none up to whi); requires 'none at wlo - 1' separately"""
    for W in range(wlo, whi + 1):
        r = search(name, basis, R, W)
        if r["found"]:
            return r["weight"], W
    return None, whi


def main_dmin(a):
    name, basis, R0, R1, wlo, whi = a[0], a[1], int(a[2]), int(a[3]), int(a[4]), int(a[5])
    res = []
    for R in range(R0, R1 + 1):
        w, W = dmin(name, basis, R, wlo, whi)
        rec = dict(spec=name, basis=basis, R=R, dmin=w, none_below=wlo, searched_to=W)
        print(json.dumps(rec), flush=True)
        res.append(rec)
    with open(OUT / "dmin_summary.jsonl", "a") as f:
        for r in res:
            f.write(json.dumps(r) + "\n")


def random_spec(rng, code_name):
    """random translation-invariant single-ancilla schedule (any term order, wrapping allowed), legal and
    deterministic; same construction as the theory-B auditor's random_u11_class but with random term orders"""
    from evaluators import candidate as cand
    from search.theory.B_audit.common import Bulk, get_code
    from search.theory.B_audit.delta import analyse
    from search.theory.B_audit.template_check import build
    code = get_code(code_name)
    labs = ["A1", "A2", "A3", "B1", "B2", "B3"]
    for _ in range(100000):
        P = rng.randint(8, 12)

        def one():
            order = labs[:]
            rng.shuffle(order)
            span = rng.randint(7, P - 1)
            offs = sorted(rng.sample(range(1, span), 6))
            p = rng.randrange(P)
            return order, (p, (p + span) % P, {k: (p + o) % P for k, o in zip(order, offs)})
        xo, X = one()
        zo, Z = one()
        T = dict(P=P, X=X, Z=Z)
        Pp, xs, zs = build(code_name, T)
        spec = {"format": "qec-schedule/v1", "period": Pp,
                "x_checks": [{"prep": p, "meas": m, "cnots": sorted(map(list, c))} for p, m, c in xs],
                "z_checks": [{"prep": p, "meas": m, "cnots": sorted(map(list, c))} for p, m, c in zs]}
        if cand.validate_schedule(cand.parse_schedule(spec), code):
            continue
        if analyse(Bulk(spec, code, "Z"))["pairing_violations"]:
            continue
        return dict(P=P, xo=xo, zo=zo, X=[X[0], X[1], X[2]], Z=[Z[0], Z[1], Z[2]]), spec
    raise RuntimeError


def main_random(a):
    """random schedules; keep the ones with (Wb) and (Wt) both failing in some basis, plus a few controls; exact
    minimum weight for R = 1..Rmax"""
    from search.theory.B_audit.common import get_code
    from search.theory.B_audit.window_test import conds
    code_name, n, seed = a[0], int(a[1]), int(a[2])
    Rmax = int(a[3]) if len(a) > 3 else 4
    dmax = {"bb72": 6, "bb90": 10, "gross": 12}[code_name]
    rng = random.Random(seed)
    code = get_code(code_name)
    sp_dir = OUT / "specs"
    sp_dir.mkdir(exist_ok=True)
    tally = {}
    for i in range(n):
        T, spec = random_spec(rng, code_name)
        cd = conds(code, spec, Rmax=1)
        for basis in ("Z", "X"):
            wb, wt = cd[f"R1{basis}"]["Wb"], cd[f"R1{basis}"]["Wt"]
            cls = ("Wb" if wb else "noWb") + "_" + ("Wt" if wt else "noWt")
            tally[cls] = tally.get(cls, 0) + 1
            # all both-failing instances; every 5th of the others as controls
            if wb or wt:
                if i % 5:
                    continue
            name = f"rnd{seed}_{i}"
            path = sp_dir / f"{name}.json"
            path.write_text(json.dumps(spec))
            c43.CIRCS[name] = (code_name, str(path.relative_to(ROOT)), 0)
            ds = []
            for R in range(1, Rmax + 1):
                w, _ = dmin(name, basis, R, 1, dmax)
                ds.append(w)
            inc = any(ds[k + 1] is not None and ds[k] is not None and ds[k + 1] > ds[k] for k in range(len(ds) - 1))
            rec = dict(i=i, name=name, basis=basis, cls=cls, T=T, d=ds, increases=inc)
            print(json.dumps(rec), flush=True)
            with open(OUT / f"random_{code_name}_{seed}.jsonl", "a") as f:
                f.write(json.dumps(rec) + "\n")
    print(json.dumps({"tally": tally}), flush=True)


if __name__ == "__main__" and sys.argv[1] in ("dmin", "random"):
    {"dmin": main_dmin, "random": main_random}[sys.argv[1]](sys.argv[2:])


# ------------------------------------------------------------------------------------------------ DEM inclusion
def terms_coords(name, basis, R):
    """set of (frozenset of (check, round) detector coords, frozenset of observables) of the evaluator's SD6 DEM"""
    from evaluators import candidate as cand
    from evaluators.noise import add_noise
    cname = c43.info(name)[0]
    code = c43.code_of(cname)
    circ = add_noise(cand.memory_circuit(cand.parse_schedule(c43.load(name)), code, basis, R), "sd6", 1e-3)
    co = circ.get_detector_coordinates()
    dem = circ.detector_error_model(approximate_disjoint_errors=True, flatten_loops=True)
    out = set()
    for e in dem.flattened():
        if e.type != "error":
            continue
        ds, os_ = set(), set()
        for t in e.targets_copy():
            if t.is_relative_detector_id():
                ds ^= {t.val}
            elif t.is_logical_observable_id():
                os_ ^= {t.val}
        if ds or os_:
            out.add((frozenset((int(co[x][0]), int(co[x][1])) for x in ds), frozenset(os_)))
    return out


def inclusion(name, basis, Rs):
    """in place: DEM(R) subset of DEM(R+1) (same coords);  late: every term shifted one round later (round + 1)
    is a term of DEM(R+1)"""
    from search.theory.B_audit.common import get_code
    from search.theory.B_audit.window_test import conds
    cd = conds(get_code(c43.info(name)[0]), c43.load(name), Rmax=1)[f"R1{basis}"]
    rows = []
    prev = None
    for R in list(Rs) + [max(Rs) + 1]:
        cur = terms_coords(name, basis, R)
        if prev is not None:
            inplace = len(prev - cur)
            late = len({(frozenset((i, j + 1) for i, j in d), o) for d, o in prev} - cur)
            rows.append(dict(R=R - 1, missing_inplace=inplace, missing_late=late))
        prev = cur
    rec = dict(spec=name, basis=basis, Wb=cd["Wb"], Wt=cd["Wt"], rows=rows)
    print(json.dumps(rec), flush=True)
    with open(OUT / "inclusion.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def main_incl(a):
    name = a[0]
    Rs = range(1, int(a[1]) + 1)
    for basis in ("Z", "X"):
        inclusion(name, basis, Rs)


if __name__ == "__main__" and sys.argv[1] == "incl":
    main_incl(sys.argv[2:])


def main_rand_incl(a):
    """random translation-invariant schedules: tally of window classes per basis (many), DEM inclusion R -> R+1
    (in place and one period late) for R = 1..Rmax on every k-th one"""
    from search.theory.B_audit.common import get_code
    from search.theory.B_audit.window_test import conds
    code_name, n, seed, every, Rmax = a[0], int(a[1]), int(a[2]), int(a[3]), int(a[4])
    rng = random.Random(seed)
    code = get_code(code_name)
    sp_dir = OUT / "specs"
    sp_dir.mkdir(exist_ok=True)
    tally = {}
    for i in range(n):
        T, spec = random_spec(rng, code_name)
        cd = conds(code, spec, Rmax=1)
        cls = {b: ("Wb" if cd[f"R1{b}"]["Wb"] else "noWb") + "_" + ("Wt" if cd[f"R1{b}"]["Wt"] else "noWt")
               for b in ("Z", "X")}
        for b in ("Z", "X"):
            tally[cls[b]] = tally.get(cls[b], 0) + 1
        if i % every == 0 or "noWb_noWt" in cls.values():
            name = f"ri{seed}_{i}"
            path = sp_dir / f"{name}.json"
            path.write_text(json.dumps(spec))
            c43.CIRCS[name] = (code_name, str(path.relative_to(ROOT)), 0)
            for b in ("Z", "X"):
                r = inclusion(name, b, range(1, Rmax + 1))
                ok_in = all(x["missing_inplace"] == 0 for x in r["rows"])
                ok_late = all(x["missing_late"] == 0 for x in r["rows"])
                with open(OUT / f"rand_incl_{code_name}_{seed}.jsonl", "a") as f:
                    f.write(json.dumps(dict(i=i, name=name, basis=b, cls=cls[b], T=T, inplace_ok=ok_in,
                                            late_ok=ok_late)) + "\n")
    print(json.dumps({"tally": tally}), flush=True)
    with open(OUT / f"rand_incl_{code_name}_{seed}.jsonl", "a") as f:
        f.write(json.dumps({"tally": tally, "n": n}) + "\n")


if __name__ == "__main__" and sys.argv[1] == "randincl":
    main_rand_incl(sys.argv[2:])
