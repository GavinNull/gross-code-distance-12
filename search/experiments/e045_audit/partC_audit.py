"""E-045 audit, Part C: window conditions, "two starts" lemma, in-place / one-period-late DEM inclusion.  auditor.

Own code (no import of search/experiments/e045).  Uses the evaluator's PUBLIC entries (parse_schedule, validate_schedule,
unroll, memory_circuit, add_noise) and, to build random translation-invariant schedules from a template, the audited
theory-B auditor helper search/theory/B_audit/template_check.build.

  windows: from U = unroll(spec, code, R): reads of reader instance 0 at start[a] + off; (Wb) all reads - P <= 0;
           (Wt) all reads + P R > U.num_layers - 1.  Reported with the distinct start values per check type.
  inclusion: SD6 DEM (approximate_disjoint_errors) terms as (frozenset of detector coords (i, round, type), obs);
           in place: T(R) subset T(R+1); late: shift every detector round by +1, subset T(R+1).

  uv run python -m search.experiments.e045_audit.partC_audit project 3
  uv run python -m search.experiments.e045_audit.partC_audit random bb72 300 7701 3
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from evaluators import candidate as cand  # noqa: E402
from evaluators.noise import add_noise  # noqa: E402

OUT = ROOT / "results/E-045-audit/partC"


def get_code(name):
    from evaluators.tasks import build_code, get_task
    return build_code(get_task({"gross": "gross-dcirc", "bb90": "bb90-dcirc", "bb72": "bb72-dcirc"}[name]), None)[0]


def windows(spec, code, R=1):
    U = cand.unroll(spec, code, R)
    lay = cand.layout_for(code)
    P = spec.period
    last = U.num_layers - 1
    out = {}
    starts = {"X": sorted({U.start[a] for a in lay.x_anc}), "Z": sorted({U.start[a] for a in lay.z_anc})}
    for basis in ("Z", "X"):
        rd = (spec.z_checks, lay.z_anc) if basis == "Z" else (spec.x_checks, lay.x_anc)
        reads = [U.start[a] + o for c, a in zip(*rd) for o, _ in c.offsets(P)[1]]
        out[basis] = dict(Wb=all(r - P <= 0 for r in reads), Wt=all(r + P * R > last for r in reads))
    out["starts"] = starts
    out["min_start"] = min(U.start.values())
    return out


def terms(spec, code, basis, R):
    circ = add_noise(cand.memory_circuit(spec, code, basis, R), "sd6", 1e-3)
    co = circ.get_detector_coordinates()
    dem = circ.detector_error_model(approximate_disjoint_errors=True)
    out = set()
    for e in dem.flattened():
        if e.type != "error":
            continue
        d, o = set(), set()
        for t in e.targets_copy():
            if t.is_relative_detector_id():
                d ^= {t.val}
            elif t.is_logical_observable_id():
                o ^= {t.val}
        if d or o:
            out.add((frozenset(tuple(int(x) for x in co[k]) for k in d), frozenset(o)))
    return out


def inclusion(spec, code, basis, Rmax):
    rows = []
    prev = terms(spec, code, basis, 1)
    for R in range(1, Rmax + 1):
        cur = terms(spec, code, basis, R + 1)
        inpl = len(prev - cur)
        late = len({(frozenset((i, r + 1, ty) for i, r, ty in d), o) for d, o in prev} - cur)
        rows.append(dict(R=R, miss_inplace=inpl, miss_late=late))
        prev = cur
    return rows


PROJECT = {"ctl_p10": ("gross", "search/experiments/e032/ctl_p10_spec.json"),
           "fig12": ("gross", "search/experiments/e033/fig12_gross_spec.json"),
           "p18w": ("gross", "search/experiments/e024b/p18w_spec.json"),
           "u11": ("gross", "search/experiments/e032/u11_spec.json"),
           "ibm90": ("bb90", "search/experiments/e030/ibm90_spec.json")}


def project(Rmax):
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (cn, path) in PROJECT.items():
        code = get_code(cn)
        spec = cand.parse_schedule(json.loads((ROOT / path).read_text()))
        w = windows(spec, code)
        rec = dict(spec=name, windows=w)
        for b in ("Z", "X"):
            rec[b] = inclusion(spec, code, b, Rmax)
        print(json.dumps(rec), flush=True)
        with open(OUT / "project.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")


def random_template(rng, P):
    labs = ["A1", "A2", "A3", "B1", "B2", "B3"]

    def one():
        span = rng.randint(7, P - 1)
        offs = sorted(rng.sample(range(1, span), 6))
        order = labs[:]
        rng.shuffle(order)
        p = rng.randrange(P)
        return (p, (p + span) % P, {k: (p + o) % P for k, o in zip(order, offs)})
    return dict(P=P, X=one(), Z=one())


def deterministic(spec, code):
    import stim
    try:
        for b in ("Z", "X"):
            cand.memory_circuit(spec, code, b, 2).detector_error_model()
        return True
    except (ValueError, stim.Error if hasattr(stim, "Error") else ValueError):
        return False
    except Exception:
        return False


def rand(code_name, n, seed, Rmax):
    from search.theory.B_audit.template_check import build
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    code = get_code(code_name)
    tally, viol, incl_bad, ndone = {}, 0, [], 0
    tries = 0
    while ndone < n:
        tries += 1
        T = random_template(rng, rng.randint(8, 12))
        Pp, xs, zs = build(code_name, T)
        d = {"format": "qec-schedule/v1", "period": Pp,
             "x_checks": [{"prep": p, "meas": m, "cnots": sorted(map(list, c))} for p, m, c in xs],
             "z_checks": [{"prep": p, "meas": m, "cnots": sorted(map(list, c))} for p, m, c in zs]}
        try:
            spec = cand.parse_schedule(d)
        except Exception:
            continue
        if cand.validate_schedule(spec, code) or not deterministic(spec, code):
            continue
        ndone += 1
        w = windows(spec, code)
        w3 = windows(spec, code, 3)
        assert all(w[b] == w3[b] for b in ("Z", "X")), "window conditions depend on R"
        assert len(w["starts"]["X"]) == 1 and len(w["starts"]["Z"]) == 1
        assert w["min_start"] == 0
        rec = dict(i=ndone, T=T, windows=w)
        for b in ("Z", "X"):
            cls = ("Wb" if w[b]["Wb"] else "noWb") + "_" + ("Wt" if w[b]["Wt"] else "noWt")
            tally[cls] = tally.get(cls, 0) + 1
            if cls == "noWb_noWt":
                viol += 1
            rows = inclusion(spec, code, b, Rmax)
            rec[b] = rows
            # theory: Wt => in place; Wb => late
            for r in rows:
                if (w[b]["Wt"] and r["miss_inplace"]) or (w[b]["Wb"] and r["miss_late"]):
                    incl_bad.append((ndone, b, r))
            rec[b + "_any_inplace_fail"] = any(r["miss_inplace"] for r in rows)
            rec[b + "_any_late_fail"] = any(r["miss_late"] for r in rows)
        with open(OUT / f"random_{code_name}_{seed}.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
    summ = dict(code=code_name, n=n, tries=tries, seed=seed, tally=tally, both_fail=viol, theory_violations=incl_bad)
    print(json.dumps(summ), flush=True)
    with open(OUT / f"random_{code_name}_{seed}.jsonl", "a") as f:
        f.write(json.dumps(dict(summary=summ)) + "\n")


if __name__ == "__main__":
    if sys.argv[1] == "project":
        project(int(sys.argv[2]))
    else:
        rand(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
