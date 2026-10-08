"""Audit E-018 (a4): validate the two modelling ingredients the impossibility argument relies on, against stim and the
evaluator's own circuit construction (build_circuits), on random colour-uniform schedules with gaps / pipelining:
 (1) determinism criterion  floor((T_x(u)-T_z(u))/P) == floor((T_x(v)-T_z(v))/P)  for every overlapping X/Z pair
     <=> stim builds a DEM without non-deterministic detectors (both bases);
 (2) model-lift => real undetected weight-11 logical: for lifting single-hook logicals, inject the 11 model faults
     (10 data X right after a read, 1 X on the X-check ancilla after its 4th CNOT) as X_ERROR(1) into the noiseless
     evaluator circuit (Z basis, R rounds) and check: 0 detectors fire, >= 1 observable flips.  Also a one-fault-removed
     negative control.
    PYTHONPATH=.:tests uv run python research/audits/2026-10-08-E-018-scripts/a4_validate.py P nsamples seed
"""
import itertools, json, random, sys, collections
import numpy as np
import stim
sys.path.insert(0, "research/audits/2026-10-08-E-018-scripts")
from a1_common import xo, zo, xcol, zcol, code, SPEC
from a3_model import single_hook_logicals, lifts, witness, T, POS
from evaluators.candidate import CheckTiming, ScheduleSpec, build_circuits

P = int(sys.argv[1]); NS = int(sys.argv[2]); rng = random.Random(int(sys.argv[3]))
classes = [("X", 0), ("X", 1), ("X", 2), ("Z", 0), ("Z", 1), ("Z", 2)]
cls_of = {("X", i): ("X", xcol[i]) for i in range(72)} | {("Z", j): ("Z", zcol[j]) for j in range(72)}
offsets = list(itertools.combinations(range(1, P - 1), 6))


def expand(cl):
    return {chk: cl[c] for chk, c in cls_of.items()}


def conflict_free(sched):
    seen = set()
    for chk, (s, o) in sched.items():
        ords = xo[chk[1]] if chk[0] == "X" else zo[chk[1]]
        for k, q in enumerate(ords):
            key = (q, (s + o[k]) % P)
            if key in seen: return False
            seen.add(key)
    return True


def my_det(sched):
    for i, oi in enumerate(xo):
        for j, oj in enumerate(zo):
            sh = sorted(set(oi) & set(oj))
            if sh:
                u, v = sh
                a, c = ("X", i), ("Z", j)
                if (T(sched, a, u) - T(sched, c, u)) // P != (T(sched, a, v) - T(sched, c, v)) // P:
                    return False
    return True


def to_spec(sched, Pp=None):
    Pp = Pp or P
    def mk(chk):
        s, o = sched[chk]
        ords = xo[chk[1]] if chk[0] == "X" else zo[chk[1]]
        return CheckTiming(s % Pp, (s + o[5] + 1) % Pp, tuple(sorted((int(q), (s + o[k]) % Pp) for k, q in enumerate(ords))))
    return ScheduleSpec(Pp, tuple(mk(("X", i)) for i in range(72)), tuple(mk(("Z", j)) for j in range(72)))


def stim_det(spec):
    try:
        for b, c in build_circuits(spec, code, 2).items():
            c.detector_error_model()
        return True
    except ValueError:
        return False


def inject(sched, Pp, L, R=14, drop=None):
    """Returns (#fired detectors, observables flipped) for the model witness of L in the noiseless Z circuit."""
    w = witness(sched, Pp, L, "Z")
    assert w is not None
    H, times = w
    free, a, res = L
    circ = build_circuits(to_spec(sched, Pp), code, R)["Z"].flattened()
    n, mx = code.n, len(xo)
    anc = {("X", i): n + i for i in range(72)} | {("Z", j): n + mx + j for j in range(72)}
    # circuit ticks of each (control, target) CX pair
    ticks = collections.defaultdict(list); tick = 0
    for op in circ:
        if op.name == "TICK": tick += 1; continue
        if op.name == "CX":
            tg = [t.value for t in op.targets_copy()]
            for x, y in zip(tg[::2], tg[1::2]):
                ticks[(x, y)].append(tick)
    def gate(chk, q):
        return (anc[chk], q) if chk[0] == "X" else (q, anc[chk])
    # global offset: circuit tick = model time + Delta (mod P)
    D = {(ticks[gate(chk, q)][0] - T(sched, chk, q)) % Pp for chk in [("X", 0), ("Z", 5), ("X", 40)] for q in (xo[chk[1]] if chk[0] == "X" else zo[chk[1]])}
    assert len(D) == 1, D
    Delta = D.pop()
    q4 = xo[a[1]][3]
    ev = [(times[wq], wq, ("data", wq)) for wq in free]
    rdcheck = {}
    for wq in free:
        rdcheck[wq] = next(c for c in [("Z", j) for j, o in enumerate(zo) if wq in o]
                           if (times[wq] - T(sched, c, wq)) % Pp == 0)
    th = T(sched, a, q4) + H["F"] * Pp
    ev.append((th, anc[a], ("hook", a)))
    tmin = min(e[0] for e in ev); tmax = max(e[0] for e in ev)
    m = ((R * Pp) // 2 - (tmax + tmin) // 2) // Pp
    ins = collections.defaultdict(list)
    for t, qb, lab in ev:
        if drop is not None and lab == drop: continue
        ct = t + m * Pp + Delta
        gq = gate(rdcheck[qb], qb) if lab[0] == "data" else gate(a, q4)
        assert ct in ticks[gq], ("no such gate at tick", lab, ct)
        ins[ct].append(qb)
    new = stim.Circuit(); tick = 0
    ops = list(circ)
    for k, op in enumerate(ops):
        if op.name == "TICK":
            if ins.get(tick): new.append("X_ERROR", ins.pop(tick), 1.0)
            tick += 1
        new.append(op)
    assert not ins, "unplaced faults"
    s = new.compile_detector_sampler().sample(1, append_observables=True)[0]
    nd = new.num_detectors
    return int(s[:nd].sum()), int(s[nd:].sum())


if __name__ == "__main__":
    LOG = single_hook_logicals("X")
    out = {"P": P, "det_agree": 0, "det_disagree": [], "n_det": 0, "n_nondet": 0, "inject_ok": 0, "inject_bad": [],
           "neg_ctrl_fired": 0, "neg_ctrl_total": 0, "blocked_counts": []}
    tries = 0
    while out["n_det"] + out["n_nondet"] < NS and tries < 10 ** 6:
        tries += 1
        cl = {c: ((0 if c == ("X", 0) else rng.randrange(P)), rng.choice(offsets)) for c in classes}
        sched = expand(cl)
        if not conflict_free(sched): continue
        spec = to_spec(sched)
        md, sd = my_det(sched), stim_det(spec)
        if md == sd: out["det_agree"] += 1
        else: out["det_disagree"].append({str(k): v for k, v in cl.items()})
        out["n_det" if sd else "n_nondet"] += 1
        if not sd: continue
        lif = [L for L in LOG if lifts(sched, P, L, "Z")]
        out["blocked_counts"].append(len(LOG) - len(lif))
        for L in rng.sample(lif, min(3, len(lif))):
            nd, no = inject(sched, P, L)
            if nd == 0 and no > 0: out["inject_ok"] += 1
            else: out["inject_bad"].append([str(cl), str(L), nd, no])
            nd2, _ = inject(sched, P, L, drop=("data", L[0][rng.randrange(10)]))
            out["neg_ctrl_total"] += 1; out["neg_ctrl_fired"] += nd2 > 0
    out["tries"] = tries
    print(json.dumps({k: v for k, v in out.items() if k != "blocked_counts"}),
          "blocked per det schedule (of 360):", sorted(out["blocked_counts"]))
    json.dump(out, open(f"results/E-018-audit/a4_P{P}_s{sys.argv[3]}.json", "w"))
