"""E-043 certification toolkit for a translation-invariant BB schedule (any of bb90 / gross), built only on the
audited theory-B auditor code (search/theory/B_audit: Bulk step model, bulk columns, CP-SAT bulk lift, window
conditions, DEM-vs-model check, translations) and the E-032/E-040 auditors' mitmsearch.c (compiled into
results/E-043-table).  Generalises search/experiments/e040_audit_circ/{legal,lists,lift_run,direct}.py (which are
hard-wired to gross) to a code argument.  Nothing from search/experiments/e040 is imported here.

Subcommands (code = bb90 | gross; spec = path of a qec-schedule/v1 json):
  legal  code spec              evaluator validate_schedule, noiseless determinism, T(P) membership (times, span,
                                distinct mod P on data, determinism floors), strict translation invariance,
                                window conditions R = 1..3, zero-image hooks, model == SD6 DEM signature sets R = 1, 2
  lists  code spec basis W      complete extended-code logical lists of weight <= W (mitmsearch enum, orbit roots)
  lift   code spec basis w F    Theorem-5 bulk lift of every translation-orbit rep of the weight-w list, <= F flips
  direct code spec basis R W    exhaustive direct search on the SD6 DEM: is there an undetectable logical of weight <= W
                                (mode decide), or 'find' to report one

  PYTHONPATH=.:tests uv run python -m search.experiments.e043.cert legal bb90 search/experiments/e030/ibm90_spec.json
"""
from __future__ import annotations

import json
import pickle
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)
OUT = ROOT / "results" / "E-043-table"
OUT.mkdir(parents=True, exist_ok=True)


def jdump(rec, fname=None):
    s = json.dumps(rec)
    print(s, flush=True)
    if fname:
        with open(OUT / fname, "a") as f:
            f.write(s + "\n")


def tag_of(spec):
    return Path(spec).stem


def load(spec):
    return json.loads((ROOT / spec).read_text())


def code_of(name):
    from search.theory.B_audit.common import get_code
    return get_code(name)


def build(code_name, spec, basis):
    from search.theory.B_audit.common import Bulk
    from search.theory.B_audit.enum_driver import translations
    from search.theory.B_audit.lift import bulk_columns
    sd = load(spec)
    B = Bulk(sd, code_of(code_name), basis)
    cols, zero = bulk_columns(B)
    keys = sorted(cols)
    kidx = {k: i for i, k in enumerate(keys)}
    perms = translations(code_name, B, sd)
    colperm = []
    for qp, cp in perms:
        pm = []
        for k in keys:
            kind, ident, _ = cols[k][0]
            img = B.key([qp[ident]]) if kind == "d" else B.key([qp[q] for q in B.wr[ident[0]][0][ident[1] - 1:]])
            pm.append(kidx[img])
        assert sorted(pm) == list(range(len(keys)))
        colperm.append(pm)
    return B, cols, zero, keys, colperm


# ------------------------------------------------------------------------------------------------ legality
def tp_membership(code_name, sd):
    """T(P) membership read off the spec: one time vector per check type (translation invariance), each side's 6 CNOT
    times distinct with span <= P - 3 (prep/meas fit), determinism (equal floor on both shared qubits)."""
    from search.theory.B_audit.common import Bulk
    from search.theory.B_audit.delta_terms import terms
    code = code_of(code_name)
    l, m, A, Bt = terms(code_name)
    P = int(sd["period"])
    out = {}
    for key in ("x_checks", "z_checks"):
        tv = set()
        spans = set()
        for ch in sd[key]:
            p = int(ch["prep"]) % P
            ts = sorted(p + ((int(t) - p) % P) for _, t in ch["cnots"])
            meas = p + ((int(ch["meas"]) - p) % P)
            spans.add((ts[0] - p, ts[-1] - ts[0], meas - ts[-1], len(set(ts))))
        out[key + "_prep_span_meas_distinct"] = sorted(spans)
    B = Bulk(sd, code, "Z")      # writers = X checks, readers = Z checks
    # determinism: for every overlapping X/Z pair, floor((tX - tZ)/P) equal on both shared qubits
    bad = 0
    pairs = 0
    for c, (o, tm) in enumerate(B.wr):
        for z, (o2, tm2) in enumerate(B.rd):
            sh = sorted(set(o) & set(o2))
            if not sh:
                continue
            pairs += 1
            fl = {int(np.floor((tm[q] - tm2[q]) / P)) for q in sh}
            bad += len(fl) != 1
    out["overlap_pairs"] = pairs
    out["nondeterministic_pairs"] = bad
    # data qubit: 6 CNOT times distinct mod P
    dq = {}
    for lst in (B.wr, B.rd):
        for o, tm in lst:
            for q in o:
                dq.setdefault(q, []).append(tm[q] % P)
    out["data_collisions"] = sum(len(v) != len(set(v)) for v in dq.values())
    return out


def cmd_legal(code_name, spec):
    from evaluators import candidate as cand
    from evaluators.noise import add_noise
    from search.theory.B_audit.common import Bulk
    from search.theory.B_audit.delta import analyse
    from search.theory.B_audit.dem_check import dem, model
    from search.theory.B_audit.enum_driver import translations
    from search.theory.B_audit.lift import bulk_columns
    from search.theory.B_audit.window_test import conds
    code = code_of(code_name)
    sd = load(spec)
    sp = cand.parse_schedule(sd)
    rec = {"code": code_name, "spec": spec, "period": sp.period,
           "validate_schedule": [str(x) for x in (cand.validate_schedule(sp, code) or [])]}
    rec["T(P)"] = tp_membership(code_name, sd)
    for R in (1, 2, 3):
        for basis in ("Z", "X"):
            circ = cand.memory_circuit(sp, code, basis, R)
            s = circ.compile_detector_sampler().sample(50, append_observables=True)
            try:
                add_noise(circ, "sd6", 1e-3).detector_error_model(approximate_disjoint_errors=True)
                ok = True
            except Exception as e:  # noqa
                ok = repr(e)
            rec[f"noiseless_R{R}{basis}"] = {"all_zero": bool(not s.any()), "dem_built": ok}
    for R in (1, 2):
        for basis in ("Z", "X"):
            circ = cand.memory_circuit(sp, code, basis, R)
            M, _ = model(code, circ, basis)
            D = dem(circ)
            rec[f"model_vs_dem_R{R}{basis}"] = {"model": len(M), "dem": len(D), "equal": M == D}
    rec["window"] = conds(code, sd, Rmax=3)
    for basis in ("Z", "X"):
        B = Bulk(sd, code, basis)
        a = analyse(B)
        cols, zero = bulk_columns(B)
        perms = translations(code_name, B, sd)
        strict = all(B.wr[cp[c]][1][qp[q]] == t for qp, cp in perms for c in range(len(B.wr))
                     for q, t in B.wr[c][1].items()) and \
            all(B.rd[cp[c]][1][qp[q]] == t for qp, cp in perms for c in range(len(B.rd))
                for q, t in B.rd[c][1].items())
        rec[f"bulk_{basis}"] = {"zero_image_hooks": len(zero), "translations": len(perms),
                                "strict_translation_invariant": strict,
                                "delta": {k: a[k] for k in ("delta_values", "coboundary", "violating_edges", "pairing_violations")}}
    jdump(rec, "legal.jsonl")


# ------------------------------------------------------------------------------------------------ lists
def cmd_lists(code_name, spec, basis, W):
    B, cols, zero, keys, colperm = build(code_name, spec, basis)
    nh = B.H.shape[0]
    orb = [-1] * len(keys)
    reps = []
    for j in range(len(keys)):
        if orb[j] < 0:
            for pm in colperm:
                orb[pm[j]] = len(reps)
            reps.append(j)
    lines = [f"{len(keys)} {nh}"]
    for k in keys:
        v = np.frombuffer(k, np.uint8)
        hs = np.flatnonzero(v[:nh]).tolist()
        ls = np.flatnonzero(v[nh:]).tolist()
        lines.append(f"{len(hs)} {' '.join(map(str, hs))} {len(ls)} {' '.join(map(str, ls))}")
    lines += [str(len(reps)), " ".join(map(str, orb)), " ".join(map(str, reps))]
    tg = tag_of(spec)
    inp = OUT / f"ext_{tg}_{basis}.txt"
    inp.write_text("\n".join(lines) + "\n")
    nw = -(-nh // 64)
    exe = str(OUT / {1: "mitm_nw2", 2: "mitm_nw2", 3: "mitm_nw4", 4: "mitm_nw4", 5: "mitm_nw5"}[nw])
    t0 = time.time()
    found, logs = set(), []
    for o in range(len(reps)):
        p = subprocess.run([exe, str(W), "enum", "2", str(o), str(o)], stdin=open(inp), capture_output=True, text=True)
        logs += [l for l in p.stderr.splitlines() if l.startswith(("CASE", "DONE"))]
        for ln in p.stdout.splitlines():
            if ln.startswith("SOL"):
                S = tuple(sorted(map(int, ln.split()[2:])))
                for pm in colperm:
                    found.add(tuple(sorted(pm[j] for j in S)))
    for S in found:
        v = np.zeros(len(keys[0]), np.uint8)
        for j in S:
            v ^= np.frombuffer(keys[j], np.uint8)
        assert not v[:nh].any() and v[nh:].any() and len(set(S)) == len(S)
    byw = Counter(len(S) for S in found)
    for w in sorted(byw):
        L = sorted(S for S in found if len(S) == w)
        pickle.dump({"keys": [[keys[j] for j in S] for S in L], "colset": keys},
                    open(OUT / f"list_{tg}_{basis}_w{w}.pkl", "wb"))
    rec = {"code": code_name, "spec": spec, "basis": basis, "W": W, "ncols": len(keys), "zero_key_hooks": len(zero),
           "orbits": len(reps), "group": len(colperm), "by_weight": dict(sorted(byw.items())),
           "d_ext": min(byw) if byw else f">{W}", "sec": round(time.time() - t0, 1)}
    jdump(rec, "lists.jsonl")


# ------------------------------------------------------------------------------------------------ lift
def cmd_lift(code_name, spec, basis, w, flips, part="0/1"):
    from search.theory.B_audit.lift import check_bulk_solution, solve_bulk
    B, cols, zero, keys, colperm = build(code_name, spec, basis)
    tg = tag_of(spec)
    pth = OUT / f"list_{tg}_{basis}_w{w}.pkl"
    if not pth.exists():
        jdump({"code": code_name, "spec": spec, "basis": basis, "w": w, "flips<=": flips, "n_list": 0, "lifted": 0,
               "note": "empty list"}, "lift.jsonl")
        return
    d = pickle.load(open(pth, "rb"))
    assert set(d["colset"]) == set(keys)
    kidx = {k: i for i, k in enumerate(keys)}
    L = [tuple(sorted(kidx[k] for k in S)) for S in d["keys"]]
    seen, todo = set(), []
    for i, S in enumerate(L):
        if S in seen:
            continue
        todo.append(i)
        for pm in colperm:
            seen.add(tuple(sorted(pm[j] for j in S)))
    assert len(seen) == len(L)
    pi, pn = map(int, part.split("/"))
    todo = todo[pi::pn]
    t0 = time.time()
    lifted, maxshift = [], 0
    for i in todo:
        r = solve_bulk(d["keys"][i], cols, flips)
        if r is not None:
            sol, nfl = r
            assert check_bulk_solution(sol, nfl, flips)
            maxshift = max(maxshift, max(abs(x) for _, x in sol))
            lifted.append(i)
    jdump({"code": code_name, "spec": spec, "basis": basis, "w": w, "flips<=": flips, "n_list": len(L),
           "orbit_reps_checked": len(todo), "part": part, "zero_key_hooks": len(zero), "lifted": len(lifted),
           "first_lifted": lifted[:10], "max_abs_shift": maxshift, "sec": round(time.time() - t0, 1)}, "lift.jsonl")


# ------------------------------------------------------------------------------------------------ direct DEM
def cmd_direct(code_name, spec, basis, R, W, mode="decide"):
    from search.experiments.e040_audit_circ.direct import gf2_solve_map
    from evaluators import candidate as cand
    from evaluators.noise import add_noise
    from search.theory.B_audit.common import Bulk
    from search.theory.B_audit.enum_driver import translations
    t0 = time.time()
    code = code_of(code_name)
    sd = load(spec)
    circ = add_noise(cand.memory_circuit(cand.parse_schedule(sd), code, basis, R), "sd6", 1e-3)
    coords = circ.get_detector_coordinates()
    dem = circ.detector_error_model(approximate_disjoint_errors=True, flatten_loops=True)
    errs = {}
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
            assert ds, "detector-free logical term"
            k = frozenset(ds)
            assert errs.get(k, frozenset(os_)) == frozenset(os_)
            errs[k] = frozenset(os_)
    keys = sorted(errs, key=sorted)
    kid = {k: i for i, k in enumerate(keys)}
    det_of = {(int(c[0]), int(c[1])): d for d, c in coords.items()}
    B = Bulk(sd, code, basis)
    perms = translations(code_name, B, sd)
    K = dem.num_observables
    O = np.zeros((len(keys), K), np.uint8)
    for i, k in enumerate(keys):
        for o in errs[k]:
            O[i, o] = 1
    nrow = 1 + max(int(c[0]) for c in coords.values())
    Hh = np.zeros((len(keys), nrow), np.uint8)
    for i, k in enumerate(keys):
        for x in k:
            Hh[i, int(coords[x][0])] ^= 1
    X = np.concatenate([O, Hh], axis=1)
    colperm = []
    for qp, cp in perms:
        dmap = {d: det_of[(cp[int(c[0])], int(c[1]))] for d, c in coords.items()}
        pm = [kid[frozenset(dmap[x] for x in k)] for k in keys]
        assert sorted(pm) == list(range(len(keys)))
        assert gf2_solve_map(X, O[pm]) is not None
        colperm.append(pm)
    orb = [-1] * len(keys)
    reps = []
    for j in range(len(keys)):
        if orb[j] < 0:
            for pm in colperm:
                orb[pm[j]] = len(reps)
            reps.append(j)
    nd = dem.num_detectors
    lines = [f"{len(keys)} {nd}"]
    for k in keys:
        lines.append(f"{len(k)} {' '.join(map(str, sorted(k)))} {len(errs[k])} {' '.join(map(str, sorted(errs[k])))}")
    lines += [str(len(reps)), " ".join(map(str, orb)), " ".join(map(str, reps))]
    inp = OUT / f"dem_{tag_of(spec)}_{basis}_R{R}.txt"
    inp.write_text("\n".join(lines) + "\n")
    nw = -(-nd // 64)
    exe = {1: "mitm_nw2", 2: "mitm_nw2", 3: "mitm_nw4", 4: "mitm_nw4", 5: "mitm_nw5", 6: "mitm_nw6"}[nw]
    found, cases = None, []
    for o in range(len(reps)):
        p = subprocess.run([str(OUT / exe), str(W), "decide", "2", str(o), str(o)], stdin=open(inp),
                           capture_output=True, text=True)
        cases += [l for l in p.stderr.splitlines() if l.startswith("CASE")]
        sols = [list(map(int, l.split()[2:])) for l in p.stdout.splitlines() if l.startswith("SOL")]
        if sols:
            found = sols[0]
            break
    rec = {"code": code_name, "spec": spec, "basis": basis, "R": R, "W<=": W, "terms": len(keys), "detectors": nd,
           "orbits": len(reps), "orbits_done": len(cases), "found": found,
           "nodes_total": sum(int(c.split("nodes=")[1].split()[0]) for c in cases if "nodes=" in c),
           "sec": round(time.time() - t0, 1)}
    if found:
        dd, oo = set(), set()
        for j in found:
            dd ^= set(keys[j])
            oo ^= set(errs[keys[j]])
        rec["found_check"] = {"weight": len(found), "distinct": len(set(found)) == len(found), "dets_zero": not dd,
                              "obs": sorted(oo)}
    inp.unlink()
    jdump(rec, "direct.jsonl")


if __name__ == "__main__":
    c = sys.argv[1]
    a = sys.argv[2:]
    if c == "legal":
        cmd_legal(a[0], a[1])
    elif c == "lists":
        cmd_lists(a[0], a[1], a[2], int(a[3]))
    elif c == "lift":
        cmd_lift(a[0], a[1], a[2], int(a[3]), int(a[4]), *(a[5:6]))
    elif c == "direct":
        cmd_direct(a[0], a[1], a[2], int(a[3]), int(a[4]))
    else:
        raise SystemExit(__doc__)
