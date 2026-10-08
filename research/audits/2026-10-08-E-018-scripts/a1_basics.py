"""Audit E-018 (a1): independent basic facts.
- own extended-code construction (keys = (H s, L s)) from the evaluator's code + Fig. 12 orders read from the
  evaluator-format spec (not from e018/common.py);
- the experimenter's 4224+4224 weight-11 sets: weight, distinct columns, He=0, Le!=0 (own matrices);
- translation symmetry: which of the 72 translations preserve per-check orders (as sequences) and colours, and
  whether the stored sets are closed under them;
- single-hook (10 data + r2) logicals: support disjointness, |Q∩c| profile.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-08-E-018-scripts/a1_basics.py
"""
import json, pickle, sys, collections
import numpy as np
sys.path.insert(0, "tests")
from schedule_helpers import from_baseline
from baselines.bb_code import gross_code
from baselines.strikis import strikis_fig12
from evaluators.tasks import build_code, get_task

OUT = "results/E-018-audit"
code, _ = build_code(get_task("gross-dcirc"), None)
HX, HZ, LX, LZ = [np.asarray(m, np.uint8) % 2 for m in (code.HX, code.HZ, code.LX, code.LZ)]
sched, meta = strikis_fig12(gross_code())
spec = from_baseline(sched)
P = spec.period
def order(c):
    return [col for _, col in sorted(((t - c.prep) % P, col) for col, t in c.cnots)]
xo = [order(c) for c in spec.x_checks]; zo = [order(c) for c in spec.z_checks]
colour = meta["check_colour"]
xcol = ["RGB".index(colour[q]) for q in sched.x_checks]; zcol = ["RGB".index(colour[q]) for q in sched.z_checks]

def ext(kind):
    H, L, ords = (HZ, LZ, xo) if kind == "X" else (HX, LX, zo)
    sups = [(j,) for j in range(144)] + [tuple(sorted(o[l:])) for o in ords for l in range(1, 6)]
    keyof = {}
    for s in sups:
        v = np.zeros(144, np.uint8); v[list(s)] = 1
        k = ((H @ v) % 2).tobytes() + ((L @ v) % 2).tobytes()
        keyof[s] = k
    return H, L, keyof

def tr(a, b):
    return [((i // 6 + a) % 12) * 6 + (i % 6 + b) % 6 for i in range(72)]

rep = {}
for kind in "XZ":
    H, L, keyof = ext(kind)
    ords = xo if kind == "X" else zo
    cols = ords and None
    E_their = __import__("search.experiments.e018.common", fromlist=["ext"]).ext(kind)  # only to read column supports
    sols = pickle.load(open(f"results/E-018-gross-interleaved-12/w11_all_{kind}.pkl", "rb"))
    bad = 0; keysets = set()
    comp = collections.Counter()
    for S in sols:
        assert len(S) == 11 and len(set(S)) == 11
        sups = [E_their["col_sups"][j][0] for j in S]
        ks = [keyof[s] for s in sups]
        assert len(set(ks)) == 11
        x = np.zeros(144, np.uint8)
        for s in sups:
            for q in s: x[q] ^= 1
        if ((H @ x) % 2).any() or not ((L @ x) % 2).any():
            bad += 1
        keysets.add(frozenset(ks))
    # translations: which preserve orders+colours (as maps check->check)
    ords_set = {tuple(o): i for i, o in enumerate(ords)}
    good_g = []
    for a in range(12):
        for b in range(6):
            p = tr(a, b); pp = p + [x + 72 for x in p]
            ok = True
            for i, o in enumerate(ords):
                t = tuple(pp[q] for q in o)
                if t not in ords_set: ok = False; break
                cl = xcol if kind == "X" else zcol
                if cl[ords_set[t]] != cl[i]: ok = False; break
            if ok: good_g.append((a, b))
    # closure under good translations (map supports, compare key sets)
    notclosed = 0
    for g in good_g:
        p = tr(*g); pp = p + [x + 72 for x in p]
        for S in list(sols)[:500]:
            ks = frozenset(keyof[tuple(sorted(pp[q] for q in E_their["col_sups"][j][0]))] for j in S)
            notclosed += ks not in keysets
    rep[kind] = {"n": len(sols), "distinct_keysets": len(keysets), "not_logical": bad,
                 "order_colour_preserving_translations": len(good_g), "closure_failures(first500)": notclosed}
    # single-hook analysis
    def typ(j):
        cs = E_their["col_sups"][j]
        return "d" if any(len(s) == 1 for s in cs) else "r%d" % len(cs[0])
    rd = zo if kind == "X" else xo
    prof = collections.Counter(); overl = 0; nsh = 0
    for S in sols:
        c = collections.Counter(typ(j) for j in S)
        if c["d"] == 10 and c["r2"] == 1:
            nsh += 1
            qs = []
            for j in S:
                cs = E_their["col_sups"][j]
                s = next((s for s in cs if len(s) == 1), cs[0])
                qs += list(s)
            if len(set(qs)) != len(qs): overl += 1
            Q = set(qs)
            prof[tuple(sorted(collections.Counter(len(Q & set(o)) for o in rd if Q & set(o)).items()))] += 1
    rep[kind]["single_hook_d10r2"] = nsh
    rep[kind]["single_hook_overlapping_supports"] = overl
    rep[kind]["single_hook_Qc_profile"] = {str(k): v for k, v in prof.items()}
print(json.dumps(rep, indent=1))
json.dump(rep, open(f"{OUT}/a1_basics.json", "w"), indent=1)
