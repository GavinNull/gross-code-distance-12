"""SM S10, "Completeness of the family encoding": circuits drawn independently of the SAT encoding are models of it.

sample  Draw legal deterministic colour-symmetric circuits (orders in the class of Fig. 12) at P = 17 and P = 12
        (pipelined) and P = 20 (common frame) with an own CP-SAT model (own list of the 8 order variants, own
        legality = distinct residues mod P, own determinism = equal floor((t_X - t_Z)/P) on the two shared qubits,
        random objective, 8 s per draw, seeds 1..25), and write them to data/circuits/encoding_completeness_sample.json.gz.
check   For every listed circuit: the specification is legal (template rules) and deterministic (stim builds the
        DEM of the noiseless circuits, R = 3, both bases), and the primary SAT encoding without logical nogoods
        (enc_primary.Enc) accepts exactly that time assignment (solve under assumptions).

    python code/sat/completeness_sample.py check
    python code/sat/completeness_sample.py sample      # regenerate the sample (about 10 CPU minutes)
"""
import gzip
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ortools.sat.python import cp_model                        # noqa: E402
from pysat.solvers import Cadical153                            # noqa: E402

from common_cli import Verdict, load_code                       # noqa: E402
from gross12.paths import CIRCUITS                              # noqa: E402
from gross12.schedule import build_circuits, parse_schedule, validate_schedule  # noqa: E402
from sat.common import Family, colour, kernel, parse_orders, table  # noqa: E402
from sat.enc_primary import Enc                                 # noqa: E402

FILE = CIRCUITS / "encoding_completeness_sample.json.gz"
X = "A1A2A3B3B1B2,A1A2A3B1B2B3,A1A3A2B3B1B2"; Z = "A1A3A2B3B1B2,A1A2A3B1B2B3,A1A2A3B3B1B2"
col = (3, 1, 1)
orders = {"X": parse_orders(X), "Z": parse_orders(Z)}
F = Family(kernel(col))
ccol = [colour(col, F.reps[k]) for k in range(F.nc)]
T = table()
CASES = ((17, 0), (20, 1), (12, 0))


def variants(o):
    res = []
    for v in range(8):
        p = list(o)
        if v & 4:
            p = p[::-1]
        if v & 1:
            p[0], p[1] = p[1], p[0]
        if v & 2:
            p[4], p[5] = p[5], p[4]
        res.append(p)
    return res


def spec_of(t, st, P):
    d = {"format": "qec-schedule/v1", "period": P, "x_checks": [], "z_checks": []}
    for ty, key in (("X", "x_checks"), ("Z", "z_checks")):
        for i in range(72):
            u = (ty, F.cls[i])
            sv = st[u]
            cn = [[int(T[ty][i][l]), t[F.idx[(ty, F.cls[i], l)]] % P] for l in range(6)]
            d[key].append({"prep": sv % P, "meas": (sv + P - 1) % P, "cnots": cn})
    return d


def draw(P, nowrap, seed):
    rng = random.Random(seed)
    m = cp_model.CpModel()
    units = [(ty, k) for ty in "XZ" for k in range(F.nc)]
    s = {u: m.NewIntVar(0, 0 if nowrap else P - 1, "") for u in units}
    m.Add(s[("X", 0)] == 0)
    t = {}
    for u in units:
        vs = variants(orders[u[0]][ccol[u[1]]])
        b = [m.NewBoolVar("") for _ in vs]
        m.AddExactlyOne(b)
        tl = {lab: m.NewIntVar(1, 2 * P - 2, "") for lab in range(6)}
        for lab in range(6):
            m.Add(tl[lab] >= s[u] + 1); m.Add(tl[lab] <= s[u] + P - 2)
            t[F.idx[(u[0], u[1], lab)]] = tl[lab]
        for bv, p in zip(b, vs):
            for k in range(5):
                m.Add(tl[p[k]] < tl[p[k + 1]]).OnlyEnforceIf(bv)
    md = {}
    for i, v in t.items():
        r = m.NewIntVar(0, P - 1, ""); m.AddModuloEquality(r, v, P); md[i] = r
    for q in range(144):
        its = sorted({F.item(ty, c, lab) for ty, c, lab in F.touch[q]})
        m.AddAllDifferent([md[i] for i in its])
    for a in range(72):
        for c in range(72):
            sh = sorted(set(map(int, T["X"][a])) & set(map(int, T["Z"][c])))
            if not sh:
                continue
            fs = []
            for q in sh:
                ix = F.item("X", a, F.label_of("X", a, q)); iz = F.item("Z", c, F.label_of("Z", c, q))
                f = m.NewIntVar(-3, 3, ""); m.Add(P * f <= t[ix] - t[iz]); m.Add(t[ix] - t[iz] <= P * f + P - 1)
                fs.append(f)
            for f in fs[1:]:
                m.Add(f == fs[0])
    m.Maximize(sum(rng.randint(-5, 5) * v for v in t.values()) + sum(rng.randint(-5, 5) * v for v in s.values()))
    sol = cp_model.CpSolver(); sol.parameters.num_workers = 1; sol.parameters.random_seed = seed
    sol.parameters.max_time_in_seconds = 8
    if sol.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return {i: sol.Value(v) for i, v in t.items()}, {u: sol.Value(v) for u, v in s.items()}


if __name__ == "__main__":
    V = Verdict()
    code = load_code()
    if sys.argv[1] == "sample":
        out = []
        for P, nowrap in CASES:
            seen = set()
            for seed in range(1, 26):
                r = draw(P, nowrap, seed)
                if r is None:
                    continue
                t, st = r
                d = spec_of(t, st, P)
                h = json.dumps(parse_schedule(d).canonical().to_dict(), sort_keys=True)
                if h in seen:
                    continue
                seen.add(h)
                out.append({"P": P, "common_frame": nowrap, "seed": seed, "times": [t[i] for i in range(len(t))],
                            "starts": [[u[0], u[1], w] for u, w in st.items()], "spec": d})
        with gzip.open(FILE, "wt") as f:
            json.dump({"description": "Legal deterministic colour-symmetric circuits (Fig. 12 order class) drawn by "
                                      "code/sat/completeness_sample.py independently of the SAT encodings; 'times' = "
                                      "absolute CNOT time of every item of the colour-symmetric family, 'starts' = "
                                      "start of every unit.", "circuits": out}, f, separators=(",", ":"))
        print(len(out), "circuits written")
    else:
        D = json.load(gzip.open(FILE))["circuits"]
        for P, nowrap in CASES:
            M = Enc(F, orders, ccol, P, nowrap)
            rec = {"listed": 0, "legal": 0, "deterministic": 0, "accepted": 0}
            for c in D:
                if (c["P"], c["common_frame"]) != (P, nowrap):
                    continue
                rec["listed"] += 1
                t = dict(enumerate(c["times"])); st = {(ty, k): w for ty, k, w in c["starts"]}
                assert spec_of(t, st, P) == c["spec"]
                sp = parse_schedule(c["spec"])
                if validate_schedule(sp, code):
                    continue
                rec["legal"] += 1
                try:
                    for circ in build_circuits(sp.canonical(), code, 3).values():
                        circ.detector_error_model()
                except ValueError:
                    continue
                rec["deterministic"] += 1
                ass = [M.x[(i, v)] for i, v in t.items()] + [M.s[(u, w)] for u, w in st.items()]
                rec["accepted"] += int(Cadical153.solve(M.S, assumptions=ass))
            V(rec["listed"] > 0 and len(set(rec.values())) == 1,
              f"P={P} {'common frame' if nowrap else 'pipelined'}: {rec['listed']} sampled circuits, legal "
              f"{rec['legal']}, deterministic {rec['deterministic']}, models of the primary encoding {rec['accepted']}")
    V.exit()
