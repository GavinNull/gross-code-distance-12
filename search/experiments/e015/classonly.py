"""Class test only (see twocol.py step 1) for a code / hom / target; prints alive block orders.
    PYTHONPATH=. uv run python search/experiments/e015/classonly.py bb108 01 10
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import BLOCKS, OUT, get_code, now  # noqa: E402
from twocol import _ctx, _job, states_for  # noqa: E402

code, hk, T = sys.argv[1], sys.argv[2], int(sys.argv[3])
out = {}
for kind in "XZ":
    res = [_job((code, kind, hk, "class", b, (0, 1), 300, T)) for b in range(len(BLOCKS))]
    alive = [r["payload"] for r in res if r["w"] is None or r["w"] >= T]
    c, col = _ctx(code, kind, hk)
    st = states_for(c, kind, col, alive)
    out[kind] = {"alive": alive, "hist": {str(w): sum(r["w"] == w for r in res) for w in {r["w"] for r in res}},
                 "proper_states": len(st), "nonuniform": sum(a != b for a, b in st)}
    print(f"[{now()}] {code} hom={hk} {kind} T={T}: {out[kind]}", flush=True)
(OUT / f"classonly_{code}_{hk}_T{T}.json").write_text(json.dumps(out, indent=1))
