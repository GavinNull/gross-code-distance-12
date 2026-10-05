"""A5 positive control: lead's W=11 DFS solutions, mapped to the auditor's own BB-coordinate extended code
(column bijection of A1), must satisfy He x = 0, Le x != 0 with the auditor's own logical basis."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
import extx, a1_gross
OUT = Path("results/E-014-E-015-audit"); LEAD = Path("results/E-014-gross-dcirc11-proof")
from gf2 import logical_basis
HX, HZ = a1_gross.bb_mats()
from baselines.bb_code import gross_code
from baselines.strikis import strikis_fig12
sched, _ = strikis_fig12(gross_code())
xo = a1_gross.orders_from_layers(sched, HX, "X"); zo = a1_gross.orders_from_layers(sched, HZ, "Z")
res = {}
for kind, H, L, orders in (("X", HZ, logical_basis(HX, HZ), xo), ("Z", HX, logical_basis(HZ, HX), zo)):
    e = extx.build(H, L, orders, 144)
    He2, Le2, _, _ = extx.read128(LEAD / f"inst_{kind}.txt")
    ok, info = extx.compare_columns(e["He"], e["Le"], True, He2, Le2[:12])
    inv = {b: a for a, b in enumerate(info["map"])}
    sols = []
    for line in open(LEAD / f"positive_W11_{kind}.txt"):
        if line.startswith("FOUND"):
            cols = [int(x) for x in line.split("cols:")[1].split()]
            mine = [inv[c] for c in cols]
            x = np.zeros(e["He"].shape[1], int); x[mine] = 1
            sols.append(dict(w=len(set(mine)), He0=bool(not ((e["He"] @ x) % 2).any()), Le_nonzero=bool(((e["Le"] @ x) % 2).any()),
                             supports=[e["members"][j][0] for j in mine]))
    res[kind] = dict(n=len(sols), all_valid=all(s["w"] == 11 and s["He0"] and s["Le_nonzero"] for s in sols), first=sols[:1])
print(json.dumps(res, default=str)[:1500])
(OUT / "a6_w11.json").write_text(json.dumps(res, indent=1, default=str))
