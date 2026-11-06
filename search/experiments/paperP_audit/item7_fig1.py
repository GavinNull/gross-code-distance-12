"""Item 7b: Fig. 1(b) example (u11, Z memory, weight-10 list item 0) checked with stim injection.
(1) realisations of every column of list 0 computed here from H, L (data qubits with equal key; hooks of all X checks
    with suffix length 1..5 with equal key); rigid hook columns; readers touched only by the two rigid hooks.
(2) stim: inject each hook alone (instance j=2, R=6), read the instance index at which Z58 / Z60 fire; holonomy.
  PYTHONPATH=.:tests uv run python search/experiments/paperP_audit/item7_fig1.py
"""
import json, pickle, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(Path(__file__).parent))
from item3_triples import CODES, build
from inject import Injector

HX, HZ, labX, labZ = build(CODES["gross"])
from search.theory.B_audit.common import get_code
code = get_code("gross"); LZ = np.asarray(code.LZ) % 2
spec = json.load(open(ROOT / "search/experiments/e032/u11_spec.json")); P = spec["period"]


def key(qs):
    v = np.zeros(144, np.uint8); v[list(qs)] = 1
    return ((HZ.astype(int) @ v) % 2).astype(np.uint8).tobytes() + ((LZ.astype(int) @ v) % 2).astype(np.uint8).tobytes()


order = []
for ch in spec["x_checks"]:
    p = ch["prep"] % P
    order.append([q for _, q in sorted((p + ((t - p) % P), q) for q, t in ch["cnots"])])
real = defaultdict(list)
for q in range(144):
    real[key([q])].append(("d", q))
for c, o in enumerate(order):
    for L in range(1, 6):
        real[key(o[6 - L:])].append(("h", c, L))
S = pickle.load(open(ROOT / "results/E-032-gross-short-period/w10_X_all_A1A2A3B3B1B2.pkl", "rb"))["keys"][0]
cols = [real[k] for k in S]
touch = defaultdict(set)
for ci, rs in enumerate(cols):
    for r in rs:
        qs = [r[1]] if r[0] == "d" else order[r[1]][6 - r[2]:]
        for q in qs:
            for z in np.flatnonzero(HZ[:, q]):
                touch[int(z)].add(ci)
rigid = {ci: rs[0] for ci, rs in enumerate(cols) if len(rs) == 1 and rs[0][0] == "h"}
priv = {z: sorted(cs) for z, cs in touch.items() if len(cs) == 2 and set(cs) <= set(rigid)}
print("columns:", [rs if len(rs) <= 2 else f"{len(rs)} realisations" for rs in cols])
print("rigid hook columns:", rigid)
print("readers touched only by two rigid hooks:", priv)

inj = Injector(spec, code, "Z", 6)
idx = {}
for ci, (_, c, L) in rigid.items():
    fired, obs = inj.run([("anc", "X", c, 2, 6 - L)])
    idx[(c, L)] = {z: [j for (zz, j) in fired if zz == z] for z in (58, 60)}
    print(f"hook X{c} suffix {L}: Z58 fires at {idx[(c, L)][58]}, Z60 at {idx[(c, L)][60]}, all fired {sorted(fired)}")
