"""SM S16, "Soundness of the clauses": sampled checks of the frame model and of the nogood clauses against the exact
detector error model (finite samples, not a proof; the UNSAT statements rest on the frame-model argument).

  A (model): on circuits B of the colour-symmetric family at period P (CEGAR models of the primary encoding, and
    random family members drawn without logical nogoods), every sampled logical that the frame model says lifts on
    B must lift exactly in B's SD6 detector error model at R = span(pi) + 3 (retry at span + 6), with the same 11
    extended-code columns (CP-SAT lift of code/gross12/ext.py).
  B (clause): nogood clauses collected along the CEGAR run; on a random family circuit for which all literals of a
    clause are false (so the clause excludes it), the clause's logical must lift exactly.

    python code/sat/soundness.py 17 0 60 15            # paper: 144 + 87 sampled checks
    python code/sat/soundness.py 17 0 4 4 all          # every claim of 4 + 4 circuits (847 + 12 checks)
Writes the sampled cases to --out (JSON) if given.
"""
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_cli import Verdict, load_code                  # noqa: E402
from gross12 import ext as GE                              # noqa: E402
from gross12.schedule import parse_schedule               # noqa: E402
from sat import frame                                       # noqa: E402
from sat.common import BASIS_OF_KIND, N2, bf_P, build_kind_data, colour, kernel, parse_orders, table, Family  # noqa: E402
from sat.enc_primary import Enc                             # noqa: E402

args = [x for x in sys.argv[1:] if not x.startswith("--")]
P, nowrap, NC, NR = (int(v) for v in args[:4])
ALL = len(args) > 4 and args[4] == "all"
outp = next((x.split("=", 1)[1] for x in sys.argv[1:] if x.startswith("--out=")), None)
X = "A1A2A3B3B1B2,A1A2A3B1B2B3,A1A3A2B3B1B2"; Z = "A1A3A2B3B1B2,A1A2A3B1B2B3,A1A2A3B3B1B2"
col = (3, 1, 1)
orders = {"X": parse_orders(X), "Z": parse_orders(Z)}
F = Family(kernel(col))
ccol = [colour(col, F.reps[k]) for k in range(F.nc)]
KD = build_kind_data(col, orders)
recs, skipped = frame.prepare(F, KD)
rng = random.Random(4242 + P)
code = load_code()
T = table()


def spec_of(t, st):
    d = {"format": "qec-schedule/v1", "period": P, "x_checks": [], "z_checks": []}
    for ty, key in (("X", "x_checks"), ("Z", "z_checks")):
        for i in range(N2):
            u = (ty, F.cls[i])
            sv = st[u]
            cn = [[int(T[ty][i][l]), t[F.idx[(ty, F.cls[i], l)]] % P] for l in range(6)]
            d[key].append({"prep": sv % P, "meas": (sv + P - 1) % P, "cnots": cn})
    return d


def times(M, model):
    ms = set(l for l in model if l > 0)
    t = {i: v for (i, v), var in M.x.items() if var in ms}
    st = {u: w for (u, w), var in M.s.items() if var in ms}
    return t, st


def key_of(kind, j):
    import numpy as np
    H, L = (code.HZ, code.LZ) if kind == "X" else (code.HX, code.LX)
    v = np.zeros(144, np.uint8); v[list(KD[kind][0]["col_sups"][j][0])] = 1
    return ((H @ v) % 2).astype(np.uint8).tobytes() + ((L @ v) % 2).astype(np.uint8).tobytes()


cache = {}


def exact(t, st, r, pi):
    sp = parse_schedule(spec_of(t, st))
    h = json.dumps(sp.canonical().to_dict(), sort_keys=True)
    kind = r["kind"]; basis = BASIS_OF_KIND[kind]
    S = [key_of(kind, j) for j in r["S"]]
    span = max(pi.values()) - min(pi.values())
    for R in (span + 3, span + 6):
        k = (h, R, basis)
        if k not in cache:
            if len(cache) > 12:
                cache.clear()
            cache[k] = GE.dem_groups(sp, code, R, basis)[0]
        g = cache[k]
        assert all(x in g for x in S)
        if GE.lift(S, g):
            return R
    return None


def claims(t):
    return frame.evaluate(F, recs, lambda cons: bf_P(cons, t, P))


def lit_true(cons, pi, t):
    out = []
    for u, w, kd, (i1, i2) in cons:
        K = pi[u] - pi[w]; dlt = t[i2] - t[i1]
        out.append(dlt <= (K - 1) * P - 1 if kd in ("free", "hook+") else dlt >= -K * P)
    return any(out)


t0 = time.time()
res = {"P": P, "nowrap": nowrap, "A_checked": 0, "A_fail": [], "B_checked": 0, "B_fail": [], "B_bf_infeasible": 0,
       "pool": 0, "cegar_iters": 0, "cases": []}
M = Enc(F, orders, ccol, P, nowrap)
pool, cmodels = [], []
for it in range(NC):
    if not M.S.solve():
        break
    t, st = times(M, M.S.get_model()); lif = claims(t)
    cmodels.append((t, st, lif))
    if not lif:
        break
    for r, cons, pi in lif:
        pool.append((r, cons, pi))
        lits = set()
        for u_, w_, kd, (i1, i2) in cons:
            K = pi[u_] - pi[w_]
            lits.add(-M.D(i1, i2, (K - 1) * P) if kd in ("free", "hook+") else M.D(i1, i2, -K * P))
        M.S.add_clause(sorted(lits))
    res["cegar_iters"] = it + 1
res["pool"] = len(pool)
M0 = Enc(F, orders, ccol, P, nowrap)
rmodels = []
for k in range(NR):
    M0.S.set_phases([v if rng.random() < 0.5 else -v for v in range(1, M0.pool.top + 1)])
    if not M0.S.solve():
        break
    t, st = times(M0, M0.S.get_model()); rmodels.append((t, st))
    M0.S.add_clause([-M0.x[(i, v)] for i, v in t.items()])
for idx, (t, st, lif) in enumerate([(t, st, lif) for t, st, lif in cmodels[::max(1, len(cmodels) // 8)]] +
                                    [(t, st, claims(t)) for t, st in rmodels]):
    for r, cons, pi in (lif if ALL else rng.sample(lif, min(6, len(lif)))):
        R = exact(t, st, r, pi); res["A_checked"] += 1
        res["cases"].append({"test": "A", "circuit_times": [t[i] for i in range(len(t))], "logical_kind": r["kind"],
                             "columns": [key_of(r["kind"], j).hex() for j in r["S"]], "exact_lift_R": R})
        if R is None:
            res["A_fail"].append((idx, r["kind"], r["S"]))
for idx, (t, st) in enumerate(rmodels):
    excl = [(r, cons, pi) for r, cons, pi in pool if not lit_true(cons, pi, t)]
    for r, cons, pi in rng.sample(excl, min(6, len(excl))):
        if bf_P(cons, t, P) is None:
            res["B_bf_infeasible"] += 1
        R = exact(t, st, r, pi); res["B_checked"] += 1
        res["cases"].append({"test": "B", "circuit_times": [t[i] for i in range(len(t))], "logical_kind": r["kind"],
                             "columns": [key_of(r["kind"], j).hex() for j in r["S"]], "exact_lift_R": R})
        if R is None:
            res["B_fail"].append((idx, r["kind"], r["S"]))
res["sec"] = round(time.time() - t0)
if outp:
    json.dump(res, open(outp, "w"))
V = Verdict()
V(not res["A_fail"] and not res["B_fail"] and res["B_bf_infeasible"] == 0,
  f"P={P}: model claims confirmed by the exact lift {res['A_checked'] - len(res['A_fail'])}/{res['A_checked']}; "
  f"excluding clauses confirmed {res['B_checked'] - len(res['B_fail'])}/{res['B_checked']} "
  f"(CEGAR iterations {res['cegar_iters']}, pool {res['pool']}, {res['sec']} s)")
V.exit()
