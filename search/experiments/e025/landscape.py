"""E-025 structure probe: sample many model-blocking (all modelled logicals blocked in the bulk) colour-symmetric
circuits at a roomy period (P = 24) and record, per unit, the CNOT order and window (max - min CNOT time), and which
two labels realise the window.  Random phases per SAT call for diversity; each found timing is excluded."""
import json, random, sys, time
from collections import Counter
from pathlib import Path
import search.experiments.e021.nwfull as NF
from search.experiments.e021.mono import LAB
from search.experiments.e025.cegar_lib import Cegar
from search.experiments.e025.exact_cp import make_family

P = int(sys.argv[1]); N = int(sys.argv[2]); sub = sys.argv[3] if len(sys.argv) > 3 else "1,2;0,3"
F = make_family(sub)
recs, _ = NF.prepare_full(F, "XZ")
C = Cegar(F, P, recs)
rng = random.Random(7)
out = []
t0 = time.time()
while len(out) < N and time.time() - t0 < 3000:
    C.M.S.set_phases([rng.choice([1, -1]) * v for v in range(1, C.M.pool.top + 1)])
    st, t, info = C.run(600)
    if st != "MODEL_SAT":
        print("stop", st, info); break
    row = {}
    for u in F.units:
        its = {lab: t[F.idx[(u[0], u[1], lab)]] for lab in range(6)}
        o = sorted(its, key=its.get)
        row[f"{u[0]}{u[1]}"] = {"order": "".join(LAB[l] for l in o), "win": its[o[-1]] - its[o[0]], "t": [its[l] for l in range(6)]}
    out.append(row)
    C.M.add([-C.M.eq(i, t[i]) for i in range(len(t))])
    if len(out) % 10 == 0:
        print(len(out), f"{time.time()-t0:.0f}s", flush=True)
Path(f"results/E-025-gross12-perchk-period/landscape_P{P}.json").write_text(json.dumps(out))
for u in out[0]:
    print(u, "win min/max", min(r[u]["win"] for r in out), max(r[u]["win"] for r in out),
          "orders", Counter(r[u]["order"] for r in out).most_common(4))
