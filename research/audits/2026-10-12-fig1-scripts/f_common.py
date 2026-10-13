"""Fig. 1 audit (2026-10-12): own DEM build, own lift oracle (DP over XOR states), own IIS / minimum extraction.
Only inputs reused: evaluator circuit builder + noise (frozen), the Fig. 12 baseline schedule, the P18 spec json,
and the E-018 audit's list of 4224 weight-11 extended logicals (as column-key tuples)."""
import collections, json, os, sys
import numpy as np, stim
ROOT = os.path.expanduser("~/Desktop/qec-ai-search")
os.chdir(ROOT)
sys.path[:0] = [ROOT, ROOT + "/tests"]
from schedule_helpers import from_baseline
from baselines.bb_code import gross_code
from baselines.strikis import strikis_fig12
from evaluators.tasks import build_code, get_task
from evaluators.candidate import parse_schedule, build_circuits
from evaluators.noise import add_noise

code, _ = build_code(get_task("gross-dcirc"), None)
HZ = np.asarray(code.HZ, np.uint8) % 2
LZ = np.asarray(code.LZ, np.uint8) % 2
N, MX = 144, 72
R = 1


def fig12_spec():
    return from_baseline(strikis_fig12(gross_code())[0])


def p18_spec():
    return parse_schedule(json.load(open("search/experiments/e024a/cs_P18_H24.json")))


def xorders(spec):
    P = spec.period
    return [[q for _, q in sorted(((t - c.prep) % P, q) for q, t in c.cnots)] for c in spec.x_checks]


def key_of(sup):
    v = np.zeros(N, np.uint8); v[list(sup)] = 1
    return ((HZ @ v) % 2).tobytes() + ((LZ @ v) % 2).tobytes()


def circuit(spec):
    return add_noise(build_circuits(spec.canonical(), code, R)["Z"], "sd6", 1e-3)


def my_dem(c):
    """Augment with HZ rows + LZ rows on the final data readout as extra observables; group DEM terms by image."""
    k0 = c.num_observables
    aug = c.copy()
    rows = list(HZ) + list(LZ)
    for r, row in enumerate(rows):
        aug.append("OBSERVABLE_INCLUDE", [stim.target_rec(int(q) - N) for q in np.flatnonzero(row)], k0 + r)
    dem = aug.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    groups = collections.defaultdict(list)
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        dets, img = set(), np.zeros(len(rows), np.uint8)
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                dets ^= {t.val}
            elif t.is_logical_observable_id() and t.val >= k0:
                img[t.val - k0] ^= 1
        if img.any():
            groups[img[:72].tobytes() + img[72:].tobytes()].append((frozenset(dets), inst))
    return aug, dem, groups


def layer_ticks(c):
    """(Z check i, q) -> layers where CX(q -> Zanc i); (X check i, q) -> layers where CX(Xanc i -> q)."""
    t, zr, xr = 0, collections.defaultdict(list), collections.defaultdict(list)
    for op in c.flattened():
        if op.name == "TICK":
            t += 1; continue
        if op.name == "CX":
            tg = [x.value for x in op.targets_copy()]
            for a, b in zip(tg[::2], tg[1::2]):
                if b >= N + MX: zr[(b - N - MX, a)].append(t)
                elif N <= a < N + MX: xr[(a - N, b)].append(t)
    return zr, xr


# ---------- lift oracle: exact DP over XOR states, with component split and dead-bit pruning ----------
def feasible(cols, active=None, want_witness=False):
    """cols: list of lists of detector frozensets (one list per column). active: detector subset or None (all).
    Returns (feasible, choice indices or None). Exact: exists one term per column with zero syndrome on active."""
    allds = sorted(set().union(*[d for col in cols for d in col])) if active is None else sorted(active)
    pos = {d: i for i, d in enumerate(allds)}
    masks = [[sum(1 << pos[d] for d in t if d in pos) for t in col] for col in cols]
    # order columns: greedy by connectivity (keeps state sets small)
    n = len(cols)
    touch = [0] * n
    for i in range(n):
        for m in masks[i]: touch[i] |= m
    order, left, cur = [], set(range(n)), 0
    while left:
        i = max(left, key=lambda j: (bin(touch[j] & cur).count("1"), -bin(touch[j]).count("1")))
        order.append(i); left.remove(i); cur |= touch[i]
    later = [0] * (n + 1)
    for k in range(n - 1, -1, -1):
        later[k] = later[k + 1] | touch[order[k]]
    states = {0: None}
    hist = []
    for k, i in enumerate(order):
        keep = later[k + 1]
        nxt = {}
        for s in states:
            for j, m in enumerate(masks[i]):
                s2 = s ^ m
                if s2 & ~keep:        # a bit no later column can clear
                    continue
                if s2 not in nxt: nxt[s2] = (s, j)
        hist.append(nxt); states = nxt
        if not states: return False, None
    if 0 not in states: return False, None
    if not want_witness: return True, None
    ch, s = [None] * n, 0
    for k in range(n - 1, -1, -1):
        ps, j = hist[k][s]; ch[order[k]] = j; s = ps
    return True, ch


def iis_deletion(cols, order):
    act = list(order)
    i = 0
    while i < len(act):
        trial = act[:i] + act[i + 1:]
        if not feasible(cols, set(trial))[0]: act = trial
        else: i += 1
    return sorted(act)


def minimum_iis(cols):
    """Minimum-cardinality infeasible detector subset via implicit hitting set:
    A infeasible <=> A meets the syndrome of every choice. Lower bound from min hitting set of found syndromes."""
    from ortools.sat.python import cp_model
    allds = sorted(set().union(*[d for col in cols for d in col]))
    fam = []
    A = set()
    while True:
        ok, ch = feasible(cols, A, want_witness=True)
        if not ok:
            return sorted(A)
        syn = set()
        for col, j in zip(cols, ch): syn ^= set(col[j])
        assert syn and not (syn & A)
        fam.append(syn)
        M = cp_model.CpModel(); y = {d: M.NewBoolVar("") for d in allds}
        for s in fam: M.AddBoolOr([y[d] for d in s])
        M.Minimize(sum(y.values()))
        sv = cp_model.CpSolver(); sv.parameters.num_workers = 1
        assert sv.Solve(M) == cp_model.OPTIMAL
        A = {d for d in allds if sv.Value(y[d])}
