"""Fig. 1 (u11) audit, 2026-10-22: shared helpers, written independently of paper/scripts/fig1_u11_data.py.
Reused only: the frozen evaluator's public builders (build_code, parse_schedule, build_circuits, add_noise),
the u11 spec json, and the E-032 audit's weight-10 list (column-key tuples; re-verified here).
Everything else (segmented control, extended code, DEM grouping, lift oracle, conflict-set extraction,
tick tables, injection) is own code."""
import collections, json, os, pickle, sys
import numpy as np, stim

ROOT = os.path.expanduser("~/Desktop/qec-ai-search")
os.chdir(ROOT)
sys.path[:0] = [ROOT]
from evaluators.tasks import build_code, get_task
from evaluators.candidate import parse_schedule, build_circuits
from evaluators.noise import add_noise

code, _ = build_code(get_task("gross-dcirc"), None)
HX, HZ, LX, LZ = [np.asarray(m, np.uint8) % 2 for m in (code.HX, code.HZ, code.LX, code.LZ)]
N, NC = 144, 72
OUT = ROOT + "/results/fig1-u11-audit"

U11 = json.load(open("search/experiments/e032/u11_spec.json"))


def order_of(c, P):
    return [q for _, q in sorted(((t - c["prep"]) % P, q) for q, t in c["cnots"])]


def segctl(u=U11):
    """Same per-check CNOT orders; X block at steps 1..6 (reset 0, meas 7), Z block at steps 8..13 (reset 7, meas 14)."""
    P = u["period"]
    return {"format": "qec-schedule/v1", "period": 15,
            "x_checks": [{"prep": 0, "meas": 7, "cnots": [[q, 1 + k] for k, q in enumerate(order_of(c, P))]} for c in u["x_checks"]],
            "z_checks": [{"prep": 7, "meas": 14, "cnots": [[q, 8 + k] for k, q in enumerate(order_of(c, P))]} for c in u["z_checks"]]}


def circ(spec_json, R, basis="Z", noisy=True):
    c = build_circuits(parse_schedule(spec_json).canonical(), code, R)[basis]
    return add_noise(c, "sd6", 1e-3).flattened() if noisy else c.flattened()


def key_of(sup):
    v = np.zeros(N, np.uint8); v[list(sup)] = 1
    return ((HZ @ v) % 2).tobytes() + ((LZ @ v) % 2).tobytes()


def ext_columns(spec_json):
    """Z basis: data columns + proper suffixes of the X-check orders; merged by image (H_Z v, L_Z v)."""
    P = spec_json["period"]
    sups = [(q,) for q in range(N)]
    for c in spec_json["x_checks"]:
        o = order_of(c, P)
        sups += [tuple(sorted(o[k:])) for k in range(1, 6)]
    cols = {}
    for s in sups:
        k = key_of(s)
        cols.setdefault(k, []).append(s)
    return cols


def dem_groups(c):
    k0 = c.num_observables
    aug = c.copy()
    rows = list(HZ) + list(LZ)
    for r, row in enumerate(rows):
        aug.append("OBSERVABLE_INCLUDE", [stim.target_rec(int(q) - N) for q in np.flatnonzero(row)], k0 + r)
    dem = aug.detector_error_model(decompose_errors=False, approximate_disjoint_errors=True)
    groups, zero = collections.defaultdict(list), []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        dets, img, ob = set(), np.zeros(len(rows), np.uint8), np.zeros(k0, np.uint8)
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                dets ^= {t.val}
            elif t.is_logical_observable_id():
                if t.val >= k0: img[t.val - k0] ^= 1
                else: ob[t.val] ^= 1
        assert (ob == img[72:]).all()
        if img.any():
            groups[img[:72].tobytes() + img[72:].tobytes()].append((frozenset(dets), inst))
        elif dets:
            zero.append((frozenset(dets), inst))
    return aug, dem, groups, zero


def feasible(cols, active=None, want=False):
    """cols: list (one per column) of lists of detector frozensets. Exact DP over XOR states restricted to `active`."""
    allds = sorted(set().union(*[d for col in cols for d in col])) if active is None else sorted(active)
    pos = {d: i for i, d in enumerate(allds)}
    masks = [[sum(1 << pos[d] for d in t if d in pos) for t in col] for col in cols]
    n = len(cols)
    touch = [0] * n
    for i in range(n):
        for m in masks[i]: touch[i] |= m
    order, left, cur = [], set(range(n)), 0
    while left:
        i = max(left, key=lambda j: (bin(touch[j] & cur).count("1"), -bin(touch[j]).count("1"), -j))
        order.append(i); left.remove(i); cur |= touch[i]
    later = [0] * (n + 1)
    for k in range(n - 1, -1, -1):
        later[k] = later[k + 1] | touch[order[k]]
    states, hist = {0: None}, []
    for k, i in enumerate(order):
        keep, nxt = later[k + 1], {}
        for s in states:
            for j, m in enumerate(masks[i]):
                s2 = s ^ m
                if s2 & ~keep: continue
                if s2 not in nxt: nxt[s2] = (s, j)
        hist.append(nxt); states = nxt
        if not states: return False, None
    if 0 not in states: return False, None
    if not want: return True, None
    ch, s = [None] * n, 0
    for k in range(n - 1, -1, -1):
        ps, j = hist[k][s]; ch[order[k]] = j; s = ps
    return True, ch


def all_syndromes(cols):
    """Set of all achievable syndromes (as frozensets of detectors), by explicit product (columns have <= few terms)."""
    st = {frozenset()}
    for col in cols:
        st = {s ^ t for s in st for t in col}
    return st


def minimal_family(syns):
    syns = sorted(syns, key=len)
    mins = []
    for s in syns:
        if not any(m <= s for m in mins): mins.append(s)
    return mins


def hitting_sets(mins, universe=None):
    """All inclusion-minimal hitting sets of the family `mins` (= all irreducible conflicting sets).
    Branch on an un-hit member; keep a candidate only if every chosen element has a private member."""
    mins = [frozenset(m) for m in mins]
    out = set()

    def rec(A):
        un = [m for m in mins if not (m & A)]
        if not un:
            if all(any((m & A) == {d} for m in mins) for d in A): out.add(frozenset(A))
            return
        # prune: an element already without a possible private member can be dropped (non-minimal branch)
        for d in A:
            if not any((m & A) == {d} for m in mins): return
        m = min(un, key=len)
        for d in sorted(m): rec(A | {d})

    rec(frozenset())
    return sorted((tuple(sorted(A)) for A in out), key=lambda t: (len(t), t))


def iis_deletion(cols, order):
    act = list(order); i = 0
    while i < len(act):
        trial = act[:i] + act[i + 1:]
        if not feasible(cols, set(trial))[0]: act = trial
        else: i += 1
    return sorted(act)


def tick_tables(c):
    """per tick: CX pairs, resets, measurements. Returns dicts keyed by (ancilla, data) etc."""
    t = 0
    cx = collections.defaultdict(list)          # (ctrl, tgt) -> ticks
    meas, reset = collections.defaultdict(list), collections.defaultdict(list)
    for op in c:
        if op.name == "TICK": t += 1; continue
        tg = [x.value for x in op.targets_copy() if x.is_qubit_target]
        if op.name in ("CX", "CNOT"):
            for a, b in zip(tg[::2], tg[1::2]): cx[(a, b)].append(t)
        elif op.name in ("M", "MX", "MR", "MRX"):
            for q in tg: meas[q].append(t)
        if op.name in ("R", "RX", "MR", "MRX"):
            for q in tg: reset[q].append(t)
    return cx, meas, reset


def load_w10():
    lp = pickle.load(open("results/E-032-audit/lists_u11_spec_Z.pkl", "rb"))
    return lp["cols"], [tuple(lp["cols"][j] for j in S) for S in lp["sets"][10]]


def translate(q, a, b):
    """gross code layout q = blk*72 + x*6 + y; translation (x,y)->(x+a, y+b)."""
    blk, r = divmod(q, 72); x, y = divmod(r, 6)
    return blk * 72 + ((x + a) % 12) * 6 + (y + b) % 6
